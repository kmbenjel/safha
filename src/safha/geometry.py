"""Small helpers on boxes: a box is ``[x0, y0, x1, y1]`` in PDF points, page coordinates (y grows downward)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

Box = list[float]


def inside(b: Sequence[float], box: Sequence[float], tol: float = 0.5) -> bool:
    """``b`` lies within ``box`` (each side may stick out by ``tol``)."""
    return b[0] >= box[0] - tol and b[1] >= box[1] - tol and b[2] <= box[2] + tol and b[3] <= box[3] + tol


def union(bs: Iterable[Sequence[float]]) -> Box:
    bs = list(bs)
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    i = (x1 - x0) * (y1 - y0)
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def quantile(vals: Iterable[float], f: float) -> float:
    """the value at share ``f`` of the sorted values (nearest rank)"""
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round(f * (len(s) - 1)))))]


def shift(b: Sequence[float], dx: float, dy: float) -> Box:
    return [b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy]


def rnd(b: Sequence[float] | None, nd: int = 1) -> Box | None:
    return None if b is None else [round(float(v), nd) for v in b]


def thin_line(b: Sequence[float], w: float, h: float) -> bool:
    """a rule or a scan line, not a letter: at most 0.4 % of the page thick and at least 3 % long, either way"""
    bw, bh = b[2] - b[0], b[3] - b[1]
    return (bh <= 0.004 * h and bw >= 0.03 * w) or (bw <= 0.004 * w and bh >= 0.03 * h)
