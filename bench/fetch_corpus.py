"""Download the public-domain benchmark corpus from the Internet Archive (books published before 1931, manuscripts).

For each item, the scan's original PDF when the uploader gave one (Digital Library of India: CCITT G4 pages), else the
Archive's own PDF (JPEG 2000 / JBIG2 / JPEG pages). The list, with each item's year, licence, file name and MD5, is
written to corpus.tsv next to the files. Each file is held against the MD5 of the file the published results were made
from (``PUBLISHED``): the Archive re-derives its PDFs now and then, and a re-derived file is said to be one.

Usage: python bench/fetch_corpus.py DIR [--max-mb 160]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request

ITEMS = [
    # (identifier, kind, note)
    ("almuqaddimah00ibnk", "Arabic print, colour camera scan", "Cairo 1904"),
    ("tarkhalrusulwaal01abaruoft", "Arabic print with Latin apparatus", "Leiden 1879"),
    ("kitbalmawiwaalit01maqruoft", "Arabic print, Bulaq", "Bulaq 1853"),
    ("kitabalzabur00barguoft", "Arabic print", "1861"),
    ("taghrbatbanhilla00bayruoft", "Arabic print", "Beirut 1900"),
    ("majmaalmasarrt00khrsuoft", "Arabic print", "1908"),
    ("chronologyofanci00biru", "English print", "London 1879"),
    ("arabicproverbsor00burc", "English print", "London 1875"),
    ("arabicmanuscript28loui", "Arabic manuscript, microfilm spreads", "manuscript, before 1900"),
    ("arabicmanuscript33loui", "Arabic manuscript, microfilm spreads", "manuscript, before 1900"),
    ("persianmedicalma33loui", "Persian manuscript, microfilm spreads", "manuscript, before 1900"),
    ("in.ernet.dli.2015.361017", "Urdu print, bitonal CCITT", "1857"),
    ("in.ernet.dli.2015.262150", "English print, bitonal CCITT", "1857"),
    ("in.ernet.dli.2015.86278", "English maths, bitonal CCITT", "1915"),
    ("in.ernet.dli.2015.70512", "Telugu-English dictionary, bitonal CCITT", "1900"),
    ("in.ernet.dli.2015.207418", "English journal, bitonal CCITT", "1907"),
    ("dictionnairefra00lagogoog", "French-Arabic dictionary, Google scan", "1896"),
]


# the files the published results (bench/results/) were made from, as the Archive served them on 2026-11-13 and still
# did on 2026-11-21
PUBLISHED = {
    "almuqaddimah00ibnk": "f8247191330f9e6f0871d581e2f7bb17", "tarkhalrusulwaal01abaruoft": "db31deff1e1ad890b3d387ed34d4e95b",
    "kitbalmawiwaalit01maqruoft": "d0b7bcccc748a26d7be28046cffc130e", "kitabalzabur00barguoft": "0b47b67b31b962575d6604083052a657",
    "taghrbatbanhilla00bayruoft": "f564a4436b5150b70cfd707ef8f565ba", "majmaalmasarrt00khrsuoft": "de18772759e16080df1a629bffd9a4e2",
    "chronologyofanci00biru": "79dd72773dee43318c1180045eb0a2de", "arabicproverbsor00burc": "82759f9d6f916179c5e7eb80e38b25f0",
    "arabicmanuscript28loui": "c8597e3561f6886de95042df4228f2b1", "arabicmanuscript33loui": "696d6f69b59337fd40955f1a12a4f307",
    "persianmedicalma33loui": "c979a440651108b67d2c733eed237a01", "in.ernet.dli.2015.361017": "1441578b44d4690ac5f56c86abb39ba5",
    "in.ernet.dli.2015.262150": "5f20cba184a179d9605dcd24823f5f8f", "in.ernet.dli.2015.86278": "797b7fa5c045d555dd45e117374685df",
    "in.ernet.dli.2015.70512": "28a075e75d3bc8190912dcc3116f9dc2", "in.ernet.dli.2015.207418": "a0f23835d7473f3524938492ffa2ab96",
    "dictionnairefra00lagogoog": "99a1124cca833673eaa938a81bd1802c",
}


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pick(ident: str, max_mb: float) -> dict | None:
    meta = json.load(urllib.request.urlopen(f"https://archive.org/metadata/{ident}", timeout=60))
    files = meta.get("files", [])
    pdfs = [f for f in files if f["name"].lower().endswith(".pdf") and not f["name"].endswith("_text.pdf")]
    pdfs.sort(key=lambda f: (f.get("source") != "original", f.get("format") != "Text PDF", int(f.get("size", 0))))
    for f in pdfs:
        if int(f.get("size", 0)) <= max_mb * 1e6:
            m = meta.get("metadata", {})
            return {"id": ident, "file": f["name"], "bytes": int(f.get("size", 0)), "format": f.get("format"),
                    "title": str(m.get("title", ""))[:90], "date": m.get("date", ""), "source": f.get("source")}
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dir")
    ap.add_argument("--max-mb", type=float, default=160)
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    rows = []
    for ident, kind, note in ITEMS:
        f = pick(ident, a.max_mb)
        if not f:
            print(f"skip {ident}: no PDF under {a.max_mb} MB")
            continue
        out = os.path.join(a.dir, ident + ".pdf")
        if not os.path.exists(out) or os.path.getsize(out) != f["bytes"]:
            url = f"https://archive.org/download/{ident}/{urllib.request.quote(f['file'])}"
            req = urllib.request.Request(url, headers={"User-Agent": "safha-bench/0.1"})
            with urllib.request.urlopen(req, timeout=600) as r, open(out + ".part", "wb") as o:
                shutil.copyfileobj(r, o, 1 << 20)
            os.replace(out + ".part", out)
        md5 = md5_of(out)
        same = "" if PUBLISHED.get(ident) in (None, md5) else \
            "  NOTE: not the file the published results were made from (the Archive has re-derived it)"
        print(f"{ident}: {f['bytes'] / 1e6:.1f} MB ({f['format']}){same}", flush=True)
        rows.append([ident, kind, note, f["title"], f["format"], str(f["bytes"]),
                     "public domain (published before 1931)" if "manuscript" not in kind else "public domain (manuscript)",
                     f"https://archive.org/details/{ident}", f["file"], md5])
    with open(os.path.join(a.dir, "corpus.tsv"), "w", encoding="utf-8") as fh:
        fh.write("id\tkind\tnote\ttitle\tformat\tbytes\tlicence\turl\tfile\tmd5\n")
        for r in rows:
            fh.write("\t".join(x.replace("\t", " ") for x in r) + "\n")


if __name__ == "__main__":
    main()
