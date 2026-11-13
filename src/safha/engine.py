"""The pipeline: detect -> decide -> check -> frames, producing a recipe (plain JSON) that ``apply`` turns into a PDF.

``plan(path)`` reads a scanned book and returns its recipe; nothing is written. Each page is measured in parallel when
``jobs`` > 1; the result does not depend on the number of jobs.
"""

from __future__ import annotations

import copy
import hashlib
import math
import os
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import pymupdf

from . import __version__
from .decide import decide
from .detect import Looker, measure_page
from .geometry import inside, thin_line, union
from .measure import figures_of, notes_of, printed_groups, printlike, text_block
from .pages import find_spreads
from .pdf import open_book, text_direction
from .profile import Profile, load_profile

SCHEMA = 1
Progress = Callable[[str, int, int], None] | None


# -- parallel page work -------------------------------------------------------------------------------------------------

def _measure_chunk(args: tuple) -> dict[int, dict]:
    path, split, direction, prof, idx = args
    doc = open_book(path, {"split": split, "direction": direction})
    try:
        return {i: measure_page(doc, i, prof) for i in idx}
    finally:
        doc.close()


def _check_chunk(args: tuple) -> dict[int, dict]:
    path, split, direction, prof, rec, idx = args
    doc = open_book(path, {"split": split, "direction": direction})
    try:
        out = {}
        for i in idx:
            p = rec["pages"][i]
            check_page(doc, i, p, rec, prof)
            out[i] = p
        return out
    finally:
        doc.close()


def _run(fn: Callable, base: tuple, n: int, jobs: int, progress: Progress, stage: str) -> dict[int, Any]:
    idx = list(range(n))
    if jobs <= 1 or n < 4:
        out: dict[int, Any] = {}
        step = max(1, n // 50)
        for k in range(0, n, step):
            out.update(fn(base + (idx[k:k + step],)))
            if progress:
                progress(stage, min(n, k + step), n)
        return out
    jobs = min(jobs, n)
    chunks = [idx[k::jobs] for k in range(jobs)]
    out = {}
    with ProcessPoolExecutor(jobs) as ex:
        done = 0
        for part in ex.map(fn, [base + (c,) for c in chunks]):
            out.update(part)
            done += len(part)
            if progress:
                progress(stage, done, n)
    return out


# -- the second check of the box, at check_px --------------------------------------------------------------------------

def _near(b: list, regions: list) -> bool:
    return any(b[0] < r[2] + 3 and b[2] > r[0] - 3 and b[1] < r[3] + 3 and b[3] > r[1] - 3 for r in regions)


def check_page(doc: pymupdf.Document, i: int, p: dict, rec: dict, prof: Profile) -> None:
    """SECOND LOOK AT THE BOX, on the page as the reader will see it, at prof.check_px: every content mark outside the box
    must lie on something the first look left out on purpose (a stain, edge noise, a scan line); otherwise the box slides
    (<= 2 % of the page) to take it in, or grows with the same proportions (a book with clean margins), or the page stays
    whole. Nothing of the text may be cut."""
    if not p.get("crop") or p["kind"] != "text":
        return
    lk = Looker(doc, i)
    try:
        q = {k: p[k] for k in ("skew", "shear", "move") if p.get(k)}
        mk = lk.look(q, prof.check_px)
    finally:
        lk.close()
    w, h, z = p["w"], p["h"], mk["z"]
    c = p["crop"]
    pts = [b for b in mk.get("parts") or [] if printlike(b, w, h, z)]
    known = (p.get("blots") or []) + (p.get("edge") or []) + (p.get("rules_dropped") or []) + (p.get("lines") or []) \
        + (p.get("cut_stray") or [])
    al = p.get("allowed")

    def in_allowed(b: list) -> bool:
        return not al or (al[0] - 0.01 * w <= (b[0] + b[2]) / 2 <= al[2] + 0.01 * w
                          and al[1] - 0.01 * h <= (b[1] + b[3]) / 2 <= al[3] + 0.01 * h)

    def fits(nb: list) -> bool:
        return nb[0] >= -0.5 and nb[1] >= -0.5 and nb[2] <= w + 0.5 and nb[3] <= h + 0.5

    if rec.get("clean_margins") and mk.get("text"):
        t0 = p.get("text")
        t = (text_block(pts, t0, w, h, z) if t0 else None) or mk["text"]
        if t0:
            t = [max(t[0], t0[0] - 0.03 * w), max(t[1], t0[1] - 0.03 * h), min(t[2], t0[2] + 0.03 * w),
                 min(t[3], t0[3] + 0.03 * h)]
        mg2 = [b for b in pts if not inside(b, t, 0.5)]
        nts, figs = notes_of(mg2, w, h), figures_of(mg2, w, h)
        if nts:
            p["notes"] = nts
        tn = union([t] + nts + figs)
        gx, gy = 0.015 * w, 0.015 * h

        def straddles(b: list, r: list, s: list) -> bool:
            return (not inside(b, r, 1.0) and b[0] < r[2] and b[2] > r[0] and b[1] < r[3] and b[3] > r[1]
                    and not _near(b, known) and b[2] >= s[0] - gx and b[0] <= s[2] + gx and b[3] >= s[1] - gy
                    and b[1] <= s[3] + gy and not thin_line(b, w, h) and in_allowed(b))

        cross = [b for b in pts if straddles(b, c, t)]
        need = ([tn] if not inside(tn, c, 1.0) else []) + cross
        if need:
            u = union(need + [tn])
            mg = rec.get("margin_pt") or 0.01 * (c[2] - c[0])

            def place(u: list) -> tuple[list, float | None]:
                hm = 0.5 * mg
                up = [u[0] - hm, u[1] - hm, u[2] + hm, u[3] + hm]
                dx = up[0] - c[0] if up[0] < c[0] else (up[2] - c[2] if up[2] > c[2] else 0)
                dy = up[1] - c[1] if up[1] < c[1] else (up[3] - c[3] if up[3] > c[3] else 0)
                nb = [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]
                if abs(dx) <= 0.02 * w and abs(dy) <= 0.02 * h and inside(up, nb, 1.0) and fits(nb):
                    return nb, None
                cw, ch = c[2] - c[0], c[3] - c[1]
                sc = max(1.0, (u[2] - u[0] + 2 * mg) / cw, (u[3] - u[1] + 2 * mg) / ch)
                smax = min(w / cw, h / ch)
                if sc > smax:
                    sc = max(1.0, smax, (u[2] - u[0]) / cw, (u[3] - u[1]) / ch)
                x2, y2 = (u[0] + u[2]) / 2, (u[1] + u[3]) / 2
                nb = [x2 - cw * sc / 2, y2 - ch * sc / 2, x2 + cw * sc / 2, y2 + ch * sc / 2]
                sx = -nb[0] if nb[0] < 0 else (w - nb[2] if nb[2] > w else 0)
                sy = -nb[1] if nb[1] < 0 else (h - nb[3] if nb[3] > h else 0)
                return [nb[0] + sx, nb[1] + sy, nb[2] + sx, nb[3] + sy], sc

            nb, sc = place(u)
            st = [b for b in pts if straddles(b, nb, u)]
            if st:
                u = union([u] + st)
                nb, sc = place(u)
            if sc is not None and sc > 1.0001:
                p["enlarged"] = round(max(sc, p.get("enlarged", 1.0)), 3)
            if fits(nb) and inside(u, nb, 1.0):
                p["crop"] = [round(max(0, nb[0]), 2), round(max(0, nb[1]), 2), round(min(w, nb[2]), 2), round(min(h, nb[3]), 2)]
                p["flags"].append("check_moved")
            else:
                p["crop"] = None
                p["need"] = u
                p["flags"].append("whole")
        return
    out = [b for b in pts if not inside(b, c, 1.0) and not _near(b, known) and in_allowed(b)]
    if out:
        tq = (text_block(pts, p["text"], w, h, z) if p.get("text") else None) or mk.get("text")
        mg_ = [b for b in pts if not tq or not inside(b, tq, 0.5)]
        needs = ([tq] if tq else []) + notes_of(mg_, w, h) + figures_of(mg_, w, h) + printed_groups(mg_, w, h)

        def meets(b: list, nb: list) -> bool:
            return b[0] < nb[2] + 1 and b[2] > nb[0] - 1 and b[1] < nb[3] + 1 and b[3] > nb[1] - 1

        cut = [b for b in out if not any(meets(b, nb) for nb in needs)]
        if cut:
            p["cut_stray"] = (p.get("cut_stray") or []) + cut
        out = [b for b in out if any(meets(b, nb) for nb in needs)]
    if out:
        ob = union(out)
        dx = ob[0] - c[0] if ob[0] < c[0] else (ob[2] - c[2] if ob[2] > c[2] else 0)
        dy = ob[1] - c[1] if ob[1] < c[1] else (ob[3] - c[3] if ob[3] > c[3] else 0)
        nb = [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]
        if abs(dx) <= 0.02 * w and abs(dy) <= 0.02 * h and fits(nb) and (p.get("box") is None or inside(p["box"], nb, 1.0)) \
                and all(inside(b, nb, 1.0) for b in out):
            p["crop"] = [round(v, 2) for v in nb]
            p["flags"].append("check_moved")
        else:
            p["crop"] = None
            p["need"] = ob
            p["flags"].append("whole")


# -- one page size for the whole book ------------------------------------------------------------------------------------

def frames(rec: dict, prof: Profile) -> dict:
    """ONE PAGE SIZE FOR THE WHOLE BOOK: every page shown in a box of exactly the book's size W x H -- ``show`` (the part of
    the page shown, in the reader's frame) and ``scale`` (W / its width). A page whose needed part is larger (a page no box
    holds, a plate, a cover) shows that part whole, drawn smaller; a page smaller than the box is drawn up to 5 % larger
    when all it holds still fits, else on blank paper beyond its own edge (``bands``)."""
    W, H = rec["size"]
    A = W / H
    m = rec.get("margin_pt") or 0.0
    n_ = len(rec["pages"])
    for k_, p in enumerate(rec["pages"]):
        for k in ("show", "scale", "bands", "fit_whole"):
            p.pop(k, None)
        pw, ph = p["w"], p["h"]
        c = p.get("crop")
        if p["kind"] == "rotated":
            p["fit_whole"] = True
            continue
        own_cover = (k_ < 2 or k_ >= n_ - 4) and p["kind"] in ("cover", "picture")
        if own_cover and not c:
            c = [0.0, 0.0, pw, ph]
        if (p["kind"] == "cover" and c) or own_cover:  # a cover fills the frame, cut to the book's proportions (<= 8 %)
            cw, chh = c[2] - c[0], c[3] - c[1]
            if cw / chh > A and (cw - chh * A) / cw <= 0.08:
                d = (cw - chh * A) / 2
                c = [c[0] + d, c[1], c[2] - d, c[3]]
            elif cw / chh < A and (chh - cw / A) / chh <= 0.08:
                d = (chh - cw / A) / 2
                c = [c[0], c[1] + d, c[2], c[3] - d]
        if c and abs(c[2] - c[0] - W) <= 1.0 and abs(c[3] - c[1] - H) <= 1.0:
            x, y, rw, rh = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2, W, H
        else:
            if c:
                N = c
            elif p["kind"] in ("picture", "blank"):
                N = [0.0, 0.0, pw, ph]
            else:
                parts = [b for b in (p.get("box"), p.get("content_box"), p.get("need")) if b]
                N = union(parts) if parts else [0.0, 0.0, pw, ph]
                N = [max(0.0, N[0] - m), max(0.0, N[1] - m), min(pw, N[2] + m), min(ph, N[3] + m)]
            nw, nh = max(N[2] - N[0], 1.0), max(N[3] - N[1], 1.0)
            rw, rh = (nw, nw / A) if nw / nh > A else (nh * A, nh)
            if rw < W and p["kind"] != "cover" and not own_cover:
                rw, rh = W, H
            x, y = (N[0] + N[2]) / 2, (N[1] + N[3]) / 2
            if rw > pw + 0.5 or rh > ph + 0.5:  # beyond the page: rather up to 5 % larger, if all it holds still fits
                fw_ = min(pw, ph * A)
                fh_ = fw_ / A
                if W / fw_ <= prof.magnify_max:
                    fx, fy = min(max(x, fw_ / 2), pw - fw_ / 2), min(max(y, fh_ / 2), ph - fh_ / 2)
                    F = [fx - fw_ / 2, fy - fh_ / 2, fx + fw_ / 2, fy + fh_ / 2]
                    if all(inside(b, F, 1.0) for b in (p.get("box"), p.get("need")) if b):
                        x, y, rw, rh = fx, fy, fw_, fh_
        if rw <= pw:
            x = min(max(x, rw / 2), pw - rw / 2)
        if rh <= ph:
            y = min(max(y, rh / 2), ph - rh / 2)
        p["show"] = [round(v, 3) for v in (x - rw / 2, y - rh / 2, x + rw / 2, y + rh / 2)]
        p["scale"] = round(W / rw, 6)
        if rw > pw + 0.01 or rh > ph + 0.01:
            p["bands"] = True
    return rec


def level_only(rec: dict) -> dict:
    """LEVEL ONLY: a good scan whose only flaw is tilted pages (or whose pages no one box holds): the tilted pages are
    turned and nothing else changes. On white paper a turned page's bare corners do not show; on grey or coloured paper
    every page loses the same thin strip, just enough to hide them."""
    pages = rec["pages"]
    rec["decision"] = "level"
    turned = [p for p in pages if p.get("skew") or p.get("shear")]
    if not turned:
        rec["decision"] = "skip"
        rec["why"] = rec.get("why") or "a good scan; no tilt confirmed"
        return rec
    paper = sorted(p.get("paper", 255) for p in pages if p["kind"] == "text")
    white = not paper or paper[len(paper) // 2] >= 250
    t = math.sin(math.radians(max(abs(p.get("skew") or 0) + abs(p.get("shear") or 0) for p in turned)))
    for p in pages:
        for k in ("show", "scale", "bands", "move", "enlarged"):
            p.pop(k, None)
        if white or p["kind"] == "rotated":
            p["crop"] = None
            continue
        tx, ty = p["h"] / 2 * t + 1, p["w"] / 2 * t + 1
        p["crop"] = [round(tx, 2), round(ty, 2), round(p["w"] - tx, 2), round(p["h"] - ty, 2)]
    rec["level_trim"] = None if white else round(t, 5)
    return rec


# -- the whole method ---------------------------------------------------------------------------------------------------

def file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def plan(path: str, profile: Profile | str | None = None, jobs: int = 1, progress: Progress = None,
         drop: list[int] | None = None) -> dict:
    """the recipe of a scanned book: per page its turn, shear, move and the part shown; nothing is written"""
    prof = profile if isinstance(profile, Profile) else load_profile(profile)
    t0 = time.time()
    src = pymupdf.open(path)
    if src.needs_pass:
        raise ValueError(f"{path}: the PDF is encrypted with a password")
    n0 = src.page_count
    direction = prof.direction if prof.direction in ("ltr", "rtl") else (text_direction(src) or "ltr")
    split = find_spreads(src, prof.split)
    src.close()
    n = n0 + len(split)
    pages_d = _run(_measure_chunk, (path, split, direction, prof), n, jobs, progress, "measure")
    pages = [pages_d[i] for i in range(n)]
    rec: dict = {}
    for wq in prof.width_quantiles:
        rec = decide(copy.deepcopy(pages), prof, wq)
        if rec["decision"] != "crop":
            if rec["decision"] == "skip" and "do not fit" in rec.get("why", "") and wq < prof.width_quantiles[-1]:
                continue
            break
        checked = _run(_check_chunk, (path, split, direction, prof, rec), n, jobs, progress, "check")
        for i, p in checked.items():
            rec["pages"][i] = p
        rec["whole"] = sorted(i for i, p in enumerate(rec["pages"]) if "whole" in p["flags"])
        if len(rec["whole"]) > prof.max_whole * max(1, rec["measured"]):
            rec["decision"] = "skip"
            rec["why"] = f"{len(rec['whole'])} pages do not fit one box (second check)"
            continue
        rec["width_quantile"] = wq
        frames(rec, prof)
        break
    if rec["decision"] == "level" or (rec["decision"] == "skip" and "do not fit" in rec.get("why", "")
                                      and any(p.get("skew") or p.get("shear") for p in rec["pages"])):
        rec = level_only(rec)
    return finish(rec, path, prof, split, direction, n0, drop, time.time() - t0)


SUMMARY_FLAGS = ("found_in_check", "frame_turn", "frame_shear", "two_angles", "unsure_tilt", "untreated_tilt",
                 "tilt_disputed", "curved", "whole", "own_centre", "dodged", "check_moved", "level_by_tracks")


def finish(rec: dict, path: str, prof: Profile, split: dict, direction: str, n0: int, drop: list[int] | None,
           seconds: float) -> dict:
    from .detect import to_recipe_page

    pages = [to_recipe_page(p) for p in rec["pages"]]
    for p in pages:
        for k in ("level_frame",):
            p.pop(k, None)
    out: dict[str, Any] = {
        "safha": __version__, "schema": SCHEMA,
        "source": {"file": os.path.basename(path), "bytes": os.path.getsize(path), "md5": file_md5(path), "pages": n0},
        "profile": {"name": prof.name, "changed": prof.diff()},
        "mode": rec["decision"],
    }
    if rec.get("why"):
        out["why"] = rec["why"]
    if split:
        out["split"] = split
    out["direction"] = direction
    if drop:
        out["drop"] = sorted(set(drop))
    for k in ("reasons", "size", "gain", "gain_h", "framed", "clean_margins", "margin_pt", "offcentre", "sway",
              "parity_offsets", "width_quantile", "level_trim"):
        if k in rec:
            out[k] = rec[k]
    summ: dict[str, Any] = {
        "pages": len(pages), "text": sum(1 for p in pages if p["kind"] == "text"),
        "turned": [p["n"] for p in pages if p.get("skew")],
        "sheared": [p["n"] for p in pages if p.get("shear")],
        "moved": [p["n"] for p in pages if p.get("move")],
        "scaled": [p["n"] for p in pages if p.get("scale") and abs(p["scale"] - 1) > 1e-4],
    }
    for f in SUMMARY_FLAGS:
        summ[f] = [p["n"] for p in pages if f in (p.get("flags") or [])]
    summ["kinds"] = {k: sum(1 for p in pages if p["kind"] == k) for k in sorted({p["kind"] for p in pages})}
    summ["seconds"] = round(seconds, 2)
    out["summary"] = summ
    out["pages"] = pages
    return _clean(out)


def _clean(v: Any) -> Any:
    """plain JSON types: numpy numbers to Python, floats rounded to 3 decimals"""
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, int) and not hasattr(v, "dtype"):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if hasattr(v, "dtype") and str(getattr(v, "dtype", "")).startswith(("int", "uint")):
        return int(f)
    return round(f, 3)

