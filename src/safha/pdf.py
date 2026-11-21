"""Lossless PDF operations. Nothing here decodes or re-encodes an image.

A scanned page holds an image (the scan) and drawing instructions (where to draw it, which part to show). safha only
changes the instructions:

* the page's **CropBox** (the part shown; what lies outside stays in the file);
* for a turned, sheared, moved or scaled page, one content stream ``q a b c d e f cm`` before the page's own content and
  one ``Q`` after it, so the reader draws the same image turned. The image streams, the text layer and everything else
  stay byte for byte.
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


def turn_cm(doc: pymupdf.Document, page: pymupdf.Page, deg: float, dx: float = 0.0, dy: float = 0.0,
            shear: float = 0.0) -> bytes:
    """the ``q ... cm`` line that draws the page's content turned by ``deg`` degrees about the MediaBox centre, its rows
    then tilted by ``shear`` degrees (y' = y + tan(shear)(x - cx); the columns stay upright), then moved by (dx, dy) pt
    (page coordinates: dy > 0 moves down)"""
    mb = media_box(page)
    cx, cy = (mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    k = math.tan(math.radians(shear)) if shear else 0.0
    b, d = s + k * c, c - k * s
    e, f = cx - c * cx + s * cy + dx, cy - b * cx - d * cy - dy
    return f"q {c:.6f} {b:.6f} {-s:.6f} {d:.6f} {e:.4f} {f:.4f} cm\n".encode()


def wrap_contents(doc: pymupdf.Document, page: pymupdf.Page, pre: bytes) -> bool:
    """one new stream ``pre`` (opening with ``q``) before the page's content and one ``Q`` after it"""
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
    doc.update_stream(xb, b"\nQ\n")
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
    if sh:
        fwd = fwd * pymupdf.Matrix(1, math.tan(math.radians(sh)), 0, 1, 0, 0)
    return fwd * pymupdf.Matrix(1, 0, 0, 1, cx, cy) * pymupdf.Matrix(1, 0, 0, 1, mv[0], -mv[1])


def as_scanned(p: dict) -> bool:
    mv = p.get("move") or [0, 0]
    return not (p.get("skew") or 0) and not (p.get("shear") or 0) and not any(mv)


def fwd_boxes(page: pymupdf.Page, p: dict, bs: Sequence[Sequence[float]]) -> list[list[float]]:
    """boxes of the page as scanned (page coordinates) as they lie in the reader's frame (bounding boxes)"""
    if as_scanned(p):
        return [list(b) for b in bs]
    tm = page.transformation_matrix
    m = ~tm * frame_matrix(page, p) * tm
    out = []
    for b in bs:
        pts = [pymupdf.Point(x, y) * m for x, y in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        out.append([min(q.x for q in pts), min(q.y for q in pts), max(q.x for q in pts), max(q.y for q in pts)])
    return out


def back_to_scan(page: pymupdf.Page, p: dict):
    """maps points of the reader's frame back onto the page as scanned (to draw the box on the scan)"""
    tm = page.transformation_matrix
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
        inv = ~page.transformation_matrix
        cb = raw_box(doc, page.xref, "CropBox") or media_box(page)
        a, b = pymupdf.Point(g, 0) * inv, pymupdf.Point(g, page.rect.height) * inv
        gx = (a.x + b.x) / 2
        doc.fullcopy_page(i, i + 1 if i + 1 < doc.page_count else -1)
        first, second = ([gx, cb[1], cb[2], cb[3]], [cb[0], cb[1], gx, cb[3]]) if rtl else \
            ([cb[0], cb[1], gx, cb[3]], [gx, cb[1], cb[2], cb[3]])
        doc.xref_set_key(doc[i].xref, "CropBox", "[%s]" % " ".join(f"{v:.2f}" for v in first))
        doc.xref_set_key(doc[i + 1].xref, "CropBox", "[%s]" % " ".join(f"{v:.2f}" for v in second))


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
