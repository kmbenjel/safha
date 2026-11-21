"""APPLY: a recipe written into a copy of the book, losslessly, then checked.

Per page: the CropBox (exactly the book's size W x H on every page) and, for a turned, sheared, moved or scaled page,
``q ... cm`` / ``Q`` pairs around its content. The copy is saved as an incremental update: the original file's bytes stay
at its start, so ``restore`` gives the original back by truncation (its MD5 is checked). Checked after saving: the same
pages, every image stream byte for byte the same, every page the same size.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
from typing import Any

import pymupdf

from .engine import file_md5
from .geometry import union
from .pdf import display_matrix, images_of, media_box, plain, raw_box, rotate_contents, split_pages, user_unit, wrap_contents

MARK = "SafhaOriginal"
CHUNK = 1 << 20


class ApplyError(RuntimeError):
    pass


def _box(v: list[float], nd: int = 2) -> str:
    return "[%s]" % " ".join(f"{x:.{nd}f}" for x in v)


def _same_file(a: str, b: str) -> bool:
    if os.path.abspath(a) == os.path.abspath(b):
        return True
    try:
        return os.path.samefile(a, b)  # the same file under two names (a link)
    except OSError:
        return False


def _writable(dst: str) -> None:
    """a plain refusal before any work when the output cannot be written where it is asked for"""
    if os.path.isdir(dst):
        raise ApplyError(f"{dst} is a folder: name the output file")
    d = os.path.dirname(os.path.abspath(dst))
    if not os.path.isdir(d):
        raise ApplyError(f"the output's folder does not exist: {d}")


def apply_recipe(src: str, rec: dict, dst: str, compact: bool = False, check_source: bool = True) -> dict[str, Any]:
    """write ``rec`` into a copy of ``src`` at ``dst`` -> a report (pages, cropped, turned, bytes in and out).

    The copy is made and checked under a temporary name beside ``dst`` and takes its name only when every check has
    passed: a refused output never stays on disk, and a ``dst`` that was there before is left as it was."""
    if not isinstance(rec.get("pages"), list):
        raise ApplyError("not a safha recipe: it lists no pages")
    if _same_file(src, dst):
        raise ApplyError("the output must be a new file: the original is never changed")
    _writable(dst)
    if check_source and rec.get("source", {}).get("md5") and file_md5(src) != rec["source"]["md5"]:
        raise ApplyError(f"{src} is not the file this recipe was made from (MD5 differs); re-run `safha plan`")
    tmp = dst + ".safha-part"
    try:
        rep = _write(src, rec, tmp, compact)
        os.replace(tmp, dst)
    finally:
        for f in (tmp, tmp + ".c"):
            with contextlib.suppress(OSError):
                os.remove(f)
    return rep


def _write(src: str, rec: dict, dst: str, compact: bool) -> dict[str, Any]:
    """``apply_recipe`` on the temporary copy ``dst``: written, then checked"""
    n_in = os.path.getsize(src)
    mode = rec.get("mode")
    shutil.copyfile(src, dst)
    before = pymupdf.open(src)
    try:
        if not before.is_pdf:
            raise ApplyError(f"{src} is not a PDF")
        imgs = images_of(before)
    finally:
        before.close()
    doc = pymupdf.open(dst, filetype="pdf")
    whole = None
    if not compact and not doc.can_save_incrementally():
        # (a file MuPDF had to repair on reading takes no incremental update: it is written out whole)
        compact, whole = True, "the file's structure had to be repaired on reading"
    try:
        done, turned_n, scaled_n, drop = _edit(doc, rec, imgs, mode)
        if drop:
            imgs = [im for j, im in enumerate(imgs) if j + 1 not in drop]
        md5 = rec.get("source", {}).get("md5") or file_md5(src)
        if not compact:
            doc.xref_set_key(doc.pdf_catalog(), MARK, f"<</Bytes {n_in}/MD5({md5})>>")
            doc.save(dst, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        else:
            doc.save(dst + ".c", garbage=3, deflate=False, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    finally:
        doc.close()
    if compact:
        os.replace(dst + ".c", dst)
    _check(src, rec, dst, imgs, mode, n_in, compact)
    rep = {"pages": len(imgs), "cropped": done, "turned": turned_n, "scaled": scaled_n, "dropped": len(drop),
           "bytes_in": n_in, "bytes_out": os.path.getsize(dst), "reversible": not compact}
    if whole:
        rep["rewritten"] = whole
    return rep


def _edit(doc: pymupdf.Document, rec: dict, imgs: list, mode: str | None) -> tuple[int, int, int, list[int]]:
    """the recipe written into the open copy (not yet saved) -> pages cropped, turned, scaled, and the pages to drop;
    ``imgs`` (the images each page must still draw) grows by the second page of every split sheet"""
    split = rec.get("split") or {}
    if split:
        bad = [k for k in split if not str(k).isdigit() or int(k) >= doc.page_count]
        if bad:
            raise ApplyError(f"the recipe splits sheet {int(bad[0]) + 1 if str(bad[0]).isdigit() else bad[0]!r}, "
                             f"which is not in the book ({doc.page_count} pages)")
        split_pages(doc, split, rec.get("direction") == "rtl")
        expect = []
        for i, im in enumerate(list(imgs)):
            expect.append(im)
            if str(i) in split:
                expect.append(im)
        imgs[:] = expect
    if len(rec["pages"]) != doc.page_count:
        raise ApplyError(f"the recipe has {len(rec['pages'])} pages, the book {doc.page_count}"
                         + (" once its two-page sheets are split" if split else "")
                         + ": it was made from another file, or edited")
    done = turned_n = scaled_n = 0
    if mode in ("crop", "level"):
        W, H = rec.get("size") or (None, None)
        for i, p in enumerate(rec["pages"]):
            page = doc[i]
            inv = ~display_matrix(page)
            mb = media_box(page)
            # a page stored sideways (/Rotate) or in another unit (/UserUnit): the book's size as its file counts it
            flat = plain(page)
            u = 1.0 if flat else user_unit(page)
            nd = 2 if flat else 4
            if mode == "level":
                if p.get("skew") or p.get("shear"):
                    rotate_contents(doc, page, p.get("skew") or 0, shear=p.get("shear") or 0)
                    turned_n += 1
                c = p.get("crop")
                if c:
                    a, b = pymupdf.Point(c[0], c[1]) * inv, pymupdf.Point(c[2], c[3]) * inv
                    doc.xref_set_key(page.xref, "CropBox",
                                     _box([min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)], nd))
                    done += 1
                continue
            if p.get("fit_whole"):  # a page turned by /Rotate: all of it, fitted
                cb = raw_box(doc, page.xref, "CropBox") or mb
                clip = [max(cb[0], mb[0]), max(cb[1], mb[1]), min(cb[2], mb[2]), min(cb[3], mb[3])]
                tw, th = (W / u, H / u) if page.rotation % 180 == 0 else (H / u, W / u)
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
                tw, th = (W / u, H / u) if page.rotation % 180 == 0 else (H / u, W / u)
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
            x0, y0 = round(cx - tw / 2, nd), round(cy - th / 2, nd)
            T = [x0, y0, round(x0 + tw, nd), round(y0 + th, nd)]
            if T[0] < mb[0] - 1e-3 or T[1] < mb[1] - 1e-3 or T[2] > mb[2] + 1e-3 or T[3] > mb[3] + 1e-3:
                doc.xref_set_key(page.xref, "MediaBox", _box(union([mb, T]), nd))
            doc.xref_set_key(page.xref, "CropBox", _box(T, nd))
            done += 1
    drop = sorted({int(k) for k in rec.get("drop") or []}, reverse=True)
    for k in drop:
        if not 1 <= k <= doc.page_count:
            raise ApplyError(f"page {k} to drop is not in the book ({doc.page_count} pages)")
    if len(drop) >= doc.page_count and drop:
        raise ApplyError("every page of the book would be dropped")
    if drop:
        doc.delete_pages([k - 1 for k in drop])
    return done, turned_n, scaled_n, drop


def _check(src: str, rec: dict, dst: str, imgs: list, mode: str | None, n_in: int, compact: bool) -> None:
    """the written copy against what it must be: the same pages, every image stream byte for byte, one page size, and
    (unless rewritten whole) the original file's bytes at its start"""
    chk = pymupdf.open(dst, filetype="pdf")
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
    if not compact and not _starts_with(dst, src, n_in):
        raise ApplyError("the output does not start with the original bytes")


def _starts_with(path: str, head: str, n: int) -> bool:
    """the first ``n`` bytes of ``path`` are the whole of ``head`` (read a megabyte at a time: a book can be gigabytes)"""
    with open(path, "rb") as f, open(head, "rb") as g:
        left = n
        while left > 0:
            a = f.read(min(CHUNK, left))
            if not a or a != g.read(len(a)):
                return False
            left -= len(a)
        return g.read(1) == b""


def restore(path: str, dst: str) -> dict[str, Any]:
    """the original file back from a safha output (incremental, not ``--compact``): truncated, MD5 checked"""
    if _same_file(path, dst):
        raise ApplyError("write the original to a new file")
    _writable(dst)
    doc = pymupdf.open(path)
    try:
        if not doc.is_pdf:
            raise ApplyError(f"{path} is not a PDF")
        t, v = doc.xref_get_key(doc.pdf_catalog(), MARK)
    finally:
        doc.close()
    if t != "dict":
        raise ApplyError(f"{path} carries no safha restore mark (made with --compact, or not by safha)")
    m = re.search(r"/Bytes\s+(\d+)", v)
    h = re.search(r"/MD5\s*\(([0-9a-f]{32})\)", v)
    if not m or not h:
        raise ApplyError("unreadable restore mark")
    n = int(m.group(1))
    tmp = dst + ".safha-part"
    md5 = hashlib.md5()
    try:
        with open(path, "rb") as f, open(tmp, "wb") as o:
            left = n
            while left > 0:
                b = f.read(min(CHUNK, left))
                if not b:
                    break
                md5.update(b)
                o.write(b)
                left -= len(b)
        if left or md5.hexdigest() != h.group(1):
            raise ApplyError("the first bytes do not match the original's MD5: the file was changed after safha")
        os.replace(tmp, dst)
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp)
    return {"bytes": n, "md5": h.group(1)}
