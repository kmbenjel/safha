"""Download the public-domain benchmark corpus from the Internet Archive (books published before 1931, manuscripts).

For each item, the scan's original PDF when the uploader gave one (Digital Library of India: CCITT G4 pages), else the
Archive's own PDF (JPEG 2000 / JBIG2 / JPEG pages). The list, with each item's year and licence, is written to
corpus.tsv next to the files. Usage: python bench/fetch_corpus.py DIR [--max-mb 160]
"""

from __future__ import annotations

import argparse
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
        print(f"{ident}: {f['bytes'] / 1e6:.1f} MB ({f['format']})", flush=True)
        rows.append([ident, kind, note, f["title"], f["format"], str(f["bytes"]),
                     "public domain (published before 1931)" if "manuscript" not in kind else "public domain (manuscript)",
                     f"https://archive.org/details/{ident}"])
    with open(os.path.join(a.dir, "corpus.tsv"), "w", encoding="utf-8") as fh:
        fh.write("id\tkind\tnote\ttitle\tformat\tbytes\tlicence\turl\n")
        for r in rows:
            fh.write("\t".join(x.replace("\t", " ") for x in r) + "\n")


if __name__ == "__main__":
    main()
