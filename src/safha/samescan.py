"""Are two PDFs the same scan? Page by page, every image compared by the MD5 of its raw (still compressed) stream:
identical streams are the same scanned pixels. Text layer, bookmarks and metadata tell which copy to keep."""

from __future__ import annotations

import hashlib
import os
from typing import Any

import pymupdf


def profile(path: str) -> dict[str, Any]:
    doc = pymupdf.open(path)
    pages = []
    for p in doc:
        imgs = [hashlib.md5(doc.xref_stream_raw(x[0]) or b"").hexdigest() for x in p.get_images(full=True)]
        pages.append({"imgs": imgs, "size": (round(p.mediabox.width), round(p.mediabox.height)),
                      "text": len(p.get_text("text").strip())})
    out = {"pages": pages, "outline": len(doc.get_toc()), "bytes": os.path.getsize(path),
           "meta": {k: v for k, v in (doc.metadata or {}).items() if v and k in ("title", "author")}}
    doc.close()
    return out


def compare(a: str, b: str) -> dict[str, Any]:
    pa, pb = profile(a), profile(b)
    r: dict[str, Any] = {"a": a, "b": b, "pages": [len(pa["pages"]), len(pb["pages"])],
                         "outline": [pa["outline"], pb["outline"]],
                         "text_pages": [sum(1 for x in pa["pages"] if x["text"]), sum(1 for x in pb["pages"] if x["text"])],
                         "bytes": [pa["bytes"], pb["bytes"]], "meta": [pa["meta"], pb["meta"]]}
    diff = None
    if len(pa["pages"]) != len(pb["pages"]):
        diff = "page count"
    else:
        for i, (x, y) in enumerate(zip(pa["pages"], pb["pages"])):
            if not x["imgs"] or x["imgs"] != y["imgs"]:
                diff = f"page {i + 1} images"
                break
    r["verdict"] = "same scan" if diff is None else "different"
    if diff:
        r["first_difference"] = diff
    return r
