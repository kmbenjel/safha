"""Lossless PDF operations. Nothing here decodes or re-encodes an image.

A scanned page holds an image (the scan) and drawing instructions (where to draw it, which part to show). safha only
changes the instructions:

* the page's **CropBox** (the part shown; what lies outside stays in the file);
* for a turned, sheared, moved or scaled page, one content stream ``q a b c d e f cm`` before the page's own content and
  one ``Q`` after it, so the reader draws the same image turned. The image streams, the text layer and everything else
  stay byte for byte.

Two frames are in play. The method measures a page **as it is shown** (page coordinates: points from the shown page's top
left corner, y downward), whatever the file does to show it that way: a ``/Rotate`` entry (a scan stored sideways), a
``/UserUnit``, a CropBox inside the MediaBox. The file is written in **PDF coordinates** (y upward, the page as stored).
``display_matrix`` is the map from the second to the first, and every box and matrix written goes through it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

import numpy as np
import pymupdf


def gray(page: pymupdf.Page, px: int) -> tuple[np.ndarray, float]:
    """the page rendered in gray, ``px`` pixels wide -> (array, pixels per pt)"""
    z = px / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csGRAY, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, : pix.width]
    return a, z


def _numbers(doc: pymupdf.Document, text: str) -> list[float] | None:
    """the numbers of a PDF array as text (``[0 0 595.28 841.89]``); a number written as an indirect object
    (``12 0 R``) is looked up. None when the text is no array of numbers"""
    tok = text.strip().strip("[]").split()
    out: list[float] = []
    k = 0
    try:
        while k < len(tok):
            if k + 2 < len(tok) and tok[k + 2] == "R":
                out.append(float(doc.xref_object(int(tok[k]), compressed=True)))
                k += 3
            else:
                out.append(float(tok[k]))
                k += 1
    except (ValueError, RuntimeError):
        return None
    return out


def raw_box(doc: pymupdf.Document, xref: int, key: str) -> list[float] | None:
    """a page's own or inherited box (``MediaBox``, ``CropBox``) as numbers, in PDF coordinates: [left, bottom, right,
    top] whatever order its corners were written in. The box may be written in the page, in a parent of the page tree,
    or as an indirect object. None when there is none (or it cannot be read)"""
    for _ in range(64):  # (a page tree is never that deep: a loop in a damaged file ends here)
        if not xref:
            break
        t, v = doc.xref_get_key(xref, key)
        if t == "xref":  # the box is an object of its own
            v = doc.xref_object(int(v.split()[0]), compressed=True)
            t = "array" if v.lstrip().startswith("[") else "null"
        if t == "array":
            a = _numbers(doc, v)
            if a is None or len(a) != 4:
                return None
            return [min(a[0], a[2]), min(a[1], a[3]), max(a[0], a[2]), max(a[1], a[3])]
        t, par = doc.xref_get_key(xref, "Parent")
        xref = int(par.split()[0]) if t == "xref" else 0
    return None


def media_box(page: pymupdf.Page) -> list[float]:
    """the page's MediaBox in PDF coordinates (as MuPDF reads it when the file gives none that can be read)"""
    mb = raw_box(page.parent, page.xref, "MediaBox")
    if mb is None:
        r = page.mediabox
        mb = [r.x0, r.y0, r.x1, r.y1]
    return mb


def user_unit(page: pymupdf.Page) -> float:
    """the page's ``/UserUnit``: the size of one unit of its coordinates in points (1 unless the file says otherwise)"""
    t, v = page.parent.xref_get_key(page.xref, "UserUnit")
    try:
        u = float(v) if t in ("int", "float", "real") else 1.0
    except ValueError:
        u = 1.0
    return u if u > 0 else 1.0


def plain(page: pymupdf.Page) -> bool:
    """a page shown as it is stored: no ``/Rotate``, one unit one point"""
    return not page.rotation and user_unit(page) == 1.0


def display_matrix(page: pymupdf.Page) -> pymupdf.Matrix:
    """PDF coordinates -> the page as it is shown (points from its top left corner, y downward), the page's ``/Rotate``
    and ``/UserUnit`` included: what a reader draws. For a plain page it is PyMuPDF's ``transformation_matrix``"""
    if plain(page):
        return page.transformation_matrix
    mb = media_box(page)
    cb = raw_box(page.parent, page.xref, "CropBox")
    box = mb if cb is None else [max(cb[0], mb[0]), max(cb[1], mb[1]), min(cb[2], mb[2]), min(cb[3], mb[3])]
    if box[2] - box[0] <= 0 or box[3] - box[1] <= 0:
        box = mb
    u = user_unit(page)
    c, s = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}.get(page.rotation, (1, 0))  # of minus the rotation
    m = pymupdf.Matrix(c, s, -s, c, 0, 0) * pymupdf.Matrix(u, 0, 0, -u, 0, 0)
    xs = [x * m.a + y * m.c for x in (box[0], box[2]) for y in (box[1], box[3])]
    ys = [x * m.b + y * m.d for x in (box[0], box[2]) for y in (box[1], box[3])]
    return m * pymupdf.Matrix(1, 0, 0, 1, -min(xs), -min(ys))


def shown_as_computed(page: pymupdf.Page) -> bool:
    """the page is shown where ``display_matrix`` says: its box, mapped, is the rectangle MuPDF gives the page. (A page
    for which this does not hold is not measured: it is shown whole.)"""
    if plain(page):
        return True
    m = display_matrix(page)
    mb = media_box(page)
    cb = raw_box(page.parent, page.xref, "CropBox")
    box = mb if cb is None else [max(cb[0], mb[0]), max(cb[1], mb[1]), min(cb[2], mb[2]), min(cb[3], mb[3])]
    pts = [pymupdf.Point(x, y) * m for x in (box[0], box[2]) for y in (box[1], box[3])]
    r = page.rect
    return (abs(min(q.x for q in pts) - r.x0) < 0.05 and abs(min(q.y for q in pts) - r.y0) < 0.05
            and abs(max(q.x for q in pts) - r.x1) < 0.05 and abs(max(q.y for q in pts) - r.y1) < 0.05)


def _linear(m: pymupdf.Matrix) -> pymupdf.Matrix:
    return pymupdf.Matrix(m.a, m.b, m.c, m.d, 0, 0)


def turn_cm(doc: pymupdf.Document, page: pymupdf.Page, deg: float, dx: float = 0.0, dy: float = 0.0,
            shear: float = 0.0) -> bytes:
    """the ``q ... cm`` line that draws the page's content turned by ``deg`` degrees about the MediaBox centre, its rows
    (as shown) then tilted by ``shear`` degrees (y' = y + tan(shear)(x - cx); the columns stay upright), then moved by
    (dx, dy) pt (page coordinates: dy > 0 moves down)"""
    if not plain(page):
        m = frame_matrix(page, {"skew": deg, "shear": shear, "move": [dx, dy]})
        return f"q {m.a + 0.0:.6f} {m.b + 0.0:.6f} {m.c + 0.0:.6f} {m.d + 0.0:.6f} {m.e + 0.0:.4f} {m.f + 0.0:.4f} cm\n".encode()
    mb = media_box(page)
    cx, cy = (mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    k = math.tan(math.radians(shear)) if shear else 0.0
    b, d = s + k * c, c - k * s
    e, f = cx - c * cx + s * cy + dx, cy - b * cx - d * cy - dy
    return f"q {c:.6f} {b:.6f} {-s:.6f} {d:.6f} {e:.4f} {f:.4f} cm\n".encode()


def wrap_contents(doc: pymupdf.Document, page: pymupdf.Page, pre: bytes, post: bytes = b"\nQ\n") -> bool:
    """one new stream ``pre`` (opening with ``q``) before the page's content and one after it (``Q``, unless ``post``
    says more). False when the page has no content to wrap"""
    ta, v = doc.xref_get_key(page.xref, "Contents")
    if ta == "xref":
        x = int(v.split()[0])
        body = doc.xref_object(x).strip()
        old = body[1:-1] if body.startswith("[") else v
    elif ta == "array":
        old = v.strip()[1:-1]
    else:
        return False
    xa = doc.get_new_xref()
    doc.update_object(xa, "<<>>")
    doc.update_stream(xa, pre)
    xb = doc.get_new_xref()
    doc.update_object(xb, "<<>>")
    doc.update_stream(xb, post)
    doc.xref_set_key(page.xref, "Contents", f"[{xa} 0 R {old} {xb} 0 R]")
    return True


def rotate_contents(doc: pymupdf.Document, page: pymupdf.Page, deg: float, dx: float = 0.0, dy: float = 0.0,
                    shear: float = 0.0) -> bool:
    """lossless deskew / shear / move of a page's whole content"""
    return wrap_contents(doc, page, turn_cm(doc, page, deg, dx, dy, shear))


def frame_matrix(page: pymupdf.Page, p: dict) -> pymupdf.Matrix:
    """the reader's frame of a page as recipe entry ``p`` draws it (turn, shear, move), as a PDF-coordinate matrix: the
    same map turn_cm writes into the content stream"""
    mv = p.get("move") or [0, 0]
    deg, sh = p.get("skew") or 0, p.get("shear") or 0
    mb = media_box(page)
    cx, cy = (mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2
    fwd = pymupdf.Matrix(1, 0, 0, 1, -cx, -cy) * pymupdf.Matrix(deg)
    if plain(page):
        if sh:
            fwd = fwd * pymupdf.Matrix(1, math.tan(math.radians(sh)), 0, 1, 0, 0)
        return fwd * pymupdf.Matrix(1, 0, 0, 1, cx, cy) * pymupdf.Matrix(1, 0, 0, 1, mv[0], -mv[1])
    # a page stored sideways or in another unit: the shear and the move are those of the page as shown
    lin = _linear(display_matrix(page))
    if sh:
        fwd = fwd * lin * pymupdf.Matrix(1, -math.tan(math.radians(sh)), 0, 1, 0, 0) * ~lin
    d = pymupdf.Point(mv[0], mv[1]) * ~lin
    return fwd * pymupdf.Matrix(1, 0, 0, 1, cx, cy) * pymupdf.Matrix(1, 0, 0, 1, d.x, d.y)


def sheet_corners(page: pymupdf.Page, p: dict) -> list[tuple[float, float]]:
    """the four corners of the scan's sheet (the page's MediaBox) as recipe entry ``p`` draws it, in page coordinates,
    in order round the sheet: beyond them a turned page shows nothing, where the scanner's bed went on"""
    mb = media_box(page)
    m = frame_matrix(page, p) * display_matrix(page)
    pts = [pymupdf.Point(x, y) * m for x, y in ((mb[0], mb[3]), (mb[2], mb[3]), (mb[2], mb[1]), (mb[0], mb[1]))]
    return [(q.x, q.y) for q in pts]


def beyond_sheet(shape: tuple[int, int], corners: Sequence[tuple[float, float]], z: float,
                 sides: Sequence[bool]) -> np.ndarray | None:
    """the pixels of a view (``shape``, ``z`` px per pt) that lie beyond the scan's sheet (``sheet_corners``) on the
    given sides of the view (left, top, right, bottom); None when there are none"""
    H, W = shape
    cx, cy = sum(c[0] for c in corners) / 4 * z, sum(c[1] for c in corners) / 4 * z
    xs, ys = np.arange(W, dtype=np.float32) + 0.5, np.arange(H, dtype=np.float32) + 0.5
    out = np.zeros(shape, bool)
    for k in range(4):
        (x0, y0), (x1, y1) = [(c[0] * z, c[1] * z) for c in (corners[k], corners[(k + 1) % 4])]
        mx, my = (x0 + x1) / 2 - cx, (y0 + y1) / 2 - cy  # from the sheet's centre to this edge
        side = (0 if mx < 0 else 2) if abs(mx) > abs(my) else (1 if my < 0 else 3)
        if not sides[side]:
            continue
        nx, ny = y1 - y0, x0 - x1  # the edge's normal, turned to point away from the centre
        n = math.hypot(nx, ny)
        if n == 0:
            continue
        if nx * mx + ny * my < 0:
            nx, ny = -nx, -ny
        out |= ((xs[None, :] - x0) * (nx / n) + (ys[:, None] - y0) * (ny / n)) > 0
    return out if out.any() else None


def as_scanned(p: dict) -> bool:
    mv = p.get("move") or [0, 0]
    return not (p.get("skew") or 0) and not (p.get("shear") or 0) and not any(mv)


def fwd_boxes(page: pymupdf.Page, p: dict, bs: Sequence[Sequence[float]]) -> list[list[float]]:
    """boxes of the page as scanned (page coordinates) as they lie in the reader's frame (bounding boxes)"""
    if as_scanned(p):
        return [list(b) for b in bs]
    tm = display_matrix(page)
    m = ~tm * frame_matrix(page, p) * tm
    out = []
    for b in bs:
        pts = [pymupdf.Point(x, y) * m for x, y in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        out.append([min(q.x for q in pts), min(q.y for q in pts), max(q.x for q in pts), max(q.y for q in pts)])
    return out


def back_to_scan(page: pymupdf.Page, p: dict):
    """maps points of the reader's frame back onto the page as scanned (to draw the box on the scan)"""
    tm = display_matrix(page)
    m = ~tm * ~frame_matrix(page, p) * tm
    return lambda x, y: pymupdf.Point(x, y) * m


def turned(doc: pymupdf.Document, i: int, deg: float = 0.0, dx: float = 0.0, dy: float = 0.0,
           shear: float = 0.0) -> pymupdf.Document:
    """page ``i`` alone in a new document, drawn turned / sheared / moved"""
    t = pymupdf.open()
    t.insert_pdf(doc, from_page=i, to_page=i)
    if deg or dx or dy or shear:
        rotate_contents(t, t[0], deg, dx, dy, shear)
    return t


class Turner:
    """one page drawn at many angles: a single one-page document whose ``cm`` stream is rewritten for each view, so the
    scan is decoded once instead of once per angle"""

    def __init__(self, doc: pymupdf.Document, i: int):
        self.t = pymupdf.open()
        self.t.insert_pdf(doc, from_page=i, to_page=i)
        self.plain = self.t.xref_get_key(self.t[0].xref, "Contents")[1]
        self.xa: int | None = None
        self.wrapped: str | None = None

    def page(self, deg: float = 0.0, dx: float = 0.0, dy: float = 0.0, shear: float = 0.0) -> pymupdf.Page:
        t = self.t
        pg = t[0]
        if not (deg or dx or dy or shear):
            if self.xa is not None:
                t.xref_set_key(pg.xref, "Contents", self.plain)
        elif self.xa is not None:
            t.update_stream(self.xa, turn_cm(t, pg, deg, dx, dy, shear))
            t.xref_set_key(pg.xref, "Contents", self.wrapped)
        elif wrap_contents(t, pg, turn_cm(t, pg, deg, dx, dy, shear)):
            self.wrapped = t.xref_get_key(pg.xref, "Contents")[1]
            self.xa = int(self.wrapped.strip("[] ").split()[0])
        return t[0]

    def close(self) -> None:
        self.t.close()


def images_of(doc: pymupdf.Document) -> list[list[tuple[int, int, int, str]]]:
    """per page: (xref, width, height, md5 of the raw, still-compressed stream) of every image it draws"""
    out = []
    for p in doc:
        row = []
        for x in p.get_images(full=True):
            raw = doc.xref_stream_raw(x[0]) or b""
            row.append((x[0], x[2], x[3], hashlib.md5(raw).hexdigest()))
        out.append(row)
    return out


def image_filters(doc: pymupdf.Document) -> dict[str, int]:
    """how many image streams use each filter (``DCTDecode``, ``JBIG2Decode``, ``CCITTFaxDecode``, ...)"""
    out: dict[str, int] = {}
    seen: set[int] = set()
    for p in doc:
        for x in p.get_images(full=True):
            if x[0] in seen:
                continue
            seen.add(x[0])
            k = x[8] if len(x) > 8 and x[8] else "none"
            for f in str(k).replace("[", " ").replace("]", " ").split():
                out[f.lstrip("/")] = out.get(f.lstrip("/"), 0) + 1
    return out


def split_pages(doc: pymupdf.Document, split: dict, rtl: bool = False) -> None:
    """each sheet of ``split`` ({index: gutter x in pt, page coordinates}) becomes two pages, the same content shown
    through two CropBoxes (images shared, never copied). LTR: the left page first; RTL: the right page first. In place"""
    for i in sorted((int(k) for k in split), reverse=True):
        g = float(split[str(i)] if str(i) in split else split[i])
        page = doc[i]
        if plain(page):
            inv = ~page.transformation_matrix
            cb = raw_box(doc, page.xref, "CropBox") or media_box(page)
            a, b = pymupdf.Point(g, 0) * inv, pymupdf.Point(g, page.rect.height) * inv
            gx = (a.x + b.x) / 2
            left, right = [cb[0], cb[1], gx, cb[3]], [gx, cb[1], cb[2], cb[3]]
            nd = 2
        else:  # a sheet stored sideways: the two halves of the sheet as shown, each back in PDF coordinates
            inv = ~display_matrix(page)
            w, h = page.rect.width, page.rect.height

            def half(x0: float, x1: float) -> list[float]:
                pts = [pymupdf.Point(x, y) * inv for x in (x0, x1) for y in (0, h)]
                return [min(q.x for q in pts), min(q.y for q in pts), max(q.x for q in pts), max(q.y for q in pts)]

            left, right = half(0, g), half(g, w)
            nd = 4
        doc.fullcopy_page(i, i + 1 if i + 1 < doc.page_count else -1)
        first, second = (right, left) if rtl else (left, right)
        doc.xref_set_key(doc[i].xref, "CropBox", "[%s]" % " ".join(f"{v:.{nd}f}" for v in first))
        doc.xref_set_key(doc[i + 1].xref, "CropBox", "[%s]" % " ".join(f"{v:.{nd}f}" for v in second))


def open_book(path: str, rec: dict | None = None) -> pymupdf.Document:
    """the book as the method sees it: split first (in memory) when the recipe says so, pages dropped"""
    doc = pymupdf.open(path)
    if rec and rec.get("split"):
        split_pages(doc, rec["split"], rec.get("direction") == "rtl")
    return doc


def text_direction(doc: pymupdf.Document, pages: int = 12) -> str | None:
    """``rtl`` when the text layer (if any) is mostly Arabic, Hebrew, Syriac or Thaana script, ``ltr`` when mostly another
    script, None without a text layer"""
    rtl = ltr = 0
    for i in range(min(pages, doc.page_count)):
        for ch in doc[min(doc.page_count - 1, i * max(1, doc.page_count // pages))].get_text("text"):
            o = ord(ch)
            if 0x0590 <= o <= 0x08FF or 0xFB1D <= o <= 0xFEFC:
                rtl += 1
            elif ch.isalpha():
                ltr += 1
    if rtl + ltr < 50:
        return None
    return "rtl" if rtl > ltr else "ltr"
