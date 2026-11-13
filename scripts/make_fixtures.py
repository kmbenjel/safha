"""Build the test fixtures and the demo book from public-domain scans on the Internet Archive (see docs/media/SOURCES.md).

Every page comes from the item's own page images (IIIF) or its original PDF; the fixture PDFs embed them without
re-encoding where possible (JPEG as DCT, CCITT G4 pages copied object for object). The Latin fixture is made bitonal and
encoded as JBIG2 (generic region, lossless) with `jbig2enc`, to exercise that filter too.

Usage: python scripts/make_fixtures.py [--cache DIR]
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import tempfile
import urllib.request

import pymupdf
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")
IIIF = "https://iiif.archive.org/image/iiif/3/{id}%2F{id}_jp2.zip%2F{id}_jp2%2F{id}_{n:04d}.jp2/full/{w},/0/default.jpg"

ARABIC = ("tarkhalrusulwaal01abaruoft", [30, 31, 32, 33, 34, 35], 900)
BULAQ = ("kitbalmawiwaalit01maqruoft", [100, 101, 102, 103, 104, 105], 900)
LATIN = ("chronologyofanci00biru", [31, 32, 101, 102, 201, 202], 1500)
SPREAD = ("arabicmanuscript28loui", [20, 30, 40, 50, 60], 1200)
CCITT = ("in.ernet.dli.2015.361017", "2015.361017.Tamreen-As.pdf", [18, 19, 20, 21, 30, 31])
# two columns with a printed rule between them, a headword and its gloss in two scripts on each line (JBIG2, copied
# object for object): scan pages 437, 87, 341, 52, 230
DICT = ("dictionnairefra00lagogoog", "dictionnairefra00lagogoog.pdf", [436, 86, 340, 51, 229])


def fetch(url: str, cache: str) -> bytes:
    os.makedirs(cache, exist_ok=True)
    f = os.path.join(cache, url.replace("/", "_").replace(":", "")[-180:])
    if not os.path.exists(f):
        req = urllib.request.Request(url, headers={"User-Agent": "safha-fixtures/0.1"})
        with urllib.request.urlopen(req, timeout=120) as r, open(f + ".part", "wb") as o:
            shutil.copyfileobj(r, o)
        os.replace(f + ".part", f)
    with open(f, "rb") as fh:
        return fh.read()


def jpeg_book(item: tuple, cache: str, out: str, dpi: float = 150, gray: bool = False, quality: int = 55) -> None:
    ident, pages, width = item
    doc = pymupdf.open()
    for n in pages:
        data = fetch(IIIF.format(id=ident, n=n, w=width), cache)
        im = Image.open(io.BytesIO(data))
        buf = io.BytesIO()  # the fixture's own JPEG (smaller than the download); safha keeps it byte for byte
        im.convert("L" if gray else "RGB").save(buf, "JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        im = Image.open(io.BytesIO(data))
        w, h = im.size
        page = doc.new_page(width=w * 72 / dpi, height=h * 72 / dpi)
        page.insert_image(page.rect, stream=data)
    doc.set_metadata({"title": f"safha fixture from archive.org/details/{ident}", "producer": "safha make_fixtures"})
    doc.save(out, garbage=3, deflate=True)


def jbig2_book(item: tuple, cache: str, out: str, dpi: float = 200) -> None:
    ident, pages, width = item
    exe = shutil.which("jbig2") or os.path.expanduser("~/.local/bin/jbig2")
    doc = pymupdf.open()
    with tempfile.TemporaryDirectory() as t:
        for n in pages:
            im = Image.open(io.BytesIO(fetch(IIIF.format(id=ident, n=n, w=width), cache))).convert("L")
            bw = im.point(lambda v: 255 if v > 150 else 0).convert("1")
            src = os.path.join(t, f"p{n}.png")
            bw.save(src)
            raw = subprocess.run([exe, "-p", src], capture_output=True, check=True).stdout  # generic region: lossless
            w, h = bw.size
            pw, ph = w * 72 / dpi, h * 72 / dpi
            page = doc.new_page(width=pw, height=ph)
            x = doc.get_new_xref()
            doc.update_object(x, f"<</Type/XObject/Subtype/Image/Width {w}/Height {h}/ColorSpace/DeviceGray"
                                 f"/BitsPerComponent 1/Filter/JBIG2Decode/Length {len(raw)}>>")
            doc.update_stream(x, raw, compress=False)
            doc.xref_set_key(x, "Filter", "/JBIG2Decode")
            doc.xref_set_key(page.xref, "Resources", f"<</XObject<</Im0 {x} 0 R>>>>")
            c = doc.get_new_xref()
            doc.update_object(c, "<<>>")
            doc.update_stream(c, f"q {pw:.3f} 0 0 {ph:.3f} 0 0 cm /Im0 Do Q".encode())
            doc.xref_set_key(page.xref, "Contents", f"{c} 0 R")
    doc.set_metadata({"title": f"safha fixture from archive.org/details/{ident}", "producer": "safha make_fixtures"})
    doc.save(out, garbage=3)


def ccitt_book(item: tuple, cache: str, out: str) -> None:
    """pages of the item's own PDF copied object for object (its image streams as they are: CCITT G4, JBIG2)"""
    ident, name, pages = item
    data = fetch(f"https://archive.org/download/{ident}/{name}", cache)
    src = pymupdf.open("pdf", data)
    doc = pymupdf.open()
    for n in pages:
        doc.insert_pdf(src, from_page=n, to_page=n)
    doc.set_metadata({"title": f"safha fixture from archive.org/details/{ident}", "producer": "safha make_fixtures"})
    doc.save(out, garbage=3)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/safha-fixtures"))
    a = ap.parse_args()
    os.makedirs(FIX, exist_ok=True)
    jpeg_book(ARABIC, a.cache, os.path.join(FIX, "arabic-leiden.pdf"), dpi=100, gray=True)
    jpeg_book(BULAQ, a.cache, os.path.join(FIX, "arabic-bulaq.pdf"), dpi=100, gray=True)
    jbig2_book(LATIN, a.cache, os.path.join(FIX, "latin-jbig2.pdf"))
    jpeg_book(SPREAD, a.cache, os.path.join(FIX, "spreads.pdf"), dpi=100, gray=True, quality=50)
    ccitt_book(CCITT, a.cache, os.path.join(FIX, "urdu-ccitt.pdf"))
    ccitt_book(DICT, a.cache, os.path.join(FIX, "dictionary-rule.pdf"))
    for f in sorted(os.listdir(FIX)):
        if f.endswith(".pdf"):
            d = pymupdf.open(os.path.join(FIX, f))
            print(f"{f}: {d.page_count} pages, {os.path.getsize(os.path.join(FIX, f)) // 1024} KB")


if __name__ == "__main__":
    main()
