"""APPLY: a recipe written into a copy of the book, losslessly, then checked.

Per page: the CropBox (exactly the book's size W x H on every page) and, for a turned, sheared, moved or scaled page,
``q ... cm`` / ``Q`` pairs around its content. The copy is saved as an incremental update: the original file's bytes stay
at its start, so ``restore`` gives the original back by truncation (its MD5 is checked). Checked after saving: the same
pages, every image stream byte for byte the same, every page the same size.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

import pymupdf

from .engine import file_md5
from .geometry import union
from .pdf import images_of, raw_box, rotate_contents, split_pages, wrap_contents

MARK = "SafhaOriginal"


class ApplyError(RuntimeError):
    pass


def _box(v: list[float]) -> str:
    return "[%s]" % " ".join(f"{x:.2f}" for x in v)


def apply_recipe(src: str, rec: dict, dst: str, compact: bool = False, check_source: bool = True) -> dict[str, Any]:
    """write ``rec`` into a copy of ``src`` at ``dst`` -> a report (pages, cropped, turned, bytes in and out)"""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ApplyError("the output must be a new file: the original is never changed")
    if check_source and rec.get("source", {}).get("md5") and file_md5(src) != rec["source"]["md5"]:
        raise ApplyError(f"{src} is not the file this recipe was made from (MD5 differs); re-run `safha plan`")
    n_in = os.path.getsize(src)
    mode = rec.get("mode")
    shutil.copyfile(src, dst)
    before = pymupdf.open(src)
    imgs = images_of(before)
    before.close()
    doc = pymupdf.open(dst)
    if not doc.can_save_incrementally():
        compact = True
    split = rec.get("split") or {}
    if split:
        split_pages(doc, split, rec.get("direction") == "rtl")
        expect = []
        for i, im in enumerate(imgs):
            expect.append(im)
            if str(i) in split:
                expect.append(im)
        imgs = expect
    if len(rec["pages"]) != doc.page_count:
        doc.close()
        raise ApplyError(f"the recipe has {len(rec['pages'])} pages, the book {doc.page_count}")
    done = turned_n = scaled_n = 0
    if mode in ("crop", "level"):
        W, H = rec.get("size") or (None, None)
        for i, p in enumerate(rec["pages"]):
            page = doc[i]
            inv = ~page.transformation_matrix
            mb = raw_box(doc, page.xref, "MediaBox")
            if mode == "level":
                if p.get("skew") or p.get("shear"):
                    rotate_contents(doc, page, p.get("skew") or 0, shear=p.get("shear") or 0)
                    turned_n += 1
                c = p.get("crop")
                if c:
                    a, b = pymupdf.Point(c[0], c[1]) * inv, pymupdf.Point(c[2], c[3]) * inv
                    doc.xref_set_key(page.xref, "CropBox", _box([min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)]))
                    done += 1
                continue
            if p.get("fit_whole"):  # a page turned by /Rotate: all of it, fitted
                cb = raw_box(doc, page.xref, "CropBox") or mb
                clip = [max(cb[0], mb[0]), max(cb[1], mb[1]), min(cb[2], mb[2]), min(cb[3], mb[3])]
                tw, th = (W, H) if page.rotation % 180 == 0 else (H, W)
                s = min(tw / (clip[2] - clip[0]), th / (clip[3] - clip[1]))
                cx, cy = (clip[0] + clip[2]) / 2, (clip[1] + clip[3]) / 2
            elif p.get("show"):
                mv = p.get("move") if p.get("crop") else None
                if p.get("skew") or mv or p.get("shear"):
                    rotate_contents(doc, page, p.get("skew") or 0, *(mv or [0, 0]), shear=p.get("shear") or 0)
                    turned_n += 1
                R = p["show"]
                a, b = pymupdf.Point(R[0], R[1]) * inv, pymupdf.Point(R[2], R[3]) * inv
                cx, cy = (a.x + b.x) / 2, (a.y + b.y) / 2
                s = p["scale"]
                tw, th = W, H
                clip = None
                if p.get("bands"):
                    r0, r1 = pymupdf.Point(0, 0) * inv, pymupdf.Point(page.rect.width, page.rect.height) * inv
                    clip = [min(r0.x, r1.x), min(r0.y, r1.y), max(r0.x, r1.x), max(r0.y, r1.y)]
            else:
                continue
            if abs(s - 1) > 1e-6 or clip:  # drawn s times its size about the shown part's centre
                pre = f"q {s:.6f} 0 0 {s:.6f} {cx * (1 - s):.4f} {cy * (1 - s):.4f} cm\n"
                if clip:
                    pre += f"{clip[0]:.4f} {clip[1]:.4f} {clip[2] - clip[0]:.4f} {clip[3] - clip[1]:.4f} re W n\n"
                wrap_contents(doc, page, pre.encode())
                scaled_n += 1
            x0, y0 = round(cx - tw / 2, 2), round(cy - th / 2, 2)
            T = [x0, y0, round(x0 + tw, 2), round(y0 + th, 2)]
            if T[0] < mb[0] - 1e-3 or T[1] < mb[1] - 1e-3 or T[2] > mb[2] + 1e-3 or T[3] > mb[3] + 1e-3:
                doc.xref_set_key(page.xref, "MediaBox", _box(union([mb, T])))
            doc.xref_set_key(page.xref, "CropBox", _box(T))
            done += 1
    drop = sorted({int(k) for k in rec.get("drop") or []}, reverse=True)
    for k in drop:
        if not 1 <= k <= doc.page_count:
            doc.close()
            raise ApplyError(f"page {k} to drop is not in the book")
    if drop:
        doc.delete_pages([k - 1 for k in drop])
        imgs = [im for j, im in enumerate(imgs) if j + 1 not in drop]
    md5 = rec.get("source", {}).get("md5") or file_md5(src)
    if not compact:
        doc.xref_set_key(doc.pdf_catalog(), MARK, f"<</Bytes {n_in}/MD5({md5})>>")
        doc.save(dst, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    else:
        tmp = dst + ".tmp"
        doc.save(tmp, garbage=3, deflate=False, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        doc.close()
        os.replace(tmp, dst)
        doc = None
    if doc is not None:
        doc.close()
    # -- checks ----------------------------------------------------------------------------------------------------
    chk = pymupdf.open(dst)
    try:
        if chk.page_count != len(imgs):
            raise ApplyError(f"page count changed: {chk.page_count}, expected {len(imgs)}")
        got = images_of(chk)
        same = [[x[1:] for x in row] for row in got] == [[x[1:] for x in row] for row in imgs]
        if not same:
            raise ApplyError("an image stream changed: refusing the output")
        if mode == "crop":
            W, H = rec["size"]
            off = sorted({(round(pg.rect.width, 2), round(pg.rect.height, 2)) for pg in chk
                          if abs(pg.rect.width - W) > 0.02 or abs(pg.rect.height - H) > 0.02})
            if off:
                raise ApplyError(f"pages of different sizes: {off[:4]} (the book: {W} x {H})")
    finally:
        chk.close()
    if not compact:
        with open(dst, "rb") as f, open(src, "rb") as g:
            if f.read(n_in) != g.read():
                raise ApplyError("the output does not start with the original bytes")
    return {"pages": len(imgs), "cropped": done, "turned": turned_n, "scaled": scaled_n, "dropped": len(drop),
            "bytes_in": n_in, "bytes_out": os.path.getsize(dst), "reversible": not compact}


def restore(path: str, dst: str) -> dict[str, Any]:
    """the original file back from a safha output (incremental, not ``--compact``): truncated, MD5 checked"""
    doc = pymupdf.open(path)
    t, v = doc.xref_get_key(doc.pdf_catalog(), MARK)
    doc.close()
    if t != "dict":
        raise ApplyError(f"{path} carries no safha restore mark (made with --compact, or not by safha)")
    import re

    m = re.search(r"/Bytes\s+(\d+)", v)
    h = re.search(r"/MD5\s*\(([0-9a-f]{32})\)", v)
    if not m or not h:
        raise ApplyError("unreadable restore mark")
    n = int(m.group(1))
    with open(path, "rb") as f:
        data = f.read(n)
    import hashlib

    if hashlib.md5(data).hexdigest() != h.group(1):
        raise ApplyError("the first bytes do not match the original's MD5: the file was changed after safha")
    if os.path.abspath(path) == os.path.abspath(dst):
        raise ApplyError("write the original to a new file")
    with open(dst, "wb") as f:
        f.write(data)
    return {"bytes": n, "md5": h.group(1)}
