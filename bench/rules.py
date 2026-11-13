"""Printed rules as the truth for a page's tilt.

A rule the printer set between two columns (or across the page) is the print's straightest line: on a level page it
stands upright. Its lean, read here independently of safha's own measures, says how far a page is from level, before
and after any tool has turned it.
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
