"""Whole-page questions: is it a cover on the scanner bed, a blank page, two book pages on one sheet?"""

from __future__ import annotations

import numpy as np
import pymupdf
from scipy import ndimage

from .measure import bands
from .pdf import gray, shown_as_computed


def cover_rect(page: pymupdf.Page, px: int = 360) -> list[float] | None:
    """A COVER photographed on the scanner bed or laid on a white sheet: the largest region whose colour differs from the
    page's outer ring (or a dark cloth cover the colour of the page's centre on a dark bed), trimmed to its solid rows and
    columns, when it fills 25-97 % of the page, is solid and of one piece, and nothing but the bed lies beside it (ink
    standing free beside it is print: a title page). -> its rectangle in pt (edges moved in past a rounded corner, <= 3 %)"""
    z = px / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csRGB, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width * 3] \
        .reshape(pix.height, pix.width, 3).astype(np.int16)
    H, W = a.shape[:2]
    r = max(2, int(0.03 * min(H, W)))
    ring = np.concatenate([a[:r].reshape(-1, 3), a[-r:].reshape(-1, 3), a[:, :r].reshape(-1, 3), a[:, -r:].reshape(-1, 3)])
    bg = np.median(ring, axis=0)
    diff = ndimage.binary_closing(np.abs(a - bg).max(axis=2) >= 45, iterations=2)
    cands = [diff]
    cc = np.median(a[int(0.35 * H):int(0.65 * H), int(0.35 * W):int(0.65 * W)].reshape(-1, 3), axis=0)
    paperish = cc.min() >= 160 and cc.max() - cc.min() < 40
    if np.abs(cc - bg).max() >= 12 and not paperish:
        same = np.sqrt(((a - cc) ** 2).sum(axis=2)) <= 55
        cands.append(ndimage.binary_fill_holes(ndimage.binary_closing(same, iterations=3)))
    for mask in cands:
        lab, n = ndimage.label(mask)
        if n == 0:
            continue
        big = int(np.argmax(np.bincount(lab.ravel())[1:])) + 1
        m = lab == big
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        sub = m[y0:y1, x0:x1]
        rows = np.nonzero(sub.mean(1) >= 0.6)[0]
        cols = np.nonzero(sub.mean(0) >= 0.6)[0]
        if len(rows) < 10 or len(cols) < 10:
            continue
        y0, y1, x0, x1 = y0 + rows[0], y0 + rows[-1] + 1, x0 + cols[0], x0 + cols[-1] + 1
        area = (y1 - y0) * (x1 - x0) / (H * W)
        if not 0.25 <= area <= 0.97 or m[y0:y1, x0:x1].mean() < 0.85:
            continue
        if m.sum() - m[y0:y1, x0:x1].sum() > 0.05 * m.sum():
            continue
        out = diff.copy()
        out[y0:y1, x0:x1] = False
        ol, k = ndimage.label(out)
        if k:
            border = set(np.unique(np.concatenate([ol[0], ol[-1], ol[:, 0], ol[:, -1]]))) - {0}
            sz = np.bincount(ol.ravel())
            small = [j for j in range(1, k + 1) if j not in border and sz[j] < 0.003 * H * W]
            if small and sz[small].sum() > 0.002 * H * W:
                continue
        y0_, y1_, x0_, x1_ = y0, y1, x0, x1
        my, mx = int(0.03 * (y1 - y0)) + 1, int(0.03 * (x1 - x0)) + 1
        for _ in range(max(my, mx)):
            moved = False
            if y1 - y0 > 10 and m[y0, x0:x1].mean() < 0.98 and y0 < y0_ + my:
                y0 += 1
                moved = True
            if y1 - y0 > 10 and m[y1 - 1, x0:x1].mean() < 0.98 and y1 > y1_ - my:
                y1 -= 1
                moved = True
            if x1 - x0 > 10 and m[y0:y1, x0].mean() < 0.98 and x0 < x0_ + mx:
                x0 += 1
                moved = True
            if x1 - x0 > 10 and m[y0:y1, x1 - 1].mean() < 0.98 and x1 > x1_ - mx:
                x1 -= 1
                moved = True
            if not moved:
                break
        return [round(x0 / z, 2), round(y0 / z, 2), round(x1 / z, 2), round(y1 / z, 2)]
    return None


def ink_share(page: pymupdf.Page, dpi: float = 40) -> float:
    """share of dark pixels in the central 90 % of the page at 40 dpi, read inside its scanner bands when it has any
    (a blank leaf on a dark bed is blank): a blank page reads below 0.001"""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), colorspace=pymupdf.csGRAY, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width].astype(int)
    r0, r1, c0, c1 = bands(a < min(128, float(np.percentile(a, 90)) - 60))
    if (r1 - r0) * (c1 - c0) >= 0.3 * a.size:  # (a page dark all over has no paper inside its bands)
        a = a[r0:r1, c0:c1]
    h, w = a.shape
    core = a[int(.05 * h):int(.95 * h), int(.05 * w):int(.95 * w)]
    paper = float(np.percentile(core, 90)) if core.size else 255.0
    return float((core < min(128, paper - 60)).mean()) if core.size else 0.0


def spread_gutter(page: pymupdf.Page, px: int = 500) -> float | None:
    """TWO BOOK PAGES ON ONE SHEET: on a sheet wider than 1.15 x its height, the gutter between its two pages -- the
    longest run of columns between 35 % and 65 % of the width where letter-sized marks leave at most 5 % of their fullest
    column's ink (rows 10-90 %). A sheet without such a run (a map, a table across both pages) is not split.
    -> the gutter's x in pt (page coordinates) or None. The paper is read inside the scan's dark border, if any."""
    r = page.rect
    if r.width <= 1.15 * r.height:
        return None
    a, z = gray(page, px)
    H, W = a.shape
    # paper is the light part of the sheet: microfilm spreads sit on a black field
    light = a[a > 100]
    if light.size < 0.2 * a.size:
        return None
    paper = float(np.percentile(light, 75))
    m = (a < paper - 50) & (a > 0)
    dark = a < 60
    colfield, rowfield = dark.mean(0), dark.mean(1)
    m &= ~((colfield > 0.6)[None, :] | (rowfield > 0.6)[:, None])
    lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
    if n == 0:
        return None
    ok = np.zeros(n + 1, bool)
    for k, sl in enumerate(ndimage.find_objects(lab), 1):
        hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        ok[k] = hh <= 0.04 * H and ww <= 0.05 * W
    letters = ok[lab]
    prof = ndimage.uniform_filter1d(letters[int(0.1 * H):int(0.9 * H)].sum(0).astype(float), max(3, int(0.01 * W)))
    if prof.max() <= 0:
        return None
    lo, hi = int(0.35 * W), int(0.65 * W)
    low = prof[lo:hi] <= 0.05 * prof.max()
    best, run = None, None
    for x in range(len(low) + 1):
        if x < len(low) and low[x]:
            run = x if run is None else run
        elif run is not None:
            if best is None or x - run > best[1] - best[0]:
                best = (run, x)
            run = None
    left, right = letters[:, :lo].sum(), letters[:, hi:].sum()
    if best and best[1] - best[0] >= 0.005 * W and min(left, right) >= 0.15 * max(1, left + right):
        return round((lo + (best[0] + best[1]) / 2) / z, 2)
    return None


def find_spreads(doc: pymupdf.Document, mode: str = "auto") -> dict[str, float]:
    """the sheets to split -> {page index: gutter x}. auto: a book where half the sheets or more are wide, and wrap-around
    covers (back, spine and front on one wide page among the first or last four pages)"""
    n = doc.page_count
    if mode == "never" or n == 0:
        return {}
    wide = [i for i in range(n) if doc[i].rect.width > 1.15 * doc[i].rect.height and shown_as_computed(doc[i])]
    spreads = mode == "always" or len(wide) >= 0.5 * n
    out: dict[str, float] = {}
    for i in wide:
        cover_zone = i < 4 or i >= n - 4
        if not spreads and not (cover_zone and doc[i].rect.width > 1.5 * doc[i].rect.height):
            continue
        g = spread_gutter(doc[i])
        if g is None and not spreads:
            g = round(doc[i].rect.width / 2, 2)
        if g is not None:
            out[str(i)] = g
    return out
