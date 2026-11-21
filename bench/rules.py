"""Readers of a page's tilt that owe nothing to safha's own measures: the judges of the head-to-head.

* A rule the printer set between two columns (or across the page) is the print's straightest line: on a level page it
  stands upright. Its lean says how far a real page is from level, before and after any tool has turned it.
* On a page drawn for the purpose, whose lines are known to be level or tilted by a known angle, the lean of the lines
  themselves is read by the oldest method there is, the projection profile, on any part of the page's height.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def rule_leans(a: np.ndarray, min_len: float = 0.25) -> dict[str, list[tuple[float, int, int]]]:
    """long thin straight marks of a gray page image -> {"v": [(angle, length px, x)], "h": [(angle, length px, y)]}.

    The angle is positive when the page's content is turned counter-clockwise (a turn of -angle squares it). A mark
    counts when it is at least ``min_len`` of the page long, at most 3 % of it thick and straight (rms <= 1.5 px)."""
    H, W = a.shape
    paper = float(np.percentile(a, 90))
    out: dict[str, list[tuple[float, int, int]]] = {"v": [], "h": []}
    if paper < 110:
        return out
    ink = a < paper - 60
    for key, m, full in (("v", ndimage.binary_opening(ink, structure=np.ones((max(8, int(0.04 * H)), 1), bool)), H),
                         ("h", ndimage.binary_opening(ink, structure=np.ones((1, max(8, int(0.04 * W))), bool)), W)):
        m = ndimage.binary_dilation(m, structure=np.ones((3, 3), bool))  # the pieces of one leaning rule joined
        lab, _ = ndimage.label(m, structure=np.ones((3, 3), bool))
        for k, sl in enumerate(ndimage.find_objects(lab), 1):
            hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            length, thick = (hh, ww) if key == "v" else (ww, hh)
            if length < min_len * full or thick > 0.03 * (W if key == "v" else H) + 4:
                continue
            ys, xs = np.nonzero(lab[sl] == k)
            t, u = (ys, xs) if key == "v" else (xs, ys)  # u as a function of t along the rule
            tt = np.unique(t)[:: max(1, len(np.unique(t)) // 400)]
            cu = np.array([u[t == v].mean() for v in tt])
            ct = tt.astype(float)
            if len(ct) < 20:
                continue
            f = np.polyfit(ct, cu, 1)
            res = np.abs(cu - np.polyval(f, ct))
            ok = res <= max(1.5, 2.5 * float(np.median(res)))
            if ok.sum() < 20:
                continue
            f = np.polyfit(ct[ok], cu[ok], 1)
            if float(np.sqrt(((cu[ok] - np.polyval(f, ct[ok])) ** 2).mean())) > 1.5:
                continue  # bent: no standard
            ang = float(np.degrees(np.arctan(f[0])))
            # rows grow downward: on a page turned counter-clockwise a level rule's right end is higher (slope < 0)
            # and an upright rule's foot lies further right (dx/dy > 0)
            pos = (sl[1].start + sl[1].stop) // 2 if key == "v" else (sl[0].start + sl[0].stop) // 2
            out[key].append((round(-ang if key == "h" else ang, 3), int(length), int(pos)))
    return out


def column_rule_lean(a: np.ndarray) -> float | None:
    """the lean of the page's column rule: the longest upright rule standing between 25 % and 75 % of the width and at
    least 35 % of the page tall, or None"""
    H, W = a.shape
    v = [r for r in rule_leans(a)["v"] if r[1] >= 0.35 * H and 0.25 * W <= r[2] <= 0.75 * W]
    return max(v, key=lambda r: r[1])[0] if v else None


def lines_lean(a: np.ndarray, top: float = 0.0, bottom: float = 1.0, widest: float = 5.0) -> float | None:
    """the lean of the lines of text in a gray page image, by the projection profile: the angle at which the rows of
    ink, sheared back, pile up sharpest (coarse steps of a quarter degree, then steps of 0.02).

    ``top``, ``bottom``: the part of the text's height that is read (0 at its first inked row, 1 at its last), so the
    upper and the lower lines of a page can be read apart. Edge rows and columns more than half dark (a scanner's
    bed, a film's black field) are left out. Positive when the page's content is turned counter-clockwise (a turn of
    minus the lean levels it). None when there is too little ink to tell."""
    paper = float(np.percentile(a, 90))
    if paper < 110:
        return None
    ink = a < paper - 60
    rows, cols = ink.mean(1), ink.mean(0)
    r0, r1, c0, c1 = 0, ink.shape[0], 0, ink.shape[1]
    while r0 < r1 and rows[r0] > 0.5:
        r0 += 1
    while r1 > r0 and rows[r1 - 1] > 0.5:
        r1 -= 1
    while c0 < c1 and cols[c0] > 0.5:
        c0 += 1
    while c1 > c0 and cols[c1 - 1] > 0.5:
        c1 -= 1
    ys, xs = np.nonzero(ink[r0:r1, c0:c1])
    if len(ys) < 2000:
        return None
    y0, y1 = np.percentile(ys, [1, 99])
    keep = (ys >= y0 + top * (y1 - y0)) & (ys <= y0 + bottom * (y1 - y0))
    xs, ys = xs[keep].astype(np.float64), ys[keep].astype(np.float64)
    if len(ys) < 1000:
        return None
    if len(ys) > 120000:
        pick = np.random.default_rng(0).choice(len(ys), 120000, replace=False)
        xs, ys = xs[pick], ys[pick]
    xs -= xs.mean()

    def sharpness(deg: float) -> float:
        yy = np.rint(ys + xs * np.tan(np.radians(deg))).astype(np.int64)
        c = np.bincount(yy - yy.min()).astype(np.float64)
        return float((c * c).sum())

    coarse = np.arange(-widest, widest + 1e-9, 0.25)
    best = float(coarse[int(np.argmax([sharpness(v) for v in coarse]))])
    fine = np.arange(best - 0.25, best + 0.25 + 1e-9, 0.02)
    score = np.array([sharpness(v) for v in fine])
    return round(float(np.median(fine[score >= 0.999 * score.max()])), 2) + 0.0  # (the middle of the sharpest angles)
