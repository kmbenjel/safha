"""DETECT: the first look (every page at 500 px) and the second look at the tilt (1,000 px).

A page is turned only when two independent measures agree that it is tilted and that the turned page reads level; a turn
that makes level lines lean (a warped leaf whose lines lie at two angles) is undone; a printed frame decides the tilt of
the page it surrounds. When unsure, the page stays as scanned and is listed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pymupdf

from .geometry import rnd
from .measure import marks
from .pages import cover_rect
from .pdf import Turner, beyond_sheet, display_matrix, gray, sheet_corners, shown_as_computed
from .profile import Profile
from .tilt import (
    EPS,
    baseline_tilt,
    columns_tilt,
    edges_refuse,
    frame_lean,
    frame_shear,
    ink_mask,
    line_tracks,
    lines_read,
    print_turn,
    proj_tilt,
    rules_made_to_lean,
    skew_of,
    two_angles,
)

KEEP_KEYS = ("box", "core", "text", "allowed", "blots", "edge", "lines", "rules", "margin", "folio", "specks", "paper",
             "level_frame")


class Looker:
    """the views of one page (turned, sheared, moved) at a given resolution, each measured once"""

    def __init__(self, doc: pymupdf.Document, i: int, first_px: int = 500, bed: list | None = None):
        self.doc, self.i = doc, i
        self.tu = Turner(doc, i)
        self.views: dict[tuple, dict] = {}
        self.first_px = first_px
        self._bed = bed

    def bed(self) -> list[bool]:
        """the sides (left, top, right, bottom) on which the page as scanned ends in a scanner band"""
        if self._bed is None:
            b = self.look({}, self.first_px).get("bands")
            r = self.tu.page().rect
            self._bed = [b[0] > 0.5, b[1] > 0.5, b[2] < r.width - 0.5, b[3] < r.height - 0.5] if b else [False] * 4
        return self._bed

    def look(self, q: dict, px: int) -> dict[str, Any]:
        mv = q.get("move") or [0, 0]
        key = (round(q.get("skew") or 0, 4), round(q.get("shear") or 0, 4), mv[0], mv[1], px)
        if key in self.views:
            return self.views[key]
        # a view that is turned shows nothing beyond the scan's sheet: where the scan ends in a scanner band, the bed
        # went on there, and the bands are read as if it did
        bed = self.bed() if any(key[:4]) else None
        page = self.tu.page(key[0], mv[0], mv[1], key[1])
        a, z = gray(page, px)
        a = np.array(a)
        void = None
        if bed and any(bed):
            void = beyond_sheet(a.shape, sheet_corners(page, {"skew": key[0], "shear": key[1], "move": mv}), z, bed)
        mk = marks(a, z, page.rect.width, void=void)
        mk["z"], mk["img"] = z, a
        memo: dict = {}

        def once(k: Any, f: Any) -> Any:
            if k not in memo:
                memo[k] = f()
            return memo[k]

        mk["proj"] = lambda lo=-0.5, hi=0.5, step=0.05: once(("proj", lo, hi, step),
                                                             lambda: proj_tilt(a, mk["paper"], lo, hi, step))
        mk["lines_fn"] = lambda: once("lines", lambda: baseline_tilt(a, mk["paper"]) if mk.get("paper") else None)
        mk["tracks"] = lambda: once("tracks", lambda: line_tracks(a, mk["paper"], mk.get("text"), z)
                                    if mk.get("paper") else [])
        def ink(key: str) -> np.ndarray | None:  # content ink as an image of the page inside its scanner bands
            xy, bd = mk.get(key), mk.get("bands")
            if xy is None or len(xy[0]) == 0:
                return None
            hw = (int(xy[1].max()) + 1, int(xy[0].max()) + 1)
            if bd:
                hw = (max(hw[0], int(round((bd[3] - bd[1]) * z))), max(hw[1], int(round((bd[2] - bd[0]) * z))))
            return ink_mask(xy, hw)

        mk["ink"] = lambda: once("ink", lambda: ink("xy"))            # print and rules: where a column rule is sought
        mk["ink_text"] = lambda: once("ink_text", lambda: ink("xy_text"))  # print alone: what its edges are read on
        mk["cols"] = lambda: once("cols", lambda: columns_tilt(mk["ink"]()) if mk["ink"]() is not None else None)
        self.views[key] = mk
        return mk

    def close(self) -> None:
        self.tu.close()


def texty(mk: dict, least: int = 100) -> bool:
    """a page of real text, whose tilt can be read: at least ``least`` letter-sized marks (a blank leaf with a binding
    shadow, a plate or a few words has no lines to level)"""
    parts = mk.get("parts") or []
    if len(parts) < least or not mk.get("text"):
        return False
    t = mk["text"]
    h, w = max(1.0, t[3] - t[1]), max(1.0, t[2] - t[0])
    small = sum(1 for b in parts if b[3] - b[1] <= 0.08 * h and b[2] - b[0] <= 0.15 * w)
    return small >= least


def _ink(mk: dict) -> int:
    return 0 if mk.get("xy") is None else len(mk["xy"][0])


def _inner(page: pymupdf.Page, q: dict, b: list) -> list:
    """the largest upright box inside box ``b`` as it lies once the page is turned like ``q`` (scanner bands carried over)"""
    tm = display_matrix(page)
    from .pdf import frame_matrix
    m = ~tm * frame_matrix(page, q) * tm
    pts = [pymupdf.Point(x, y) * m for x, y in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
    xs = sorted(p.x for p in pts)
    ys = sorted(p.y for p in pts)
    return [xs[1], ys[1], xs[2], ys[2]]


def first_look(doc: pymupdf.Document, i: int, prof: Profile, lk: Looker) -> tuple[dict, dict]:
    """measure page i at prof.first_px and find its tilt -> (page record, the marks of the view it settled on)"""
    page = doc[i]
    r = page.rect
    n = doc.page_count
    rec: dict[str, Any] = {"n": i + 1, "w": round(r.width, 2), "h": round(r.height, 2), "flags": []}
    if not shown_as_computed(page):  # (a /Rotate or a box MuPDF reads another way: the page is shown whole)
        rec["kind"] = "rotated"
        return rec, {}
    q0: dict = {}
    sheet = None
    if prof.covers and (i < 2 or i >= n - 2):
        cv = cover_rect(page)
        if cv:
            mk = lk.look(q0, prof.first_px)
            t = mk.get("text")
            # a page of text on a dark scanner bed is no cover: the «cover» is its sheet, which bounds the box
            if mk["box"] is not None and mk["dark"] <= 0.35 and len(mk.get("parts") or []) >= 150 and t \
                    and t[0] >= cv[0] and t[2] <= cv[2] and t[1] >= cv[1] and t[3] <= cv[3]:
                sheet = cv
            else:
                rec.update(kind="cover", cover=cv, box=cv)
                return rec, {}
    mk = lk.look(q0, prof.first_px)
    if sheet and mk.get("allowed"):
        al = mk["allowed"]
        rec["sheet"] = sheet
        mk["allowed"] = [max(al[0], sheet[0]), max(al[1], sheet[1]), min(al[2], sheet[2]), min(al[3], sheet[3])]
    if mk["box"] is not None and mk["dark"] <= 0.35 and prof.deskew and texty(mk):
        ang, gain = skew_of(mk["xy"], wide=prof.skew_max)
        if 0.1 <= abs(ang) < 0.35:  # small: measured again at twice the resolution
            ang, gain = skew_of(lk.look(q0, 2 * prof.first_px)["xy"], wide=prof.skew_max)
        if abs(ang) >= 1.0 and mk.get("level_frame"):  # a photographed leaf inside a level printed frame: not turned
            rec["frame_level"] = round(ang, 3)
            ang = 0.0
        if abs(ang) >= prof.skew_min and gain >= 1.02:
            for deg in (-ang, ang):
                q = {"skew": round(deg, 3)}
                mk2 = lk.look(q, prof.first_px)
                if mk2["box"] is None or mk2["xy"] is None or not 0.6 <= _ink(mk2) / max(1, _ink(mk)) <= 5.0:
                    continue
                left, _ = skew_of(mk2["xy"], raw=True)
                if abs(left) <= max(0.1, abs(ang) / 3):
                    rec["skew"] = q["skew"]
                    rec["tilt"] = round(-q["skew"], 3)
                    break
    return rec, mk


def _carry_bands(page: pymupdf.Page, rec: dict, mk0: dict, mk: dict) -> None:
    """the bands and edge shadows read on the page as scanned bound the turned page too, on every side where the
    turned page shows none of its own (a shadow the turn has lifted off the page's edge)"""
    al0 = mk0.get("allowed")
    if not rec.get("skew") or not al0 or not mk.get("allowed"):
        return
    w, h = rec["w"], rec["h"]
    al = mk["allowed"]
    bd = [al0[0] > 0.5 and al[0] <= 0.5, al0[1] > 0.5 and al[1] <= 0.5, al0[2] < w - 0.5 and al[2] >= w - 0.5,
          al0[3] < h - 0.5 and al[3] >= h - 0.5]
    if not any(bd):
        return
    a_ = _inner(page, rec, al0)
    mk["allowed"] = [max(al[0], a_[0]) if bd[0] else al[0], max(al[1], a_[1]) if bd[1] else al[1],
                     min(al[2], a_[2]) if bd[2] else al[2], min(al[3], a_[3]) if bd[3] else al[3]]


def second_look(doc: pymupdf.Document, i: int, p: dict, prof: Profile, lk: Looker) -> None:
    """the tilt checked at prof.check_px on the page as the reader will see it: a turn is kept only when the turned page
    reads level by two measures; tilts the first look missed are found; lines at two angles undo a turn; a printed frame
    decides the turn (and a sheared print is sheared level)"""
    px = prof.check_px
    flags: list[str] = p["flags"]
    level, img_level, curved = prof.level + 1e-6, prof.img_level + 1e-6, prof.curved + 1e-6

    def unturned() -> dict:
        return {k: v for k, v in p.items() if k not in ("skew", "shear")}

    def best_turn(d0: float) -> tuple[float, float, float, dict]:
        tried: dict[float, tuple] = {}

        def ev(d: float) -> tuple:
            d = round(d, 3)
            if d not in tried:
                m2 = lk.look(dict(p, skew=d), px)
                tried[d] = (9.0, 9.0, m2) if m2["xy"] is None else (abs(skew_of(m2["xy"], raw=True)[0]), m2["proj"](), m2)
            return tried[d]

        r, im, m2 = ev(d0)
        if r <= level and im <= img_level:
            return round(d0, 3), r, im, m2
        for k in range(1, 6):
            ev(d0 - 0.05 * k)
            ev(d0 + 0.05 * k)

        def key(kv: tuple) -> tuple:
            return max(kv[1][0], kv[1][1]), kv[1][0]

        lv = [kv for kv in tried.items() if kv[1][0] <= level and kv[1][1] <= img_level]
        d, (r, im, m2) = min(lv or tried.items(), key=key)
        if not (r <= level and im <= img_level):  # none level by both: the one whose lines read most level
            cl = []
            for dd, v in tried.items():
                if max(v[0], v[1]) <= 0.35:
                    b = v[2]["lines_fn"]()
                    cl.append((round(abs(b), 3) if b is not None else 9, v[0], dd, v))
            if cl and min(cl, key=lambda c: c[:3])[0] <= 0.15:
                _, _, d, (r, im, m2) = min(cl, key=lambda c: c[:3])
        return d, r, im, m2

    def keep(d: float, r: float, im: float, before: float, m2: dict) -> bool:
        if r <= level and im <= img_level:
            return True
        if r <= curved and im <= curved and max(r, im) <= abs(before) / 3:
            flags.append("curved")
            return True
        if abs(before) >= 0.4 and max(r, im) <= min(0.35, abs(before) - 0.15):
            b = m2["lines_fn"]()
            if b is not None and abs(b) <= 0.15:
                flags.append("level_by_lines")
                return True
        if abs(before) >= 1.5 and max(r, im) <= max(0.4, 0.2 * abs(before)):
            flags.append("reduced")
            return True
        return False

    def set_turn(d: float, r: float, im: float) -> None:
        p["skew"] = round(d, 3)
        p["after"] = [round(r, 3), round(im, 3)]

    def refused(d: float, m2: dict) -> bool:
        """the text's own margins against the turn ``d`` (edges_refuse: on the page as scanned and on the page as turned,
        ``m2``, they show less than half the tilt the turn was made for): the page then stays as scanned and is listed --
        unless its print certifies the turn: every printed rule across the text (half the block wide or more) stands
        level once turned (<= 0.15 deg). A sheared print, its lines and rules leaning one way and its margins another,
        is levelled by its lines and rules."""
        if not prof.edge_guard:
            return False
        R = [t for t in mk0["tracks"]() if t[5] and t[3] <= 1.0 and t[4] >= 6 and t[2] >= 0.5]
        if R and all(abs(t[1] - d) <= 0.15 + EPS for t in R):
            return False
        e = edges_refuse(mk0["ink_text"](), -d, turned=m2["ink_text"]())
        if e:
            p["edges"] = e
            if "tilt_disputed" not in flags:
                flags.append("tilt_disputed")
        return bool(e)

    mk0 = lk.look(unturned(), px)
    # TWO COLUMNS WITH A PRINTED RULE BETWEEN THEM: the whole-page measures are not trusted on such a page (a dictionary
    # whose headword and gloss stand at different heights in the line, an index of short entries: their row profile
    # sharpens at an angle the lines do not lie at). The rule is the page's upright: the page is turned by its lean
    # (>= 0.25 deg) when the rule stands upright once turned (<= 0.15 deg), or it stays as scanned and is listed.
    ct = mk0["cols"]() if prof.deskew else None
    if ct is not None:
        had = p.pop("skew", None)
        tr, tl = ct
        if tr is not None and tl is not None and tr * tl > 0 and min(abs(tr), abs(tl)) >= 0.25 \
                and abs(tr - tl) <= max(0.15, 0.15 * max(abs(tr), abs(tl))) + EPS:
            u2 = (tr + tl) / 2
            best: tuple | None = None
            # the turn that squares an edge is minus its lean: that turn first, then the turns beside it (0.05 deg apart),
            # and only if none stands the columns upright the turns the other way
            for sgn in (-1, 1):
                for k in (0, -1, 1, -2, 2, -3, 3):
                    d = round(sgn * u2 + 0.05 * k, 3)
                    if abs(d) < prof.skew_min - EPS:
                        continue
                    m2 = lk.look(dict(unturned(), skew=d), px)
                    c2 = m2["cols"]()
                    if not c2 or c2[0] is None or c2[1] is None:
                        continue
                    sc = max(abs(c2[0]), abs(c2[1]))
                    if best is None or sc < best[0]:
                        best = (sc, d, m2)
                    if sc <= 0.05 + EPS:
                        break
                if best and best[0] <= 0.15 + EPS:
                    break
            if best and best[0] <= 0.15 + EPS:
                sc, d, m2 = best
                p["skew"] = d
                p["tilt"] = round(-d, 3)
                p["columns"] = {"tilt": [round(tr, 3), round(tl, 3)], "after": round(sc, 3)}
                flags.append("by_columns")
            else:
                p["tilt"] = round(u2, 3)
                flags.append("tilt_disputed")
        elif had:
            p.pop("tilt", None)
            flags.append("unsure_tilt")
    elif p.get("skew"):
        before = p["skew"]
        d, r, im, m2 = best_turn(before)
        if keep(d, r, im, before, m2) and not refused(d, m2):
            set_turn(d, r, im)
        else:
            p.pop("skew", None)
            if "tilt_disputed" not in flags:
                flags.append("unsure_tilt")
    elif mk0.get("xy") is not None and p.get("kind") == "text" and prof.deskew and texty(mk0, 300):
        u, g = skew_of(mk0["xy"], wide=prof.skew_max)
        if abs(u) >= 1.0 and mk0.get("level_frame"):
            u = 0.0
        if abs(u) >= prof.skew_min and g >= 1.02:
            if mk0["proj"](-3.0, 3.0, 0.25) < prof.skew_min - 0.05:
                flags.append("tilt_disputed")
                p["tilt"] = round(u, 3)
            else:
                tries = []
                for d0 in (-u, u):
                    m2 = lk.look(dict(p, skew=round(d0, 3)), px)
                    if m2["xy"] is None or not 0.6 <= _ink(m2) / max(1, _ink(mk0)) <= 5.0:
                        continue
                    tries.append((abs(skew_of(m2["xy"], raw=True)[0]), round(d0, 3)))
                done = False
                if tries:
                    d, r, im, m2 = best_turn(min(tries)[1])
                    if keep(d, r, im, u, m2) and not refused(d, m2):
                        set_turn(d, r, im)
                        p["tilt"] = round(-d, 3)
                        flags.append("found_in_check")
                        done = True
                if not done:
                    if "tilt_disputed" not in flags:
                        flags.append("untreated_tilt")
                    p["tilt"] = round(u, 3)
    # LINES AT TWO ANGLES: every turn is checked line by line on the page as scanned and as turned
    if p.get("skew") and prof.two_angle_guard:
        t0, t1 = mk0["tracks"](), lk.look(p, px)["tracks"]()
        L = lines_read(t0, t1, p["skew"])
        tw = two_angles(L)
        # (on a page turned by its column rule the lines have the last word: a rule set askew to its lines turns nothing)
        if tw and "by_columns" not in flags and print_turn(t0, t1, p["skew"])[0]:
            tw = []
            flags.append("level_by_print")
        if not tw:  # a printed rule the turn makes lean: the print refuses it
            tw = rules_made_to_lean(t0, t1, p["skew"])
        if tw:
            d0 = p.pop("skew")
            p.pop("after", None)
            m_ = round(round(float(np.median([v[1] for v in L])) / 0.025) * 0.025, 3) if L else 0.0
            L2, m2 = None, None
            # (a page with a rule between two columns is turned by that rule or not at all: no second turn by its lines)
            if abs(m_) >= prof.skew_min and "by_columns" not in flags:
                m2 = lk.look(dict(p, skew=m_), px)
                L2 = lines_read(t0, m2["tracks"](), m_)
            if L2 and m2 is not None and not two_angles(L2) and sum(1 for v in L2 if abs(v[2]) <= 0.2 + 1e-6) >= 0.8 * len(L2) \
                    and m2["xy"] is not None and abs(skew_of(m2["xy"], raw=True)[0]) <= 0.2 + 1e-6 \
                    and not rules_made_to_lean(t0, m2["tracks"](), m_):
                set_turn(m_, abs(skew_of(m2["xy"], raw=True)[0]), m2["proj"]())
                flags.append("level_by_tracks")
            else:
                for k in ("found_in_check", "by_columns"):
                    if k in flags:
                        flags.remove(k)
                flags.append("two_angles")
                p["two_angles"] = {"turn": d0, "lines": [list(v) for v in tw[:8]]}
    # THE PRINTED FRAME IS THE STANDARD OF TILT
    if p.get("kind") == "text" and mk0.get("text") is not None and mk0.get("rules") and prof.deskew:
        fl = frame_lean(mk0)
        sk0 = p.get("skew") or 0.0
        if fl is not None and abs(fl + sk0) > prof.frame_side_max + 1e-6:
            d = round(round(-fl / 0.025) * 0.025, 3) if abs(fl) >= prof.skew_min - 1e-6 else 0.0
            m2 = lk.look(dict(p, skew=d), px) if d else mk0
            f2 = frame_lean(m2)
            if f2 is not None and abs(f2) <= 0.2 + 1e-6:
                for k in ("two_angles", "unsure_tilt", "untreated_tilt", "tilt_disputed", "found_in_check", "curved",
                          "level_by_tracks"):
                    if k in flags:
                        flags.remove(k)
                p.pop("two_angles", None)
                p["frame"] = {"lean": fl, "was": round(sk0, 3), "after": f2}
                if d:
                    p["skew"] = d
                    p["tilt"] = round(-d, 3)
                else:
                    p.pop("skew", None)
                flags.append("frame_turn")
        cur = lk.look(p, px)
        fr = frame_shear(cur) if cur.get("text") is not None else None
        if fr is not None and prof.shear_min + 1e-6 < abs(fr[0]) <= prof.shear_max + 1e-6:
            d_ = round(round(-fr[0] / 0.025) * 0.025, 3)
            m3 = lk.look(dict(p, shear=d_), px)
            f3, s3 = frame_shear(m3), frame_lean(m3)
            if f3 is not None and abs(f3[0]) <= 0.2 + 1e-6 and s3 is not None and abs(s3) <= prof.frame_side_max + 1e-6:
                p["shear"] = d_
                p.setdefault("frame", {})["rules"] = [fr[1], fr[2]]
                flags.append("frame_shear")
    if p.get("skew") and "after" not in p:
        m2 = lk.look(p, px)
        if m2.get("xy") is not None:
            p["after"] = [round(abs(skew_of(m2["xy"], raw=True)[0]), 3), m2["proj"]()]


def measure_page(doc: pymupdf.Document, i: int, prof: Profile) -> dict:
    """the first and second look at page i -> its record, with the marks of its final view (at prof.first_px)"""
    lk = Looker(doc, i, prof.first_px)
    try:
        rec, mk0 = first_look(doc, i, prof, lk)
        if rec.get("kind") in ("rotated", "cover"):
            return rec
        if mk0["box"] is None:
            rec["kind"] = "blank" if mk0["dark"] < 0.5 else "picture"
        elif mk0["dark"] > 0.35:
            rec["kind"] = "picture"
        else:
            rec["kind"] = "text"
        if rec["kind"] == "text":
            second_look(doc, i, rec, prof, lk)
        final = {k: v for k, v in rec.items() if k in ("skew", "shear")}
        mk = lk.look(final, prof.first_px)
        if final:
            rec["bed"] = lk.bed()  # (for the second check of the box, which looks at the turned page alone)
            mk = dict(mk)
            _carry_bands(doc[i], rec, mk0, mk)
            if mk["box"] is None:  # the turned page lost its content: a broken drawing, never kept
                for k in ("skew", "shear"):
                    rec.pop(k, None)
                rec["flags"].append("turn_dropped")
                mk = mk0
        for k in KEEP_KEYS:
            if k in mk:
                rec[k] = mk[k]
        rec["parts_n"] = len(mk.get("parts") or [])
        if rec["kind"] == "text" and mk.get("box") is None:
            rec["kind"] = "blank"
        return rec
    finally:
        lk.close()


def to_recipe_page(rec: dict) -> dict:
    """the page record as stored in a recipe: boxes rounded, measuring internals dropped"""
    out = {}
    for k, v in rec.items():
        if k in ("box", "core", "text", "allowed", "crop", "show", "cover", "content_box", "need"):
            out[k] = rnd(v)
        elif k in ("blots", "edge", "lines", "rules", "rules_dropped", "notes", "figures", "cut_stray"):
            out[k] = [rnd(b) for b in v] if v else []
        elif k in ("specks", "margin"):
            out[k + "_n"] = len(v or [])
        elif k == "folio":
            out[k] = (rnd(v[:4]) + [v[4]]) if v else None
        elif k == "paper":
            out[k] = round(float(v))
        else:
            out[k] = v
    return out
