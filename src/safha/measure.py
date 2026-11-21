"""The page measure: every ink mark of a rendered page, sorted into content and not-content.

Sizes are shares of the page, or "reference pt" (pt on a page scaled to 420 pt wide). The rules, in order:

* paper = 90th percentile of the grey levels; ink = darker than paper - 50; marks = 8-connected components.
* NOT content (left outside the box): scanner bands (rows/columns at an edge more than 60 % dark); edge shadows (a mark
  touching a side, long along it, thin across it); isolated specks; dust (groups of specks outside the text block); the
  sheet's border zone of a photocopy (ink at the edge followed by a clear gap); scanner edge noise; corner marks; streaks
  (tall ragged marks along a side) and blots (solid irregular marks alone in a margin); thin lines and dashed or dotted
  lines beside the text (scan lines and print damage; a printed rule comes back in ``decide`` when the book repeats it).
* Everything else is content, however small or faint.
* The text block is measured mark by mark (2nd-98th percentile of the marks' edges), then widened by gaps: every
  letter-like mark less than 1.5 % of the width away joins it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import ndimage
from scipy.sparse.csgraph import connected_components

from .geometry import inside, thin_line, union

REF = 420.0  # the page width (pt) the sizes in pt refer to
M = 14.0  # pt: isolation distance of a speck, and the least margin
SPECK = 4.0  # pt: a speck is at most SPECK x SPECK


def bands(mask: np.ndarray) -> tuple[int, int, int, int]:
    """rows/columns at the edges more than 60 % dark (scanner bed, black borders) -> the allowed area [r0, r1) x [c0, c1)"""
    rows, cols = mask.mean(1), mask.mean(0)

    def trim(a: np.ndarray) -> tuple[int, int]:
        i, j = 0, len(a)
        while i < j and a[i] > 0.6:
            i += 1
        while j > i and a[j - 1] > 0.6:
            j -= 1
        if 0 < i < j and a[i] > 0.3:  # the blurred edge of a band
            i += 1
        if j < len(a) and j > i and a[j - 1] > 0.3:
            j -= 1
        return i, j

    (r0, r1), (c0, c1) = trim(rows), trim(cols)
    return r0, r1, c0, c1


def marks(a: np.ndarray, scale: float, width: float, exclude: list | None = None,
          void: np.ndarray | None = None) -> dict[str, Any]:
    """ink marks of one page in pt (page coordinates) -> dict with

    box      every content mark;  core  the text block (2-98 % of the content ink: where the page is centred);
    text     the text block widened by gaps;  margin  content marks outside it;  folio  the page number line, if any;
    specks   isolated specks and dust;  blots  stains and edge streaks;  edge  scanner edge noise and sheet edges;
    lines    thin lines and dashed lines (not content here);  rules  faint printed rules and frames beside the text;
    allowed  where the box may go (inside scanner bands and edge shadows);  dark  share of dark pixels;
    xy       content ink pixels, thin lines included (for the tilt measures);  xy_text  the same without the lines;
    parts    every content mark's box.

    ``scale`` = pixels per pt, ``width`` = page width in pt; ``exclude``: boxes (pt) whitened before measuring;
    ``void``: the pixels of a turned view that lie beyond the scan's sheet, on the sides where the scan ends in a
    scanner band: nothing is drawn there, but the bed went on, so for the bands (and only for them) they are dark.
    Without them the blank wedge a turn leaves at the page's edge hides the band behind it, and the whole bed is taken
    for content."""
    if exclude:
        a = a.copy()
        for b in exclude:
            a[max(0, int(b[1] * scale)):int(b[3] * scale) + 1, max(0, int(b[0] * scale)):int(b[2] * scale) + 1] = 255
    unit = scale * width / REF
    out: dict[str, Any] = {"box": None, "core": None, "text": None, "specks": [], "blots": [], "edge": [], "rules": [],
                           "lines": [], "margin": [], "folio": None, "allowed": None, "dark": 1.0, "xy": None,
                           "xy_text": None, "parts": [], "level_frame": False}
    paper = float(np.percentile(a, 90))
    out["paper"] = paper
    if paper < 110:
        return out
    mask = a < paper - 50
    out["dark"] = float(mask.mean())
    r0, r1, c0, c1 = bands(mask if void is None else mask | void)
    m = mask[r0:r1, c0:c1]
    if m.size >= 0.3 * mask.size:  # a page on a black field (microfilm, scanner bed): dark share inside the bands
        out["dark"] = float(m.mean())
    allowed = [c0 / scale, r0 / scale, c1 / scale, r1 / scale]
    out["allowed"] = allowed
    out["bands"] = list(allowed)
    if m.size == 0:
        return out
    lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
    if n == 0:
        return out
    objs = ndimage.find_objects(lab)
    area = np.bincount(lab.ravel(), minlength=n + 1)
    H, Wd = m.shape
    hgt = np.array([0] + [s[0].stop - s[0].start for s in objs])
    wid = np.array([0] + [s[1].stop - s[1].start for s in objs])
    X0 = np.array([0] + [s[1].start for s in objs])
    X1 = np.array([0] + [s[1].stop for s in objs])
    Y0 = np.array([0] + [s[0].start for s in objs])
    Y1 = np.array([0] + [s[0].stop for s in objs])
    sp = SPECK * unit
    small = (hgt <= sp) & (wid <= sp)
    small[0] = False
    # marks closer than M to each other fall in one group
    k_ = max(1, int(M * unit / 2))  # (k dilations by 3 x 3 = one by a (2k+1) square: separable, fast)
    grp, _ = ndimage.label(ndimage.maximum_filter(m, size=2 * k_ + 1), structure=np.ones((3, 3), bool))
    gid = np.zeros(n + 1, np.int64)
    gid[lab[m]] = grp[m]
    members: dict[int, list[int]] = {}
    for i in range(1, n + 1):
        members.setdefault(int(gid[i]), []).append(i)
    isolated = {ids[0] for ids in members.values() if len(ids) == 1 and small[ids[0]]}
    # edge shadows: touching a side, long along it, thin across it; the box keeps out of them
    shadow = {i for i in range(1, n + 1)
              if ((X0[i] <= 1 or X1[i] >= Wd - 1) and hgt[i] >= 0.4 * H and wid[i] <= 0.06 * Wd)
              or ((Y0[i] <= 1 or Y1[i] >= H - 1) and wid[i] >= 0.4 * Wd and hgt[i] <= 0.06 * H)}
    for i in shadow:
        if X0[i] <= 1 and hgt[i] >= 0.4 * H:
            allowed[0] = max(allowed[0], (X1[i] + c0) / scale)
        elif X1[i] >= Wd - 1 and hgt[i] >= 0.4 * H:
            allowed[2] = min(allowed[2], (X0[i] + c0) / scale)
        elif Y0[i] <= 1:
            allowed[1] = max(allowed[1], (Y1[i] + r0) / scale)
        else:
            allowed[3] = min(allowed[3], (Y0[i] + r0) / scale)
    pre = [i for i in range(1, n + 1) if i not in isolated and i not in shadow]

    def pt(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        return [(x0 + c0) / scale, (y0 + r0) / scale, (x1 + c0) / scale, (y1 + r0) / scale]

    def box_of(i: int) -> list[float]:
        return pt(X0[i], Y0[i], X1[i], Y1[i])

    out["specks"] = [box_of(i) for i in sorted(isolated)]
    # marks lying in a scanner band (centre beyond the allowed area by more than 1 %) are the band, not the page
    lim = [allowed[0] * scale - c0 - 0.01 * Wd, allowed[1] * scale - r0 - 0.01 * H,
           allowed[2] * scale - c0 + 0.01 * Wd, allowed[3] * scale - r0 + 0.01 * H]
    inband = {i for i in pre if not (lim[0] <= (X0[i] + X1[i]) / 2 <= lim[2] and lim[1] <= (Y0[i] + Y1[i]) / 2 <= lim[3])}
    if inband and len(inband) < 0.3 * len(pre):
        out["edge"] += [box_of(i) for i in sorted(inband)]
        pre = [i for i in pre if i not in inband]
    if not pre:
        return out
    # THE SHEET'S BORDER ZONE of a photocopy: from each side inward, ink at the sheet's edge (outer 4 %) followed, within
    # 12 % of the side, by a clear gap (2 % of the width almost without ink): what lies wholly inside is the sheet's edge
    # (the photographed edges of other leaves, copier bars). A printed frame never touches the edge; text that runs to
    # the edge leaves no gap.

    def zone(cov: np.ndarray, nn: int, limit: float, gap: int) -> int:
        if cov[:max(1, int(0.04 * nn))].max() < 0.05:
            return 0
        last, run = -1, 0
        for k in range(min(nn, int(limit * nn))):
            if cov[k] >= 0.02:
                last, run = k, 0
            else:
                run += 1
                if run >= gap and last >= 0:
                    return last + 1
        return 0

    gpx = max(2, int(0.02 * Wd))
    zl = zr = zt = zb = 0
    for _ in range(2):
        colcov = m[zt:H - zb].mean(0)
        zl, zr = zone(colcov, Wd, 0.12, gpx), zone(colcov[::-1], Wd, 0.12, gpx)
        rowcov = m[:, zl:Wd - zr].mean(1)
        zt, zb = zone(rowcov, H, 0.10, gpx), zone(rowcov[::-1], H, 0.10, gpx)
    if zl or zr or zt or zb:
        Z = np.zeros((H, Wd), bool)
        if zl:
            Z[:, :zl] = True
        if zr:
            Z[:, Wd - zr:] = True
        if zt:
            Z[:zt, :] = True
        if zb:
            Z[H - zb:, :] = True
        zoned = set()
        for i in pre:
            sl = objs[i - 1]
            if Z[sl].any() and np.count_nonzero((lab[sl] == i) & Z[sl]) >= 0.9 * area[i]:
                zoned.add(i)
        if zoned and len(zoned) < len(pre):
            out["edge"] += [box_of(i) for i in sorted(zoned)]
            pre = [i for i in pre if i not in zoned]
    # a blank page showing only the edges of the sheet: every mark lies in the outer 8 % of a side
    if all(small[i] or X1[i] <= 0.08 * Wd or X0[i] >= 0.92 * Wd or Y1[i] <= 0.08 * H or Y0[i] >= 0.92 * H for i in pre):
        out["edge"] += [box_of(i) for i in pre]
        return out

    def in_strip(i: int) -> bool:
        return X1[i] <= 0.03 * Wd or X0[i] >= 0.97 * Wd or Y1[i] <= 0.03 * H or Y0[i] >= 0.97 * H

    def block(ids: list[int], lo: float = 2, hi: float = 98) -> tuple[float, float, float, float]:
        return (float(np.percentile(X0[ids], lo)), float(np.percentile(X1[ids], hi)),
                float(np.percentile(Y0[ids], lo)), float(np.percentile(Y1[ids], hi)))

    big = [i for i in pre if not small[i] and not in_strip(i)] or [i for i in pre if not small[i]] or pre
    cx0, cx1, cy0, cy1 = block(big)
    edge: set[int] = set()
    # the photocopied sheet's border in pieces: the text block measured without the outer 6 %; a mark wholly in that
    # outer 6 %, at most 4 % thick and at least 5 % of the width away from the text block is the sheet's edge
    inner = [i for i in pre if not small[i] and not (X1[i] <= 0.06 * Wd or X0[i] >= 0.94 * Wd or Y1[i] <= 0.06 * H
                                                     or Y0[i] >= 0.94 * H)]
    if inner:
        ex0, ex1, ey0, ey1 = block(inner)
        for i in pre:
            x0, x1, y0, y1 = X0[i], X1[i], Y0[i], Y1[i]
            if (x1 <= 0.06 * Wd and wid[i] <= 0.04 * Wd and ex0 - x1 >= 0.05 * Wd) \
                    or (x0 >= 0.94 * Wd and wid[i] <= 0.04 * Wd and x0 - ex1 >= 0.05 * Wd) \
                    or (y1 <= 0.06 * H and hgt[i] <= 0.04 * H and ey0 - y1 >= 0.05 * Wd) \
                    or (y0 >= 0.94 * H and hgt[i] <= 0.04 * H and y0 - ey1 >= 0.05 * Wd):
                edge.add(i)
    # a tilted edge of the sheet: from the border, along half the side or more, thin on average, sparse in its box
    for i in pre:
        fill = area[i] / max(1, hgt[i] * wid[i])
        if (wid[i] >= 0.5 * Wd and (Y0[i] <= 0.03 * H or Y1[i] >= 0.97 * H) and area[i] / wid[i] <= 0.03 * H and fill < 0.5) \
                or (hgt[i] >= 0.5 * H and (X0[i] <= 0.03 * Wd or X1[i] >= 0.97 * Wd) and area[i] / hgt[i] <= 0.03 * Wd
                    and fill < 0.5):
            edge.add(i)
    for i in pre:
        if i in edge:
            continue
        x0, x1, y0, y1 = X0[i], X1[i], Y0[i], Y1[i]
        # scanner edge noise in the outer 3 % of a side the text block is at least 5 % away from
        noise = (x1 <= 0.03 * Wd and wid[i] <= 0.02 * Wd and cx0 >= 0.05 * Wd) \
            or (x0 >= 0.97 * Wd and wid[i] <= 0.02 * Wd and Wd - cx1 >= 0.05 * Wd) \
            or (y1 <= 0.03 * H and hgt[i] <= 0.02 * H and cy0 >= 0.05 * H) \
            or (y0 >= 0.97 * H and hgt[i] <= 0.02 * H and H - cy1 >= 0.05 * H)
        # a scanner mark in a corner of the sheet, outside the text block
        corner = (x0 <= 0.01 * Wd or x1 >= 0.99 * Wd or y0 <= 0.01 * H or y1 >= 0.99 * H) \
            and wid[i] <= 0.05 * Wd and hgt[i] <= 0.05 * H \
            and (x0 <= 0.04 * Wd or x1 >= 0.96 * Wd) and (y0 <= 0.04 * H or y1 >= 0.96 * H) \
            and (x1 <= cx0 or x0 >= cx1 or y1 <= cy0 or y0 >= cy1)
        # a long line or copier bar within 6 % of a side, at least 5 % of the width away from the text block
        bar = (hgt[i] >= 0.3 * H and wid[i] <= 0.04 * Wd
               and ((x1 <= 0.06 * Wd and cx0 - x1 >= 0.05 * Wd) or (x0 >= 0.94 * Wd and x0 - cx1 >= 0.05 * Wd))) \
            or (wid[i] >= 0.3 * Wd and hgt[i] <= 0.04 * H
                and ((y1 <= 0.06 * H and cy0 - y1 >= 0.05 * Wd) or (y0 >= 0.94 * H and y0 - cy1 >= 0.05 * Wd)))
        if noise or corner or bar:
            edge.add(i)
        # the edge of the sheet: a thin sparse line touching the border, its ink almost all outside the text block
        elif (x0 <= 0.01 * Wd or x1 >= 0.99 * Wd or y0 <= 0.01 * H or y1 >= 0.99 * H) \
                and area[i] / max(1, hgt[i] * wid[i]) < 0.08:
            if np.count_nonzero(lab[int(cy0):int(cy1), int(cx0):int(cx1)] == i) < 0.1 * area[i]:
                edge.add(i)
    out["edge"] += [box_of(i) for i in sorted(edge)]
    big = [i for i in pre if i not in edge and not small[i]] or [i for i in pre if i not in edge] or pre
    cx0, cx1, cy0, cy1 = block(big)
    # dust: a group made only of specks, wholly outside the text block (unless it forms a long thin line: a chain rule)
    g1 = 0.01 * Wd
    dust: set[int] = set()
    for ids in members.values():
        if len(ids) > 1 and all(small[j] for j in ids):
            gx0, gx1 = min(X0[j] for j in ids), max(X1[j] for j in ids)
            gy0, gy1 = min(Y0[j] for j in ids), max(Y1[j] for j in ids)
            if (gy1 - gy0 >= 0.2 * H and gx1 - gx0 <= 0.03 * Wd) or (gx1 - gx0 >= 0.2 * Wd and gy1 - gy0 <= 0.03 * H):
                continue
            if gx1 <= cx0 - g1 or gx0 >= cx1 + g1 or gy1 <= cy0 - g1 or gy0 >= cy1 + g1:
                dust.update(ids)
    out["specks"] += [box_of(i) for i in sorted(dust) if i not in isolated]
    pre = [i for i in pre if i not in edge and i not in dust]
    if not pre:
        return out
    g, gap = 0.01 * Wd, M * unit
    blots: set[int] = set()
    for i in pre:
        x0, x1, y0, y1 = X0[i], X1[i], Y0[i], Y1[i]
        fill = area[i] / max(1, hgt[i] * wid[i])
        side = x1 <= cx0 - g or x0 >= cx1 + g
        # (a) a streak along a side (torn edge, binding shadow): tall, ragged, beyond the text block, near the edge
        if side and hgt[i] >= 0.25 * H and 0.006 * Wd <= wid[i] <= 0.06 * Wd and fill < 0.85 \
                and (x0 < 0.15 * Wd or x1 > 0.85 * Wd):
            blots.add(i)
            continue
        # (b) a blot: solid but irregular, at least M across, alone, at least M from the text block, not large
        far = x1 <= cx0 - gap or x0 >= cx1 + gap or y1 <= cy0 - gap or y0 >= cy1 + gap
        if far and max(hgt[i], wid[i]) >= gap and 0.45 <= fill < 0.85 and hgt[i] * wid[i] <= 0.03 * H * Wd \
                and all(j == i or j in isolated or j in shadow for j in members[int(gid[i])]):
            blots.add(i)
    for i in list(blots):  # the detached pieces of a stain: marks of its group on the same side
        lft, rgt = X1[i] <= cx0 - g, X0[i] >= cx1 + g
        for j in members[int(gid[i])]:
            if j in pre and j not in blots:
                if (lft and X1[j] <= cx0 - g) or (rgt and X0[j] >= cx1 + g) \
                        or (not lft and not rgt and (Y1[j] <= cy0 - g or Y0[j] >= cy1 + g)):
                    blots.add(j)
    out["blots"] = [box_of(i) for i in sorted(blots)]
    content = [i for i in pre if i not in blots]
    if not content:
        return out
    # LINES ARE NOT CONTENT HERE: a long thin mark (<= 0.6 % thick, >= 20 % of the page long) or a shorter thin line
    # beyond the text block, a dashed or dotted line beside it. A printed rule comes back in decide() when the book prints
    # it on many pages; a scan line does not. A line at a slant is thin by its ink, not by its box.

    def straight_thin(i: int, horiz: bool, lim_: float) -> bool:
        ys_, xs_ = np.nonzero(lab[objs[i - 1]] == i)
        if not horiz:
            ys_, xs_ = xs_, ys_
        n_ = int(xs_.max()) + 1
        cnt = np.bincount(xs_, minlength=n_)
        has = cnt > 0
        if has.sum() < 0.8 * n_ or np.percentile(cnt[has], 90) > lim_:
            return False
        xs1 = np.nonzero(has)[0]
        mid = np.bincount(xs_, weights=ys_, minlength=n_)[has] / cnt[has]
        fit = np.polyfit(xs1, mid, 1)
        return abs(fit[0]) <= 0.1 and np.percentile(np.abs(mid - np.polyval(fit, xs1)), 90) <= 1.0

    def thin_h(i: int, lim_: float) -> bool:
        return hgt[i] <= lim_ or (hgt[i] <= lim_ + 0.1 * wid[i] and straight_thin(i, True, lim_))

    def thin_v(i: int, lim_: float) -> bool:
        return wid[i] <= lim_ or (wid[i] <= lim_ + 0.1 * hgt[i] and straight_thin(i, False, lim_))

    lines = {i for i in content
             if (hgt[i] >= 0.2 * H and thin_v(i, 0.006 * Wd)) or (wid[i] >= 0.2 * Wd and thin_h(i, 0.006 * H))}
    for i in content:
        yc, xc = (Y0[i] + Y1[i]) / 2, (X0[i] + X1[i]) / 2
        if (wid[i] >= 0.03 * Wd and (yc <= cy0 - g or yc >= cy1 + g) and thin_h(i, 0.004 * H)) or \
                (hgt[i] >= 0.03 * H and (xc <= cx0 - g or xc >= cx1 + g) and thin_v(i, 0.004 * Wd)):
            lines.add(i)
    cset = set(content)
    for i in list(lines):  # the detached pieces of a line: specks of its group lying along it
        horiz = wid[i] >= hgt[i]
        for j in members[int(gid[i])]:
            if j in lines or j not in cset or not small[j]:
                continue
            if (horiz and Y0[j] >= Y0[i] - 1 and Y1[j] <= Y1[i] + 1) or (not horiz and X0[j] >= X0[i] - 1 and X1[j] <= X1[i] + 1):
                lines.add(j)
    bx0, bx1, by0, by1 = block(big, 10, 90)
    for vert in (True, False):
        pos = (lambda i: (X0[i] + X1[i]) / 2) if vert else (lambda i: (Y0[i] + Y1[i]) / 2)
        for kind in ("dash", "dot"):
            if kind == "dash":
                lo_c, hi_c, span, tol, least = (cx0, cx1, H, 0.004 * Wd, 4) if vert else (cy0, cy1, Wd, 0.004 * H, 4)
                ok = ((lambda i: wid[i] <= 0.004 * Wd and hgt[i] >= 2 * wid[i]) if vert
                      else (lambda i: hgt[i] <= 0.004 * H and wid[i] >= 2 * hgt[i]))
            else:
                lo_c, hi_c, span, tol, least = (bx0, bx1, H, 0.008 * Wd, 8) if vert else (by0, by1, Wd, 0.008 * H, 8)
                ok = ((lambda i: wid[i] <= 0.006 * Wd and hgt[i] <= 0.03 * H and (hgt[i] >= 2 * wid[i] or hgt[i] <= 0.008 * H))
                      if vert else
                      (lambda i: hgt[i] <= 0.006 * H and wid[i] <= 0.03 * Wd and (wid[i] >= 2 * hgt[i] or wid[i] <= 0.008 * Wd)))
            cand = sorted((i for i in content if i not in lines and (pos(i) <= lo_c - g or pos(i) >= hi_c + g) and ok(i)), key=pos)
            k = 0
            while k < len(cand):
                j = k
                while j + 1 < len(cand) and pos(cand[j + 1]) - pos(cand[k]) <= tol:
                    j += 1
                grp_ = cand[k:j + 1]
                if len(grp_) >= least:
                    lo = min(Y0[i] if vert else X0[i] for i in grp_)
                    hi = max(Y1[i] if vert else X1[i] for i in grp_)
                    if hi - lo >= 0.15 * span and (kind == "dot" or sum(hgt[i] if vert else wid[i] for i in grp_) >= 0.3 * (hi - lo)):
                        lines.update(grp_)
                k = j + 1
    out["lines"] = [box_of(i) for i in sorted(lines)]
    with_lines = list(content)
    content = [i for i in content if i not in lines] or content
    # printed rules and frames, even faint ones: beyond the text block, a column (row) where light ink runs along half
    # the text block's height (width) or more
    faint = a[r0:r1, c0:c1] < paper - 20
    iy0, iy1 = int(cy0), max(int(cy1), int(cy0) + 1)
    ix0, ix1 = int(cx0), max(int(cx1), int(cx0) + 1)
    bw = max(3, int(round(0.01 * Wd)))
    colcov = ndimage.maximum_filter(faint[iy0:iy1, :], size=(1, bw)).mean(0)
    rowcov = ndimage.maximum_filter(faint[:, ix0:ix1], size=(bw, 1)).mean(1)

    def sheet_edge(v: float, lo: float, hi: float, nn: int) -> bool:
        return (v < 0.06 * nn and lo - v >= 0.05 * Wd) or (v > 0.94 * nn and v - hi >= 0.05 * Wd)

    rule_x = [x for x in range(Wd) if colcov[x] >= 0.5 and (x <= cx0 - g or x >= cx1 + g) and 0.03 * Wd < x < 0.97 * Wd
              and not sheet_edge(x, cx0, cx1, Wd)]
    rule_y = [y for y in range(H) if rowcov[y] >= 0.5 and (y <= cy0 - g or y >= cy1 + g) and 0.03 * H < y < 0.97 * H
              and not sheet_edge(y, cy0, cy1, H)]

    def runs(v: list[int]) -> list[tuple[int, int]]:
        res, s0 = [], None
        for k, x in enumerate(v):
            if s0 is None:
                s0 = x
            if k + 1 == len(v) or v[k + 1] > x + 1:
                res.append((s0, x))
                s0 = None
        return res

    out["rules"] = [pt(a_, iy0, b_ + 1, iy1) for a_, b_ in runs(rule_x)] + [pt(ix0, a_, ix1, b_ + 1) for a_, b_ in runs(rule_y)]

    def rule_angle(a_: int, b_: int, vert: bool) -> float | None:
        sub = faint[iy0:iy1, a_:b_ + 1] if vert else faint[a_:b_ + 1, ix0:ix1].T
        rows = np.nonzero(sub.any(1))[0]
        if len(rows) < 0.3 * sub.shape[0] or len(rows) < 20:
            return None
        pos_ = np.array([np.nonzero(sub[r_])[0].mean() for r_ in rows])
        k, c = np.polyfit(rows, pos_, 1)
        ok_ = np.abs(pos_ - (k * rows + c)) <= 2
        if ok_.sum() >= 20:
            k = np.polyfit(rows[ok_], pos_[ok_], 1)[0]
        return float(np.degrees(np.arctan(k)))

    def lv(a_: int, b_: int, vert: bool) -> bool:
        g_ = rule_angle(a_, b_, vert)
        return g_ is not None and abs(g_) <= 0.35

    sides = {("L" if b_ < cx0 else "R") for a_, b_ in runs(rule_x) if lv(a_, b_, True)} | \
            {("T" if b_ < cy0 else "B") for a_, b_ in runs(rule_y) if lv(a_, b_, False)}
    out["level_frame"] = {"L", "R"} <= sides or {"T", "B"} <= sides
    keep = np.zeros(n + 1, bool)
    keep[content] = True
    ys, xs = np.nonzero(keep[lab])
    out["box"] = pt(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    out["parts"] = [box_of(i) for i in content]
    qx, qy = np.percentile(xs, [2, 98]), np.percentile(ys, [2, 98])
    out["core"] = pt(qx[0], qy[0], qx[1] + 1, qy[1] + 1)
    # THE TEXT BLOCK BY GAPS: from the core's columns, every letter-like mark less than 1.5 % of the width away joins the
    # text and widens it (a longer line, a heading, a verse stays whole); everything above and below inside those
    # columns is text too (running head, page number, footnotes). Marks further out sit in a side margin.
    cid = np.array(content)
    x0a, x1a, y0a, y1a = X0[cid], X1[cid], Y0[cid], Y1[cid]
    gx = 0.015 * Wd
    strip = (x1a <= 0.03 * Wd) | (x0a >= 0.97 * Wd) | (y1a <= 0.03 * H) | (y0a >= 0.97 * H)
    hh, ww = y1a - y0a, x1a - x0a
    thin = ((hh <= 0.004 * H) & (ww >= 0.03 * Wd)) | ((ww <= 0.004 * Wd) & (hh >= 0.03 * H))
    letter = ~strip & ~thin & (hh <= 0.15 * H) & ((hh >= 0.004 * H) | (ww >= 0.008 * Wd))
    # a scan line broken into dashes is no letter: a hairline is a letter only beside another letter on its row
    hair = letter & (hh < 2.5) & (ww >= 4 * hh)
    if hair.any():
        oth = letter & ~hair
        ym = (y0a + y1a) / 2
        for k in np.nonzero(hair)[0]:
            if not (oth & (y0a <= ym[k]) & (y1a >= ym[k]) & (x0a <= x1a[k] + gx) & (x1a >= x0a[k] - gx)).any():
                letter[k] = False
    if not letter.any():
        letter = ~strip if (~strip).any() else np.ones(len(cid), bool)
    tx0, tx1 = float(np.percentile(x0a[letter], 2)), float(np.percentile(x1a[letter], 98))
    while True:
        inn = letter & (x1a >= tx0 - gx) & (x0a <= tx1 + gx)
        if not inn.any():
            inn = letter
            break
        nx0, nx1 = float(x0a[inn].min()), float(x1a[inn].max())
        if nx0 >= tx0 and nx1 <= tx1:
            break
        tx0, tx1 = min(tx0, nx0), max(tx1, nx1)
    out["text"] = pt(float(x0a[inn].min()), float(y0a[inn].min()), float(x1a[inn].max()), float(y1a[inn].max()))
    # THE PAGE NUMBER on its own line at the foot or the head of the text block: a short group with a clear gap
    lx0, lx1, ly0, ly1 = x0a[inn], x1a[inn], y0a[inn], y1a[inn]
    for foot in (True, False):
        e = ly1.max() if foot else ly0.min()
        sel = (ly0 >= e - 0.025 * H) if foot else (ly1 <= e + 0.025 * H)
        if not sel.any() or sel.all():
            continue
        fy0, fy1, fx0, fx1 = ly0[sel].min(), ly1[sel].max(), lx0[sel].min(), lx1[sel].max()
        gp = fy0 - ly1[~sel].max() if foot else ly0[~sel].min() - fy1
        if gp >= 0.012 * H and 0.005 * Wd <= fx1 - fx0 <= 0.08 * Wd and fy1 - fy0 <= 0.025 * H:
            out["folio"] = pt(float(fx0), float(fy0), float(fx1), float(fy1)) + ["foot" if foot else "head"]
            break
    tb_ = out["text"]
    out["margin"] = [b for b in (box_of(int(i)) for i in cid) if not inside(b, tb_)]
    kl = np.zeros(n + 1, bool)
    kl[with_lines] = True
    out["xy"] = tuple(reversed(np.nonzero(kl[lab]))) if len(with_lines) != len(content) else (xs, ys)
    out["xy_text"] = (xs, ys)  # the same without the thin lines: what the text's own edges are read on
    return out


# -- marks in a page's margin ------------------------------------------------------------------------------------------

def figures_of(margin: list, w: float, h: float) -> list:
    """pictures, plates, tables beside the text: a mark at least 15 % of the page wide and tall and 4 % of its area"""
    return [b for b in margin if b[2] - b[0] >= 0.15 * w and b[3] - b[1] >= 0.15 * h
            and (b[2] - b[0]) * (b[3] - b[1]) >= 0.04 * w * h]


def _groups(boxes: list, g: float) -> list[np.ndarray]:
    B = np.array(boxes, float)
    adj = (B[:, None, 0] < B[None, :, 2] + g) & (B[None, :, 0] < B[:, None, 2] + g) & \
          (B[:, None, 1] < B[None, :, 3] + g) & (B[None, :, 1] < B[:, None, 3] + g)
    k, lab = connected_components(adj, directed=False)
    return [B[lab == j] for j in range(k)]


def printed_groups(margin: list, w: float, h: float) -> list:
    """print in the margin of a book that prints there (folio numbers, glosses, side headings): groups of margin marks
    less than 1.5 % of the width apart holding two letter-sized marks or more, or one large glyph; not lines"""
    marks_ = [b for b in margin if not thin_line(b, w, h)]
    if not marks_:
        return []
    out = []
    for S in _groups(marks_, 0.015 * w):
        hh, ww = S[:, 3] - S[:, 1], S[:, 2] - S[:, 0]
        if ((hh >= 0.006 * h) & (ww >= 0.003 * w)).sum() >= 2 or (hh >= 0.015 * h).any():
            out.append([float(S[:, 0].min()), float(S[:, 1].min()), float(S[:, 2].max()), float(S[:, 3].max())])
    return out


def notes_of(margin: list, w: float, h: float) -> list:
    """marginal notes a reader or the printer put beside the text: groups (less than 2 % of the width apart) of three
    letter-sized strokes or more, not in the sheet's outer 3 %, with no more specks than strokes inside, spanning 2-30 %
    of the width and at most 25 % of the height. A single stroke, dots, smudges and scan edges are not notes"""
    L = [b for b in margin if not (b[2] <= 0.03 * w or b[0] >= 0.97 * w or b[3] <= 0.03 * h or b[1] >= 0.97 * h)
         and b[3] - b[1] <= 0.06 * h and b[2] - b[0] <= 0.10 * w and (b[3] - b[1] >= 0.005 * h or b[2] - b[0] >= 0.008 * w)
         and not (b[2] - b[0] <= 0.003 * w and b[3] - b[1] >= 3 * (b[2] - b[0]))
         and not (b[3] - b[1] <= 0.003 * h and b[2] - b[0] >= 3 * (b[3] - b[1]))]
    if not L or len(L) > 400:
        return []
    out = []
    for S in _groups(L, 0.02 * w):
        box = [float(S[:, 0].min()), float(S[:, 1].min()), float(S[:, 2].max()), float(S[:, 3].max())]
        bw, bh = box[2] - box[0], box[3] - box[1]
        tiny = sum(1 for b in margin if max(b[2] - b[0], b[3] - b[1]) < 0.004 * w and inside(b, box, 1.0))
        if len(S) >= 3 and tiny <= len(S) and max(bw, bh) >= 0.02 * w and min(bw, bh) >= 0.008 * w and bw <= 0.3 * w \
                and bh <= 0.25 * h:
            out.append(box)
    return out


def printlike(b: list, w: float, h: float, z: float) -> bool:
    """a mark that may be print the box must hold: not a hairline (1-2 px thick, 4x as long: a scan line in dashes), not a
    bar (a tenth of the page long or more and 8x as long as thick: a copier's bar)"""
    bw, bh = b[2] - b[0], b[3] - b[1]
    th, ln = min(bw, bh), max(bw, bh)
    if th * z < 2.5 and ln >= 4 * th:
        return False
    return not ((bw >= 0.1 * w and bw >= 8 * bh) or (bh >= 0.1 * h and bh >= 8 * bw))


def letterlike(b: list, w: float, h: float) -> bool:
    bw, bh = b[2] - b[0], b[3] - b[1]
    return not (b[2] <= 0.03 * w or b[0] >= 0.97 * w or b[3] <= 0.03 * h or b[1] >= 0.97 * h) and not thin_line(b, w, h) \
        and bh <= 0.15 * h and (bh >= 0.004 * h or bw >= 0.008 * w)


def text_block(parts: list, seed: list, w: float, h: float, z: float) -> list | None:
    """the text block by gaps on print-like marks only (at high resolution a scan line breaks into one-pixel dashes)"""
    L = [b for b in parts if printlike(b, w, h, z) and letterlike(b, w, h)]
    x0, x1, gx = seed[0], seed[2], 0.015 * w
    while True:
        inn = [b for b in L if b[2] >= x0 - gx and b[0] <= x1 + gx]
        if not inn:
            return None
        nx0, nx1 = min(b[0] for b in inn), max(b[2] for b in inn)
        if nx0 >= x0 and nx1 <= x1:
            break
        x0, x1 = min(x0, nx0), max(x1, nx1)
    return union(inn)


def needed(p: dict) -> list | None:
    """what a page must show: its text block, its marginal notes, figures, print in the margin, kept rules, folio"""
    if not p.get("text"):
        return p.get("box")
    mg = p.get("margin") or []
    return union([p["text"]] + notes_of(mg, p["w"], p["h"]) + figures_of(mg, p["w"], p["h"])
                 + printed_groups(mg, p["w"], p["h"]) + (p.get("rules") or []) + ([p["folio"][:4]] if p.get("folio") else []))
