"""What the book's proportions take off each cover, over a corpus run.

A cover found on the scanner bed, and a picture page at either end of a book (a binding board), fill the page: a strip
of them is left out at two opposite edges. This lists every such page of the cropped books with the strips its shown
part leaves out, as shares of the cover (the cover's own box when one was found, else the sheet).

Usage: python bench/covers.py RECIPES      (the folder `safha bench CORPUS --recipes RECIPES` filled)
"""

from __future__ import annotations

import json
import os
import sys


def strips(p: dict) -> list[float]:
    """left, top, right, bottom: the shares of the cover that its shown part leaves out"""
    c = p.get("cover") or [0.0, 0.0, p["w"], p["h"]]
    s = p["show"]
    cw, ch = c[2] - c[0], c[3] - c[1]
    return [max(0.0, s[0] - c[0]) / cw, max(0.0, s[1] - c[1]) / ch, max(0.0, c[2] - s[2]) / cw, max(0.0, c[3] - s[3]) / ch]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    worst: dict[str, float] = {}
    print("| book | page | kind | left out: left, top, right, bottom (% of the cover) |\n|---|---:|---|---|")
    for name in sorted(os.listdir(sys.argv[1])):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(sys.argv[1], name), encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("mode") != "crop":
            continue
        n = len(rec["pages"])
        for k, p in enumerate(rec["pages"]):
            at_end = (k < 2 or k >= n - 4) and p["kind"] in ("cover", "picture")
            if not (p["kind"] == "cover" or at_end) or not p.get("show"):
                continue
            out = strips(p)
            book = rec["source"]["file"]
            worst[book] = max(worst.get(book, 0.0), max(out))
            print(f"| {book} | {p['n']} | {p['kind']} | " + ", ".join(f"{100 * v:.1f}" for v in out) + " |")
    print("\nThe widest strip by book: " + "; ".join(f"{b} {100 * v:.1f} %" for b, v in sorted(worst.items())) + ".")


if __name__ == "__main__":
    main()
