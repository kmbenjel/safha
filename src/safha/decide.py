"""DECIDE: one box size for the whole book, placed page by page on each page's text.

* Box size: the content width of 95 % of the typical text pages (else 98 %, else all) plus a margin of 8 % of it on
  each side (a hairline outside a printed frame; text + 6 % on every side for a book with nothing in its side margins);
  the tallest typical page plus 5 % above and below. Narrowed only as far as needed to centre the text on 95 % of pages.
* Box place: a full page is centred on its own text block (one centre for odd and even pages unless the book lays out by
  parity); a short page (a chapter end) keeps the place of its full neighbours, corrected by its own scan shift; a page
  whose marks do not fit there is centred on its own content. On white paper the content moves when the box would leave
  the page. The box slides away from a stain or a scan line beside the text when the content allows.
* A page whose content is wider than the box stays uncropped (shown whole, shrunk to the book's size by ``frames``).
* The book is cropped for a real gain or a flaw: the text grows >= 15 % on a phone, tilted pages, scanner bands, text
  off-centre or swaying from page to page, stains. Otherwise it is a good scan and stays as it is.
"""

from __future__ import annotations

from typing import Any

from .geometry import inside, quantile, union
from .measure import REF, figures_of, needed, notes_of
from .profile import Profile


def _same_place(a: list, b: list, w: float, h: float) -> bool:
    aw, ah, bw_, bh_ = a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1]
    return abs((a[0] + a[2]) - (b[0] + b[2])) / 2 <= 0.03 * w and abs((a[1] + a[3]) - (b[1] + b[3])) / 2 <= 0.03 * h \
        and 0.5 <= (aw + 1) / (bw_ + 1) <= 2 and 0.5 <= (ah + 1) / (bh_ + 1) <= 2


def decide(pages: list[dict], prof: Profile, wq: float = 0.95) -> dict[str, Any]:
    out: dict[str, Any] = {"pages": pages, "n": len(pages)}
    text = [i for i, p in enumerate(pages) if p["kind"] == "text"]
    out["measured"] = len(text)
    if len(text) < prof.min_text_pages or len(text) < 0.5 * len(pages):
        rot = sum(1 for p in pages if p["kind"] == "rotated")
        out["decision"] = "skip"
        out["why"] = f"few text pages ({len(text)} of {len(pages)})" \
            + (f"; {rot} pages are shown in a way that cannot be followed (their /Rotate entry or their boxes): such "
               "pages are shown whole, not measured" if rot else "")
        return out
    # a «stain» at the same place on 3 other pages or more is print (an ornament, a logo): content again
    allb = [(i, bl) for i in text for bl in pages[i].get("blots") or []]
    need_rep = max(3, int(0.03 * len(text)))
    for i, bl in allb:
        w, h = pages[i]["w"], pages[i]["h"]
        if sum(1 for j, c in allb if j != i and _same_place(bl, c, w, h)) >= need_rep:
            p = pages[i]
            p["blots"] = [b for b in p["blots"] if b is not bl]
            p["box"] = union([p["box"], bl])
    # PRINTED RULES AND FRAMES belong to the page when the book prints them: a rule on the same side of the text block at
    # the same distance (+- 2 % of the page) on >= 40 % of the text pages (at least 3), within 6 % of the page from the
    # text; a rule across the text block stays. Scan lines and print damage do not repeat.

    def rkey(i: int, r: list) -> tuple[str, float]:
        c = pages[i].get("core") or pages[i]["box"]
        w_, h_ = pages[i]["w"], pages[i]["h"]
        if r[3] - r[1] >= r[2] - r[0]:
            return ("L", (c[0] - r[2]) / w_) if r[2] <= c[0] else (("R", (r[0] - c[2]) / w_) if r[0] >= c[2] else ("I", 0.0))
        return ("T", (c[1] - r[3]) / h_) if r[3] <= c[1] else (("B", (r[1] - c[3]) / h_) if r[1] >= c[3] else ("I", 0.0))

    rk = {i: [(rkey(i, r), r) for r in pages[i].get("rules") or []] for i in text}
    allk = [k for i in text for k, _ in rk[i]]
    for i in text:
        kept = [r for k, r in rk[i] if k[0] == "I" or (k[1] <= 0.06 and sum(
            1 for k2 in allk if k2[0] == k[0] and abs(k2[1] - k[1]) <= 0.02) >= max(3, 0.4 * len(text)))]
        dropped = [r for k, r in rk[i] if not any(r is x for x in kept)]
        if dropped:
            pages[i]["rules_dropped"] = dropped
        pages[i]["rules"] = kept
        if kept:
            pages[i]["box"] = union([pages[i]["box"]] + kept)
    bw = {i: pages[i]["box"][2] - pages[i]["box"][0] for i in text}
    bh = {i: pages[i]["box"][3] - pages[i]["box"][1] for i in text}
    core = {i: pages[i].get("core") or pages[i]["box"] for i in text}
    cw = {i: core[i][2] - core[i][0] for i in text}
    pw = quantile([pages[i]["w"] for i in text], 0.5)
    ph = quantile([pages[i]["h"] for i in text], 0.5)
    # typical pages decide the size: a page > 25 % wider (15 % taller) than the median is not typical; it gets the book's
    # size all the same (its content shrunk to fit). Taller pages are left out of the height only when they are few.
    mw, mh = quantile(bw.values(), 0.5), quantile(bh.values(), 0.5)
    typ = [v for v in bh.values() if v <= 1.15 * mh]
    Tw = quantile([v for v in bw.values() if v <= 1.25 * mw] or list(bw.values()), wq)
    Th = quantile(typ, 1.0) if typ and len(bh) - len(typ) <= max(2, 0.1 * len(bh)) else quantile(list(bh.values()), 1.0)
    full_w = [i for i in text if cw[i] >= 0.9 * quantile(cw.values(), 0.5)]
    full_h = [i for i in text if bh[i] >= 0.9 * quantile(bh.values(), 0.5)]

    def framed(i: int) -> bool:
        c = core[i]
        rs = pages[i].get("rules") or []
        return any(r[2] <= c[0] for r in rs) and any(r[0] >= c[2] for r in rs)

    out["framed"] = sum(1 for i in full_w if framed(i)) >= 0.5 * max(1, len(full_w))
    m0 = prof.min_margin_pt * pw / REF
    if out["framed"]:
        W, H = Tw * (1 + 2 * prof.framed_margin), Th * (1 + 2 * prof.framed_margin)
    else:
        W, H = Tw + 2 * max(m0, prof.margin * Tw), Th + 2 * max(m0, prof.margin_v * Th)
    cx = {i: (core[i][0] + core[i][2]) / 2 for i in text}
    cy = {i: (pages[i]["box"][1] + pages[i]["box"][3]) / 2 for i in text}

    def lim(i: int) -> list:
        return pages[i].get("allowed") or [0, 0, pages[i]["w"], pages[i]["h"]]

    fitW = [2 * min(cx[i] - lim(i)[0], lim(i)[2] - cx[i]) for i in full_w]
    fitH = [2 * min(cy[i] - lim(i)[1], lim(i)[3] - cy[i]) for i in full_h]
    W = min(W, max(Tw, quantile(fitW, 0.05)) if fitW else W, pw)
    H = min(H, max(Th, quantile(fitH, 0.05)) if fitH else H, ph)
    # odd and even pages: one horizontal centre by default; one per parity only when the book lays out like that
    # (marginal material on a fixed side, odd pages one way and even pages the other)
    off = {0: 0.0, 1: 0.0}
    ext = {i: (needed(pages[i])[0] + needed(pages[i])[2]) / 2 - cx[i] for i in full_w}
    for par in (0, 1):
        v = [ext[i] for i in full_w if i % 2 == par]
        if len(v) >= 10:
            med = quantile(v, 0.5)
            same = sum(1 for x in v if x * med > 0 and abs(x) >= 0.005 * pw) / len(v)
            if abs(med) >= 0.015 * pw and same >= 0.7:
                off[par] = med
    if off[0] or off[1]:
        def carries(i: int) -> bool:
            o = off[i % 2]
            nb = needed(pages[i])
            t_ = pages[i].get("text") or pages[i]["box"]
            return (o > 0 and nb[2] - t_[2] >= 0.015 * pw) or (o < 0 and t_[0] - nb[0] >= 0.015 * pw)

        cx = {i: v + (off[i % 2] if carries(i) else 0.0) for i, v in cx.items()}
        fitW = [2 * min(cx[i] - lim(i)[0], lim(i)[2] - cx[i]) for i in full_w]
        base_w = Tw * (1 + 2 * prof.framed_margin) if out["framed"] else Tw + 2 * max(m0, prof.margin * Tw)
        W = min(base_w, max(Tw, quantile(fitW, 0.05)) if fitW else base_w, pw)
    out["parity_offsets"] = [round(off[0], 1), round(off[1], 1)]
    tb = {i: pages[i].get("text") for i in text}

    def marg_print(i: int) -> bool:
        w, h = pages[i]["w"], pages[i]["h"]

        def printish(b: list) -> bool:
            bw_, bh_ = b[2] - b[0], b[3] - b[1]
            edge = b[2] <= 0.03 * w or b[0] >= 0.97 * w or b[3] <= 0.03 * h or b[1] >= 0.97 * h
            sliver = (bw_ <= 0.006 * w and bh_ >= 4 * bw_) or (bh_ <= 0.006 * h and bw_ >= 4 * bh_)
            return not edge and not sliver and bh_ < 0.15 * h and (bh_ >= 0.008 * h or bw_ >= 0.015 * w)

        return sum(1 for b in pages[i].get("margin") or [] if printish(b)) >= 2

    # A BOOK WITHOUT PRINT IN ITS SIDE MARGINS: the box is the text block + clean_margin on every side, centred on each
    # page's text block; what lies in the side margins is cut, except marginal notes and figures (kept whole)
    clean = (not out["framed"]) and len(full_w) >= 5 and all(tb.get(i) for i in full_w) \
        and sum(1 for i in full_w if marg_print(i)) <= 0.10 * len(full_w)
    out["clean_margins"] = clean
    mc = 0.0
    out["margin_pt"] = round(prof.framed_margin * Tw if out["framed"] else max(m0, prof.margin * Tw), 2)
    edges = {i: core[i] for i in text}
    if clean:
        off = {0: 0.0, 1: 0.0}
        out["parity_offsets"] = [0.0, 0.0]
        tw = {i: tb[i][2] - tb[i][0] for i in text if tb.get(i)}
        th = {i: tb[i][3] - tb[i][1] for i in text if tb.get(i)}
        full_t = [i for i in full_w if i in tw]
        mt = quantile([tw[i] for i in full_t], 0.5)
        Tq = quantile([tw[i] for i in full_t if tw[i] <= 1.25 * mt] or [tw[i] for i in full_t], wq)
        mc = prof.clean_margin * Tq
        out["margin_pt"] = round(mc, 2)
        W = min(Tq + 2 * mc, pw)
        th_ = [th[i] for i in full_h if i in th] or list(th.values())
        mth = quantile(th_, 0.5)
        H = min(quantile([v for v in th_ if v <= 1.15 * mth] or th_, 0.98) + 2 * mc, ph)
        cx = {i: ((tb[i][0] + tb[i][2]) / 2 if tb.get(i) else cx[i]) for i in text}
        cy = {i: ((tb[i][1] + tb[i][3]) / 2 if tb.get(i) else cy[i]) for i in text}
        edges = {i: tb[i] for i in text if tb.get(i)}
        for i in text:
            if tb.get(i):
                mg = pages[i].get("margin") or []
                nts = notes_of(mg, pages[i]["w"], pages[i]["h"])
                figs = figures_of(mg, pages[i]["w"], pages[i]["h"])
                pages[i]["content_box"] = pages[i]["box"]
                pages[i]["box"] = union([tb[i]] + nts + figs)
                if nts:
                    pages[i]["notes"] = nts
                if figs:
                    pages[i]["figures"] = figs

    def near(i: int, pool: list[int], val: dict) -> float:
        same = [j for j in pool if j % 2 == i % 2] or pool
        k = sorted(same, key=lambda j: abs(j - i))[:6]
        return quantile([val[j] for j in k], 0.5)

    fw, fh = set(full_w), set(full_h)
    EL = {i: edges[i][0] for i in edges}
    ER = {i: edges[i][2] for i in edges}
    ET = {i: edges[i][1] for i in edges}
    EB = {i: edges[i][3] for i in edges}

    def shift(d0: float, d1: float, tol: float) -> float | None:
        c = [d for d in (d0, d1) if abs(d) <= tol]
        return min(c, key=abs) if c else None

    fwe = [j for j in full_w if j in edges]
    fhe = [j for j in full_h if j in edges]
    whole: list[int] = []
    offc: list[float] = []
    own = moved = 0
    for i, p in enumerate(pages):
        if p["kind"] == "cover":
            p["crop"] = p["cover"]
            continue
        if p["kind"] in ("rotated", "picture", "blank"):
            p["crop"] = None
            continue
        bx = p.get("box")
        e = edges.get(i)
        x = cx[i] if i in fw else (near(i, full_w, cx) if full_w else pw / 2)
        y = cy[i] if i in fh else (near(i, full_h, cy) if full_h else ph / 2)
        if e and i not in fw and fwe:  # a short page: where its neighbours' lines are, corrected by its own shift
            dx_ = shift(e[0] - near(i, fwe, EL), e[2] - near(i, fwe, ER), 0.03 * p["w"])
            if dx_ is not None:
                x += dx_
            else:
                x = cx[i]  # centred lines (a title page, a poem): on themselves
        if e and i not in fh and fhe:
            dy_ = shift(e[1] - near(i, fhe, ET), e[3] - near(i, fhe, EB), 0.03 * p["h"])
            if dy_:
                y += dy_
        if bx and i not in fw and (bx[2] - bx[0]) < 0.75 * Tw:
            x = (bx[0] + bx[2]) / 2
        if e and bx and i not in fh and fhe and e[1] - near(i, fhe, ET) >= 0.15 * p["h"]:
            x, y = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        if bx:
            b = [x - W / 2, y - H / 2, x + W / 2, y + H / 2]
            dx = bx[0] - b[0] if bx[0] < b[0] else (bx[2] - b[2] if bx[2] > b[2] else 0)
            dy = bx[1] - b[1] if bx[1] < b[1] else (bx[3] - b[3] if bx[3] > b[3] else 0)
            if (dx or dy) and not clean and p.get("text"):  # stray marks far from the text are not laid out: cut them
                nd = needed(p)
                if nd and inside(nd, bx, 1.0) and not inside(bx, nd, 1.0):
                    p["cut_stray"] = [m for m in (p.get("margin") or []) if not inside(m, nd, 1.0)]
                    p["content_box"] = bx
                    p["box"] = bx = nd
                    dx = bx[0] - b[0] if bx[0] < b[0] else (bx[2] - b[2] if bx[2] > b[2] else 0)
                    dy = bx[1] - b[1] if bx[1] < b[1] else (bx[3] - b[3] if bx[3] > b[3] else 0)
            if dx or dy:
                if dx:
                    x = (bx[0] + bx[2]) / 2
                if dy:
                    y = (bx[1] + bx[3]) / 2
                p["flags"].append("own_centre")
                own += 1
        b = [x - W / 2, y - H / 2, x + W / 2, y + H / 2]
        sx = -b[0] if b[0] < 0 else (p["w"] - b[2] if b[2] > p["w"] else 0)
        sy = -b[1] if b[1] < 0 else (p["h"] - b[3] if b[3] > p["h"] else 0)
        al_ = p.get("allowed") or [0, 0, p["w"], p["h"]]
        open_side = (sx <= 0 or al_[0] <= 0.5) and (sx >= 0 or al_[2] >= p["w"] - 0.5) \
            and (sy <= 0 or al_[1] <= 0.5) and (sy >= 0 or al_[3] >= p["h"] - 0.5)
        if (sx or sy) and bx and p.get("paper", 0) >= 235 and open_side:
            nb = [bx[0] + sx, bx[1] + sy, bx[2] + sx, bx[3] + sy]
            if nb[0] >= 0 and nb[1] >= 0 and nb[2] <= p["w"] and nb[3] <= p["h"]:  # on white paper the content moves
                p["move"] = [round(sx, 1), round(sy, 1)]
                moved += 1
                p["box"] = bx = nb
                for k in ("blots", "edge", "lines", "text"):
                    if p.get(k):
                        p[k] = [[v[0] + sx, v[1] + sy, v[2] + sx, v[3] + sy] for v in p[k]] if k != "text" else \
                            [p[k][0] + sx, p[k][1] + sy, p[k][2] + sx, p[k][3] + sy]
        b = [b[0] + sx, b[1] + sy, b[2] + sx, b[3] + sy]
        # dodge a stain or a line beside the text: slide the box away from it, as far as the content and the page allow
        tbx = p.get("text") or bx
        avoid = (p.get("blots") or []) + [ln for ln in (p.get("lines") or []) if tbx and not inside(ln, tbx, 1.0)]
        pxm, pym = 0.006 * p["w"], 0.006 * p["h"]
        avoid = [[v[0] - pxm, v[1] - pym, v[2] + pxm, v[3] + pym] for v in avoid]
        if bx and avoid:
            for ax in (0, 1):
                k0, k1, size = (0, 2, p["w"]) if ax == 0 else (1, 3, p["h"])
                span = b[k1] - b[k0]
                lo, hi = max(0, bx[k1] - span), min(bx[k0], size - span)
                for bl in avoid:
                    if not (bl[2] > b[0] and bl[0] < b[2] and bl[3] > b[1] and bl[1] < b[3]):
                        continue
                    nx = bl[k1] + 2 if bl[k1] <= bx[k0] else (bl[k0] - 2 - span if bl[k0] >= bx[k1] else None)
                    if nx is None or lo > hi:
                        continue
                    cand = min(max(nx, lo), hi)
                    ml, mr = bx[k0] - cand, cand + span - bx[k1]
                    if min(ml, mr) < (0.6 if ax == 0 else 0.35) * max(ml, mr):
                        continue  # the text would sit too far off-centre: the stain stays in view
                    b[k0], b[k1] = cand, cand + span
                    if "dodged" not in p["flags"]:
                        p["flags"].append("dodged")
        b = [round(max(0, b[0]), 2), round(max(0, b[1]), 2), round(min(p["w"], b[2]), 2), round(min(p["h"], b[3]), 2)]
        hm = 0.5 * mc
        if clean and bx and not inside([bx[0] - hm, bx[1] - hm, bx[2] + hm, bx[3] + hm], b):
            sc = max(1.0, (bx[2] - bx[0] + 2 * mc) / W, (bx[3] - bx[1] + 2 * mc) / H)  # grows with the same proportions
            smax = min(p["w"] / W, p["h"] / H)
            if sc > smax:
                sc = max(1.0, smax, (bx[2] - bx[0]) / W, (bx[3] - bx[1]) / H)
            W2, H2 = W * sc, H * sc
            x2, y2 = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            b = [x2 - W2 / 2, y2 - H2 / 2, x2 + W2 / 2, y2 + H2 / 2]
            sx = -b[0] if b[0] < 0 else (p["w"] - b[2] if b[2] > p["w"] else 0)
            sy = -b[1] if b[1] < 0 else (p["h"] - b[3] if b[3] > p["h"] else 0)
            b = [round(max(0, b[0] + sx), 2), round(max(0, b[1] + sy), 2), round(min(p["w"], b[2] + sx), 2),
                 round(min(p["h"], b[3] + sy), 2)]
            if sc > 1.0001:
                p["enlarged"] = round(sc, 3)
        if bx and not inside(bx, b):
            p["crop"] = None
            p["flags"].append("whole")
            whole.append(i)
            continue
        p["crop"] = b
        if i in fw and bx:
            mv = p.get("move") or [0, 0]
            offc.append(abs((b[0] + b[2]) / 2 - (cx[i] + mv[0])) / p["w"])
    out["whole"] = whole
    out["own_centre"] = own
    out["content_moved"] = moved
    out["size"] = [round(W, 2), round(H, 2)]
    out["gain"] = round(pw / W, 3)
    out["gain_h"] = round(ph / H, 3)
    out["offcentre"] = round(quantile([abs(cx[i] - pages[i]["w"] / 2) / pages[i]["w"] for i in full_w], 0.5), 3) \
        if full_w else 0.0
    banded = sum(1 for i in text if lim(i)[0] > 0.02 * pw or lim(i)[2] < 0.98 * pages[i]["w"]) > 0.5 * len(text)
    out["banded"] = banded

    def iqr(v: list) -> float:
        v = sorted(v)
        return v[int(0.75 * (len(v) - 1))] - v[int(0.25 * (len(v) - 1))] if v else 0.0

    out["sway"] = [round(iqr([(edges[i][0] + edges[i][2]) / 2 / pages[i]["w"] for i in fwe]), 4),
                   round(iqr([(edges[i][1] + edges[i][3]) / 2 / pages[i]["h"] for i in fhe]), 4)]
    skewed = sum(1 for p in pages if p.get("skew") or p.get("shear"))
    blot_pages = sum(1 for p in pages if p.get("crop") and p.get("blots"))
    reasons = []
    if out["gain"] >= prof.gain_min:
        reasons.append(f"text {round((out['gain'] - 1) * 100)} % larger")
    if skewed:
        reasons.append(f"{skewed} tilted pages")
    if banded:
        reasons.append("scanner bands")
    if out["offcentre"] >= prof.offcentre:
        reasons.append(f"text off-centre {round(out['offcentre'] * 100, 1)} %")
    if max(out["sway"]) >= prof.sway:
        reasons.append(f"text sways {round(max(out['sway']) * 100, 1)} %")
    if blot_pages >= prof.stained * len(text):
        reasons.append(f"stains on {blot_pages} pages")
    out["reasons"] = reasons
    if len(whole) > prof.max_whole * len(text):
        out["decision"] = "skip"
        out["why"] = f"{len(whole)} pages do not fit one box"
    elif not reasons and not prof.always:
        out["decision"] = "skip"
        out["why"] = f"a good scan: the crop changes little (text {round((out['gain'] - 1) * 100)} % larger)"
    elif reasons and all(r.endswith("tilted pages") for r in reasons) and not prof.always:
        out["decision"] = "level"
    else:
        out["decision"] = "crop"
    return out
