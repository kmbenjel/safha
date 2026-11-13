"""Tilt measures. Angles are degrees, counter-clockwise positive (the turn that levels a page is minus its tilt).

Four independent rulers, so that no page is turned on the word of one:

* ``skew_of``   the shear angle that makes the ink's row profile sharpest, read on the whole text and on its two
                halves; a real tilt is the same everywhere (index pages, two columns and verse fool the whole page).
* ``proj_tilt`` the page image itself, turned in steps, its central rows counted: coarse, a guard against a bad turn.
* ``line_tracks`` each line followed across the page strip by strip: lines at two angles (a warped leaf) are seen.
* ``frame_lean`` / ``frame_shear`` a printed frame around the text: the standard the eye squares a page by.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

EPS = 1e-6


def skew_of(xy: tuple | None, raw: bool = False, wide: float = 8.0) -> tuple[float, float]:
    """the angle that makes the text lines level, and its sharpness gain over 0 -> (angle, gain); (0, 1) when unsure.

    Accepted only when the whole page's angle lies within the range of its halves' angles (+-0.1) and the halves differ by
    <= 0.6 deg. ``raw``: the whole-page angle alone. Too little ink or fewer than 8 text lines: (0, 1)."""
    if xy is None or len(xy[0]) < 1500:
        return 0.0, 1.0
    xs, ys = xy
    if len(xs) > 60000:
        k = np.random.default_rng(0).choice(len(xs), 60000, replace=False)
        xs, ys = xs[k], ys[k]

    def best(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
        def score(a: float) -> float:
            yy = np.round(y + x * np.tan(np.radians(a))).astype(np.int64)
            yy -= yy.min()
            c = np.bincount(yy).astype(float)
            return float((c * c).sum())

        base = score(0.0)
        angs = np.arange(-4, 4.001, 0.25)
        a0 = float(angs[int(np.argmax([score(v) for v in angs]))])
        if abs(a0) >= 3.75 and wide > 4:  # the best at the edge: look further
            angs = np.arange(-wide, wide + 0.001, 0.25)
            a0 = float(angs[int(np.argmax([score(v) for v in angs]))])
        fine = np.arange(a0 - 0.25, a0 + 0.2501, 0.025)
        sc = [score(v) for v in fine]
        return float(fine[int(np.argmax(sc))]), max(sc) / base

    x, y = xs.astype(float), ys.astype(float)
    a, gain = best(x, y)
    if raw:
        return a, gain
    if len(xs) < 6000:
        return 0.0, 1.0
    yy = np.round(y + x * np.tan(np.radians(a))).astype(np.int64)
    yy -= yy.min()
    prof = np.bincount(yy).astype(float)
    thr = 0.3 * prof.max()
    lines = sum(1 for i in range(1, len(prof) - 1) if prof[i] >= thr and prof[i] >= prof[i - 1] and prof[i] > prof[i + 1])
    if lines < 8:
        return 0.0, 1.0
    h = np.percentile(x, 50)
    parts = []
    for msk in (x < h, x >= h):
        if msk.sum() >= 500:
            parts.append(best(x[msk] - x[msk].min(), y[msk])[0])
    if len(parts) < 2 or abs(parts[0] - parts[1]) > 0.6 + EPS \
            or not (min(parts) - 0.1 - EPS <= a <= max(parts) + 0.1 + EPS):
        return 0.0, 1.0
    return a, gain


def proj_tilt(a: np.ndarray, paper: float, lo: float = -0.5, hi: float = 0.5, step: float = 0.05,
              width: int = 700) -> float:
    """|tilt| by the page image: its ink pixels at 700 px wide, turned about the centre by each angle, the rows of the
    page's centre (8-92 % of the width, 5-95 % of the height) counted; the sharpest row profile wins (coarse steps, then
    0.025 deg around the best). A guard independent of the marks: sign-free use only."""
    H0, W0 = a.shape
    f = min(1.0, width / W0)
    if f < 1.0:
        from PIL import Image

        im = Image.fromarray(np.ascontiguousarray(a)).resize((width, max(1, round(H0 * f))), Image.BILINEAR)
        a = np.asarray(im)
    h, w = a.shape
    thr = max(60, min(200, paper - 50))
    ys, xs = np.nonzero(a < thr)
    if len(xs) < 50:
        return 0.0
    cx, cy = w / 2, h / 2
    x, y = xs - cx, ys - cy
    x0, x1, y0, y1 = w * .08 - cx, w * .92 - cx, h * .05 - cy, h * .95 - cy

    def score(t: float) -> float:
        r = np.radians(t)
        c, s = np.cos(r), np.sin(r)
        xr, yr = c * x + s * y, -s * x + c * y
        k = (xr >= x0) & (xr < x1) & (yr >= y0) & (yr < y1)
        rows = np.floor(yr[k] - y0).astype(np.int64)
        cnt = np.bincount(rows, minlength=int(y1 - y0) + 1).astype(float)
        return float(np.var(cnt))

    angs = np.arange(lo, hi + step / 2, step)
    k = int(np.argmax([score(t) for t in angs]))
    fine = np.arange(angs[k] - step, angs[k] + step + 1e-9, 0.025)
    j = int(np.argmax([score(t) for t in fine]))
    return round(abs(float(fine[j])), 3)


def baseline_tilt(a: np.ndarray, paper: float, min_lines: int = 6) -> float | None:
    """line by line, the height of the baseline (densest ink row) at the line's right third against its left third; the
    median over lines at least 20 % of the page wide. Only certifies a turn, never decides one."""
    m = a < max(60, min(200, paper - 50))
    H, W = m.shape
    prof = ndimage.uniform_filter1d(m.sum(1).astype(float), 3)
    thr = 0.25 * prof.max()
    r = int(0.008 * H)
    peaks = [i for i in range(2, H - 2) if prof[i] >= thr and prof[i] == prof[max(0, i - r):i + r + 1].max()]
    if len(peaks) < min_lines:
        return None
    gaps = np.diff(peaks)
    sp = float(np.median(gaps)) if len(gaps) else 0
    if sp < 6:
        return None
    sl = []
    for y in peaks:
        y0, y1 = int(max(0, y - 0.45 * sp)), int(min(H, y + 0.45 * sp))
        band = m[y0:y1]
        cols = np.nonzero(band.any(0))[0]
        if len(cols) < 10:
            continue
        x0, x1 = cols[0], cols[-1]
        if x1 - x0 < 0.2 * W:
            continue
        t = (x1 - x0) / 3
        L, R = band[:, x0:int(x0 + t)], band[:, int(x1 - t):x1 + 1]
        if L.sum() < 30 or R.sum() < 30:
            continue
        rl = ndimage.uniform_filter1d(L.sum(1).astype(float), 3)
        rr = ndimage.uniform_filter1d(R.sum(1).astype(float), 3)
        dy = float(np.argmax(rr) - np.argmax(rl))
        dx = (x1 - t / 2) - (x0 + t / 2)
        sl.append(np.degrees(np.arctan2(dy, dx)))
    if len(sl) < min_lines:
        return None
    return float(np.median(sl))


def ink_mask(xy: tuple | None, shape: tuple[int, int] | None = None) -> np.ndarray | None:
    """the page's content ink (``marks()['xy']``: its print and rules, without scanner bands, sheet edges and stains)
    as an image"""
    if xy is None or len(xy[0]) == 0:
        return None
    xs, ys = xy
    m = np.zeros(shape or (int(ys.max()) + 1, int(xs.max()) + 1), bool)
    m[ys, xs] = True
    return m


def edge_tilt(m: np.ndarray) -> list[tuple[float, int, float] | None]:
    """THE LINES' EDGE AS A RULER: lines set flush all start (or end) at one edge, and on a level page that edge stands
    upright. In the ink mask ``m``, line by line (bands of ink rows), the outermost ink on each side; the lines within
    1.5 % of the width of the median edge are the aligned ones; the lean is the median of the slopes between pairs of
    them at least 10 % of the page apart. -> [right edge, left edge], each (degrees in the sign of skew_of's angle,
    aligned lines, spread: the interquartile range of those slopes in degrees -- a flush edge reads under half a degree,
    a ragged one several) or None when fewer than 6 lines are aligned on that side"""
    H, W = m.shape
    prof = ndimage.uniform_filter1d(m.sum(1).astype(float), 3)
    if prof.max() <= 0:
        return [None, None]
    rows = prof >= 0.15 * prof.max()
    pts = []
    y = 0
    while y < H:
        if rows[y]:
            y0 = y
            while y < H and rows[y]:
                y += 1
            if y - y0 >= 0.004 * H:
                cols = np.nonzero(m[y0:y].sum(0) >= 2)[0]
                if len(cols) >= 5:
                    pts.append(((y0 + y) / 2, cols[-1], cols[0]))
        y += 1
    out: list[tuple[float, int] | None] = []
    for k in (1, 2):
        if len(pts) < 6:
            out.append(None)
            continue
        P = np.array(pts, float)
        xs = P[:, k]
        keep = P[np.abs(xs - np.median(xs)) <= 0.015 * W]
        if len(keep) < 6:
            out.append(None)
            continue
        dy = keep[None, :, 0] - keep[:, None, 0]
        dx = keep[None, :, k] - keep[:, None, k]
        far = dy > 0.1 * H
        if not far.any():
            out.append(None)
            continue
        sl = np.degrees(np.arctan(dx[far] / dy[far]))
        out.append((float(np.median(sl)), len(keep), float(np.subtract(*np.percentile(sl, [75, 25])))))
    return out


def column_rule(m: np.ndarray) -> tuple[int, float | None] | None:
    """A PRINTED RULE BETWEEN TWO COLUMNS (a dictionary, a journal, a table): the print's straightest line and so the
    page's own standard of upright. In the ink mask ``m``: the strokes that run 3 % of the page's height or more without
    a break (no letter does), between 28 % and 72 % of the width; the tallest piece and the pieces standing within
    1.2 % of the width of it (a rule often prints broken), when together they cover half the height of the page's ink or
    more, and no other tall rule stands elsewhere in that middle band (several mean a table). The rule is followed row
    by row (rows where a letter touches it left out; a line that runs through letters
    on more than 15 % of its rows is a streak or a fold across the text, no rule) and fitted by a line, the rows
    furthest from it dropped twice.
    -> None (no such rule), or (its column at mid-height in px, its lean in degrees: the turn that squares it is its
    negative). The lean is None when the rule is no standard: bent or in pieces out of line (more than 1.5 px off the
    fitted line; its upper and lower halves leaning more than 0.6 deg apart, as for a frame's side; the line through
    both leaning more than 0.15 deg off their mean, as two straight pieces set a little apart do; or one half standing
    so much straighter than the other that squaring the whole would make it lean more than it does) -- a warped leaf,
    which no single turn levels, or a rule that cannot say."""
    H, W = m.shape
    x0, x1 = int(0.28 * W), int(0.72 * W)
    L = max(12, int(0.03 * H))
    v = ndimage.maximum_filter1d(ndimage.minimum_filter1d(m[:, x0:x1].astype(np.uint8), L, axis=0), L, axis=0) > 0
    if int(v.sum()) < 0.25 * H:
        return None
    inked = np.nonzero(m.any(1))[0]
    if len(inked) < 50:
        return None
    th = float(np.percentile(inked, 98) - np.percentile(inked, 2))
    lab, n = ndimage.label(v, structure=np.ones((3, 3), bool))
    objs = ndimage.find_objects(lab)
    thin = [k for k, sl in enumerate(objs, 1) if sl[1].stop - sl[1].start <= 0.06 * W]
    if not thin:
        return None
    seed = max(thin, key=lambda k: objs[k - 1][0].stop - objs[k - 1][0].start)
    cx = (objs[seed - 1][1].start + objs[seed - 1][1].stop) / 2
    near = [k for k in thin if abs((objs[k - 1][1].start + objs[k - 1][1].stop) / 2 - cx) <= 0.012 * W]
    sub = np.isin(lab, near)
    rows = np.nonzero(sub.any(1))[0]
    if len(rows) < 0.5 * th:
        return None
    # a second tall rule elsewhere in the middle of the page: a table's grid, not a rule between two columns of text (the
    # rules of a table are no standard for its rows); such a page is measured like any other
    if any(k not in near and objs[k - 1][0].stop - objs[k - 1][0].start >= 0.3 * th for k in thin):
        return None
    # a rule stands here: the page is in two columns. Whether it is a standard is another matter
    first = sub.argmax(1)[rows]
    last = sub.shape[1] - 1 - sub[:, ::-1].argmax(1)[rows]
    wd = last - first + 1
    # the ink right beside it (3 px each side): a rule between columns stands clear of the letters
    cs = np.cumsum(np.pad(m[:, x0:x1], ((0, 0), (1, 0))), axis=1)
    lo, hi = np.maximum(first - 3, 0), np.minimum(last + 4, sub.shape[1])
    beside = cs[rows, hi] - cs[rows, lo] - wd
    if (beside > 1).mean() > 0.15:
        return None  # it runs through the letters on many rows: a streak or a fold across the text, no column rule
    ok = (wd <= np.median(wd) + 3) & (beside <= 1)
    rows, xs = rows[ok].astype(float), ((first + last) / 2.0)[ok]
    at = int(x0 + cx)
    if len(rows) < 0.4 * th:
        return at, None
    f = np.polyfit(rows, xs, 1)
    for _ in range(2):
        res = np.abs(xs - np.polyval(f, rows))
        keep = res <= max(1.0, 2.5 * float(np.median(res)))
        if keep.sum() < 0.4 * th:
            return at, None
        rows, xs = rows[keep], xs[keep]
        f = np.polyfit(rows, xs, 1)
    half = rows < (rows[0] + rows[-1]) / 2
    if float(np.sqrt(((xs - np.polyval(f, rows)) ** 2).mean())) > 1.5 or half.sum() < 15 or (~half).sum() < 15:
        return at, None
    t = float(np.degrees(np.arctan(np.polyfit(rows[half], xs[half], 1)[0])))
    u = float(np.degrees(np.arctan(np.polyfit(rows[~half], xs[~half], 1)[0])))
    lean = float(np.degrees(np.arctan(f[0])))
    if abs(t - u) > 0.6 + EPS or abs(lean - (t + u) / 2) > 0.15 + EPS \
            or any(abs(h - lean) > max(abs(h), 0.15) + EPS for h in (t, u)):
        # bent; or two pieces set out of line, each standing straighter than the line through both; or squaring the
        # whole would leave one half leaning more than it does now (the other half's lean moved onto it)
        return at, None
    return int(x0 + np.polyval(f, (rows[0] + rows[-1]) / 2)), round(lean, 3)


def columns_tilt(m: np.ndarray) -> list[float | None] | None:
    """TWO COLUMNS WITH A PRINTED RULE BETWEEN THEM (a dictionary, an index, a journal): lines whose two ends stand at
    different heights (a headword and its gloss in another script, an entry and its page number) fool every whole-page
    measure, and the rule is what the print holds upright: its lean (``column_rule``) is the page's tilt.

    ``m`` is the page's content ink (``ink_mask``: a scanner band or a sheet's edge is no rule).
    -> None (no such rule: the page is measured like any other), or [lean, lean] in degrees, the sign of skew_of's angle
    (None for both when the rule is bent: no standard). Two columns across a white gutter, with no rule, are not read
    here: the edges of their lines lean with the setting as often as with the page, and turn nothing on their own."""
    rule = column_rule(m)
    return None if rule is None else [rule[1], rule[1]]


def edges_refuse(m: np.ndarray | None, tilt: float, least: int = 10, turned: np.ndarray | None = None) -> list[float]:
    """A TURN THE MARGINS REFUSE: the text's own edges (``edge_tilt`` on the page as scanned: lines set flush stand on a
    straight edge) against the tilt a turn was made for. Each edge at least ``least`` lines stand on, straight enough
    to be read (the slopes between its lines within one degree of each other, by their interquartile range), is a
    witness. A witness stands against the turn when it shows less than half of that tilt (it stands upright, or leans the other
    way) and reads more than 0.3 deg from it; the turn is refused when every witness does. (The row profile of lines whose
    two ends stand at different heights -- a headword and its gloss in another script, an entry and its page number --
    sharpens at an angle the page does not lie at; its margins do not lie.) Margins that lean the way of the lines, by
    half their tilt or more, refuse nothing: the leaf lies askew, whatever the two disagree on. ``turned``: the ink of
    the page as turned for that tilt; the edges are read there too (a page that lies well off level smears its lines
    into each other as scanned, and its edges read badly): what they show there, plus the tilt, is what they stood at
    before the turn, and they must stand against the turn in that reading as well. A view with no witness changes
    nothing. -> the witnesses' readings as scanned when they refuse, else []"""
    if m is None:
        return []
    s = 1.0 if tilt >= 0 else -1.0

    def against(v: float) -> bool:
        return v * s < 0.5 * abs(tilt) - EPS and abs(v - tilt) > 0.3 + EPS

    def witnesses(mask: np.ndarray) -> list[float]:
        return [v[0] for v in edge_tilt(mask) if v is not None and v[1] >= least and v[2] <= 1.0 + EPS]

    e = witnesses(m)
    if not e or not all(against(v) for v in e):
        return []
    if turned is not None:
        e2 = [v + tilt for v in witnesses(turned)]
        if e2 and not all(against(v) for v in e2):
            return []
    return [round(v, 3) for v in e]


def _line_chains(ink: np.ndarray, z: float, strip_pt: float, pitch: int, ref: float) -> list[np.ndarray]:
    """the chains of baseline peaks of one column of a text block: per strip the peaks of the ink-row profile (a parabola
    gives a fraction of a pixel), each linked to the line heading towards it in the next strips (within a fifth of the
    line pitch, up to 3 strips on)"""
    bh, bw = ink.shape
    K = max(3, int(round(bw / (strip_pt * z))))
    e = np.linspace(0, bw, K + 1).astype(int)
    peaks = []
    for j in range(K):
        pr = ndimage.gaussian_filter1d(ink[:, e[j]:e[j + 1]].sum(1), 1.0)
        mxf = ndimage.maximum_filter1d(pr, 2 * max(2, int(0.45 * pitch)) + 1)
        pk = []
        for r in np.nonzero((pr == mxf) & (pr >= 0.25 * ref * (e[j + 1] - e[j])))[0]:
            rr = float(r)
            if 0 < r < len(pr) - 1:
                den = pr[r - 1] - 2 * pr[r] + pr[r + 1]
                if den < 0:
                    rr = r + 0.5 * (pr[r - 1] - pr[r + 1]) / den
            pk.append(rr)
        peaks.append(pk)
    chains: list[list] = []
    for j in range(K):
        xc = (e[j] + e[j + 1]) / 2
        cand = []
        for ci, (pts, last) in enumerate(chains):
            if j - last > 3:
                continue
            if len(pts) >= 3:
                X = np.array(pts)
                yp = np.polyval(np.polyfit(X[:, 0], X[:, 1], 1), xc)
            else:
                yp = pts[-1][1]
            cand += [(abs(y - yp), ci, k) for k, y in enumerate(peaks[j]) if abs(y - yp) <= 0.2 * pitch]
        uc, uk = set(), set()
        for _, ci, k in sorted(cand):
            if ci in uc or k in uk:
                continue
            uc.add(ci)
            uk.add(k)
            chains[ci][0].append((xc, peaks[j][k]))
            chains[ci][1] = j
        chains += [[[(xc, y)], j] for k, y in enumerate(peaks[j]) if k not in uk]
    return [np.array(c[0]) for c in chains]


Track = tuple[float, float, float, float, int, bool]


def line_tracks(a: np.ndarray, paper: float, tb: list | None, z: float, strip_pt: float = 21.0) -> list[Track]:
    """each line of the text block ``tb`` (pt; z px per pt) followed across the page strip by strip: vertical rules
    whitened, the block cut at its white gutters (an index in columns is never linked across them), the line pitch read
    from the strips' autocorrelation; a straight line through each chain of >= 6 strips and 30 % of its column.
    Returns [(y pt, angle, share of the block's width, rms px, points, is_rule)] sorted by height; the angle has the sign
    of the turn that levels the line (on a page turned by d a line reads angle - d)."""
    if tb is None:
        return []
    H, W = a.shape
    mx, my = 0.02 * W, 0.01 * H
    x0, y0 = max(0, int(tb[0] * z - mx)), max(0, int(tb[1] * z - my))
    x1, y1 = min(W, int(tb[2] * z + mx)), min(H, int(tb[3] * z + my))
    if x1 - x0 < 50 or y1 - y0 < 50:
        return []
    ink = np.clip((paper - a[y0:y1, x0:x1].astype(np.float32)) / max(paper, 1), 0, 1)
    bh, bw = ink.shape
    m = ink > 0.35
    run = np.zeros(bw, int)
    for x in np.nonzero(m.sum(0) >= 0.25 * bh)[0]:
        d_ = np.diff(np.concatenate(([0], m[:, x].astype(np.int8), [0])))
        s0, s1 = np.nonzero(d_ == 1)[0], np.nonzero(d_ == -1)[0]
        run[x] = int((s1 - s0).max()) if len(s0) else 0
    rl = np.nonzero(run >= 0.25 * bh)[0]
    if len(rl):
        ink[:, np.unique(np.clip(np.concatenate([rl - 1, rl, rl + 1]), 0, bw - 1))] = 0
    K = max(8, int(round(bw / (strip_pt * z))))
    e = np.linspace(0, bw, K + 1).astype(int)
    P = [ndimage.gaussian_filter1d(ink[:, e[j]:e[j + 1]].sum(1), 1.0) for j in range(K)]
    ac = np.zeros(bh)
    for pr in P:
        qq = pr - pr.mean()
        f = np.fft.rfft(qq, 2 * bh)
        ac += np.fft.irfft(f * np.conj(f))[:bh]
    hi = min(bh // 2, int(0.08 * W))
    up = np.nonzero(np.diff(ac[:hi]) > 0)[0]
    if len(up) == 0:
        return []
    lo = max(3, int(up[0]))
    if lo >= hi:
        return []
    pitch = lo + int(np.argmax(ac[lo:hi]))
    if ac[pitch] <= 0.05 * ac[0]:
        pitch = int(0.035 * W)
    ref = np.percentile([pr.max() / max(1, e[j + 1] - e[j]) for j, pr in enumerate(P)], 90)
    occ = ndimage.uniform_filter1d(m.mean(0), max(3, int(0.006 * W)))
    lab, n = ndimage.label(occ < 0.01)
    cuts = [0]
    for k in range(1, n + 1):
        xs = np.nonzero(lab == k)[0]
        if xs[-1] - xs[0] + 1 >= 0.006 * W and 0.15 * bw <= (xs[0] + xs[-1]) / 2 <= 0.85 * bw:
            cuts.append(int((xs[0] + xs[-1]) / 2))
    cuts.append(bw)
    out: list[Track] = []
    for c0, c1 in zip(cuts[:-1], cuts[1:]):
        if c1 - c0 < 0.12 * bw:
            continue
        for X in _line_chains(ink[:, c0:c1], z, strip_pt, pitch, ref):
            if len(X) < 6 or X[-1, 0] - X[0, 0] < 0.3 * (c1 - c0):
                continue
            for _ in range(2):
                f = np.polyfit(X[:, 0], X[:, 1], 1)
                res = np.abs(X[:, 1] - np.polyval(f, X[:, 0]))
                if len(X) > 6:
                    X = X[res <= max(1.0, 2.5 * np.median(res))]
            if len(X) < 6:
                continue
            f = np.polyfit(X[:, 0], X[:, 1], 1)
            res = X[:, 1] - np.polyval(f, X[:, 0])
            xs = np.arange(int(X[0, 0]), int(X[-1, 0]) + 1)
            rs = np.rint(np.polyval(f, xs)).astype(int)
            hit = np.array([ink[max(0, r - 1):max(0, r + 2), c0 + x].max(initial=0) >= 0.4 for x, r in zip(xs, rs)])
            rule = bool(hit.mean() >= 0.9 and
                        (np.diff(np.concatenate(([-1], np.nonzero(hit)[0], [len(hit)]))) - 1).max() <= 6 * z)
            out.append((round((float(np.polyval(f, (c1 - c0) / 2)) + y0) / z, 1), round(float(np.degrees(np.arctan(f[0]))), 3),
                        round(float(X[-1, 0] - X[0, 0]) / bw, 2), round(float(np.sqrt((res ** 2).mean())), 2), len(X), rule))
    return sorted(out)


def _read_well(t: Track) -> bool:
    return t[3] <= 1.0 and t[4] >= 6 and t[2] >= 0.3


def tracks_tilt(T: list[Track]) -> tuple[float, int, float] | None:
    """the page's tilt by its lines followed across it: the median of the lines read well when >= 5 agree (IQR < 0.3)"""
    an = [t[1] for t in T if _read_well(t) and not t[5]]
    if len(an) < 5:
        return None
    iq = float(np.subtract(*np.percentile(an, [75, 25])))
    return (round(float(np.median(an)), 3), len(an), round(iq, 3)) if iq < 0.3 else None


def lines_read(t0: list[Track], t1: list[Track], d: float) -> list[tuple[float, float, float]] | None:
    """the lines a turn ``d`` can be judged by: read well on the page as scanned (t0) and as turned (t1), alike in both
    (moved by the turn within 0.15 deg), following one another (median change line to line <= 0.25 deg).
    -> [(y, before, after)] or None (fewer than 5)"""
    B = [u for u in t1 if _read_well(u)]
    L = []
    for t in t0:
        if not _read_well(t):
            continue
        m_ = [u for u in B if abs(u[0] - t[0]) <= 6]
        if m_ and abs(min(m_, key=lambda u: abs(u[0] - t[0]))[1] - (t[1] - d)) <= 0.15 + EPS:
            L.append((t[0], t[1], round(t[1] - d, 3)))
    L.sort()
    if len(L) < 5 or float(np.median(np.abs(np.diff([v[1] for v in L])))) > 0.25 + EPS:
        return None
    return L


def two_angles(L: list | None) -> list:
    """a turn the lines do not take: lines it leaves beyond 0.35 deg and >= 0.25 deg more tilted than they were, when there
    are two or more and they are a fifth of the lines, or fewer than 80 % of the lines end within 0.35 deg of level"""
    if not L:
        return []
    w = [v for v in L if abs(v[2]) > 0.35 + EPS and abs(v[2]) >= abs(v[1]) + 0.25 - EPS]
    agree = sum(1 for v in L if abs(v[2]) <= 0.35 + EPS)
    return w if len(w) >= 2 and (len(w) >= 0.2 * len(L) or agree < 0.8 * len(L)) else []


def print_turn(t0: list[Track], t1: list[Track], d: float) -> tuple[bool, list]:
    """a turn the print certifies: the page's printed rules (read alike in both views) all level once turned, and its
    lines of text give no steady reading of their own (an index under a head rule)"""
    R = []
    for t in t0:
        if not (_read_well(t) and t[5]):
            continue
        m_ = [u for u in t1 if _read_well(u) and abs(u[0] - t[0]) <= 6]
        if not m_:
            continue
        u = min(m_, key=lambda u: abs(u[0] - t[0]))
        if abs(u[1] - (t[1] - d)) <= 0.15 + EPS:
            R.append((t[0], t[1], round(t[1] - d, 3)))
    if not R or any(abs(v[2]) > 0.15 + EPS for v in R):
        return False, R
    LT = lines_read([t for t in t0 if not t[5]], [t for t in t1 if not t[5]], d)
    if LT and float((np.abs(np.diff([v[1] for v in LT])) > 0.3 + EPS).mean()) <= 0.25:
        return False, R
    return True, R


def rules_made_to_lean(t0: list[Track], t1: list[Track], d: float) -> list[tuple[float, float, float]]:
    """A TURN THE PRINT REFUSES: a printed rule across the text (a head rule, a rule over the footnotes, a table's),
    half the block wide or more, read alike in both views (its angle moved by the turn within 0.15 deg), that the turn
    leaves beyond 0.35 deg and at least 0.25 deg more tilted than it was. A rule is the print's straightest line: a turn
    that makes one lean has made a new tilt (a leaf whose head stands level and whose foot does not has no single turn).
    -> those rules [(y, before, after)]"""
    out = []
    for t in t0:
        if not (_read_well(t) and t[5] and t[2] >= 0.5):
            continue
        m_ = [u for u in t1 if _read_well(u) and u[5] and abs(u[0] - t[0]) <= 6]
        if not m_:
            continue
        u = min(m_, key=lambda u: abs(u[0] - t[0]))
        after = t[1] - d
        if abs(u[1] - after) <= 0.15 + EPS and abs(after) > 0.35 + EPS and abs(after) >= abs(t[1]) + 0.25 - EPS:
            out.append((t[0], t[1], round(after, 3)))
    return out


def _frame(mk: dict) -> tuple | None:
    """the closed printed frame round the text block: (left side, right side, top rules, bottom rules) or None"""
    a, z, paper, tb = mk.get("img"), mk.get("z"), mk.get("paper"), mk.get("text")
    if a is None or tb is None or not paper or not z:
        return None
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    if tw <= 0 or th <= 0:
        return None
    R = mk.get("rules") or []
    V = [b for b in R if b[3] - b[1] > b[2] - b[0] and b[3] - b[1] >= 0.7 * th]
    L = [b for b in V if b[2] <= tb[0] + 0.02 * tw]
    Rt = [b for b in V if b[0] >= tb[2] - 0.02 * tw]
    Hz = [b for b in R if b[2] - b[0] >= b[3] - b[1] and b[2] - b[0] >= 0.7 * tw]
    T = [b for b in Hz if b[3] <= tb[1] + 0.05 * th]
    B = [b for b in Hz if b[1] >= tb[3] - 0.05 * th]
    if not L or not Rt or not T or not B:
        return None
    return max(L, key=lambda b: b[3] - b[1]), max(Rt, key=lambda b: b[3] - b[1]), T, B


def frame_lean(mk: dict) -> float | None:
    """THE PRINTED FRAME AS THE STANDARD OF TILT: on a page whose text stands inside a closed printed frame, the mean lean
    of the frame's two sides, each followed row by row (letters touching it skipped) and fitted by a line on >= 80 % of
    its rows; each side's halves within 0.6 deg (a bent side is no standard) and the two sides within 0.4 deg.
    -> lean in degrees (the turn that levels it is its negative), or None"""
    fr = _frame(mk)
    if fr is None:
        return None
    a, z, paper = mk["img"], mk["z"], mk["paper"]
    ls, rs = fr[0], fr[1]

    def lean(b: list, part: tuple[float, float]) -> float | None:
        x0, y0, x1, y1 = [int(round(v * z)) for v in b]
        pad = int(6 * z)
        sub = a[y0:y1, max(0, x0 - pad):x1 + pad] < paper - 80
        r0, r1 = int(sub.shape[0] * part[0]), int(sub.shape[0] * part[1])
        rows, xs = [], []
        for r in range(r0, r1):
            c = np.nonzero(sub[r])[0]
            if len(c) >= 2 and c[-1] - c[0] <= 14 * z:
                rows.append(r)
                xs.append((c[0] + c[-1]) / 2)
        if len(rows) < 30 or len(rows) < 0.8 * (r1 - r0):
            return None
        return float(np.degrees(np.arctan(np.polyfit(rows, xs, 1)[0])))

    out = []
    for b in (ls, rs):
        w, t, u = lean(b, (0.0, 1.0)), lean(b, (0.0, 0.5)), lean(b, (0.5, 1.0))
        if w is None or t is None or u is None or abs(t - u) > 0.6 + EPS:
            return None
        out.append(w)
    if abs(out[0] - out[1]) > 0.4 + EPS:
        return None
    return round(float(np.mean(out)), 3)


def frame_shear(mk: dict, pad: float = 8.0) -> tuple[float, float, float] | None:
    """A SHEARED PRINT: the frame's sides stand upright but its top and bottom rules (and the lines with them) still lean,
    a parallelogram no turn squares. The lean of the two rules, each read column by column on its outer edge between the
    sides, fitted robustly on >= 60 % of the columns; halves within 0.6 deg and the two rules within 0.4 deg of each other
    (a warped or keystoned leaf has no common lean a shear could level). -> (mean, top, bottom) or None"""
    fr = _frame(mk)
    if fr is None:
        return None
    a, z, paper, tb = mk["img"], mk["z"], mk["paper"], mk["text"]
    tw = tb[2] - tb[0]
    ls, rs, T, B = fr

    def lean(b: list, part: tuple[float, float], top: bool) -> float | None:
        x0, x1 = max(b[0], ls[2] + 2.0), min(b[2], rs[0] - 2.0)
        if x1 - x0 < 0.5 * tw:
            return None
        X0, X1 = int(round(x0 * z)), int(round(x1 * z))
        pd = int(pad * z)
        Y0, Y1 = max(0, int(round(b[1] * z)) - pd), int(round(b[3] * z)) + pd
        sub = a[Y0:Y1, X0:X1] < paper - 80
        c0, c1 = int(sub.shape[1] * part[0]), int(sub.shape[1] * part[1])
        cols, ys = [], []
        for c in range(c0, c1):
            r = np.nonzero(sub[:, c])[0]
            if len(r) < 2:
                continue
            cuts = np.nonzero(np.diff(r) > 1)[0] + 1
            rr = [s for s in np.split(r, cuts) if len(s) >= 2]
            if not rr:
                continue
            cols.append(c)
            ys.append(float(min(s[0] for s in rr) if top else max(s[-1] for s in rr)))
        if len(cols) < 30:
            return None
        cols_, ys_ = np.array(cols, float), np.array(ys)
        h = len(cols_) // 2
        xl, xr, yl, yr = np.median(cols_[:h]), np.median(cols_[h:]), np.median(ys_[:h]), np.median(ys_[h:])
        if xr - xl < 1:
            return None
        k0 = (yr - yl) / (xr - xl)
        ok = np.abs(ys_ - (yl + k0 * (cols_ - xl))) <= 3
        if ok.sum() < 30 or ok.sum() < 0.6 * (c1 - c0):
            return None
        k = np.polyfit(cols_[ok], ys_[ok], 1)[0]
        return -float(np.degrees(np.arctan(k)))

    out = []
    for b, top in ((max(T, key=lambda b: b[2] - b[0]), True), (max(B, key=lambda b: b[2] - b[0]), False)):
        w, left, right = lean(b, (0.0, 1.0), top), lean(b, (0.0, 0.5), top), lean(b, (0.5, 1.0), top)
        if w is None or left is None or right is None or abs(left - right) > 0.6 + EPS:
            return None
        out.append(w)
    if abs(out[0] - out[1]) > 0.4 + EPS:
        return None
    return round(float(np.mean(out)), 3), round(out[0], 3), round(out[1], 3)
