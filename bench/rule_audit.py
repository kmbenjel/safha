"""The turns safha made over a corpus, held against the print's own rules.

A rule the printer set across or down a page (a column rule, a rule under a running head, a table's) is the print's
straightest line. On every page safha turned, the long straight rules standing inside the print are read on the page as
scanned by ``bench/rules.py`` (which owes nothing to safha's measures); the turn is then held against them: a rule
that leaned by ``b`` degrees stands at ``b + turn`` after it.

A page counts when it carries such a rule: upright ones at least 35 % of the page tall, between 25 % and 75 % of its
width; level ones at least 35 % of the page wide, between 8 % and 92 % of its height; and when its rules agree among
themselves within 0.15 degree (rules that do not are no standard).

Usage: python bench/rule_audit.py CORPUS RECIPES [-o bench/results/rule-audit.json] [--jobs N]
RECIPES: the folder `safha bench CORPUS --recipes RECIPES` filled. Writes the JSON (one row per page) and a Markdown
summary beside it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import rule_leans

from safha.pdf import open_book


def read_pages(args: tuple) -> list[dict]:
    corpus, recipe, idx = args
    with open(recipe, encoding="utf-8") as f:
        rec = json.load(f)
    doc = open_book(os.path.join(corpus, rec["source"]["file"]), rec)
    rows = []
    for i in idx:
        p = rec["pages"][i]
        page = doc[i]
        z = 1400 / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csGRAY, alpha=False)
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
        H, W = a.shape
        r = rule_leans(a)
        cand = [v[0] for v in r["v"] if v[1] >= 0.35 * H and 0.25 * W <= v[2] <= 0.75 * W] \
            + [h[0] for h in r["h"] if h[1] >= 0.35 * W and 0.08 * H <= h[2] <= 0.92 * H]
        if not cand or max(cand) - min(cand) > 0.15:
            continue
        before = float(np.median(cand))
        rows.append({"book": rec["source"]["file"], "page": p["n"], "turn": p["skew"], "rules": len(cand),
                     "before": round(before, 3), "after": round(before + p["skew"], 3), "flags": p.get("flags") or []})
    doc.close()
    return rows


def summary(rows: list[dict], turned: dict[str, int]) -> str:
    def count(v: list[dict]) -> list[int]:
        a = [abs(r["after"]) for r in v]
        return [len(v), sum(x <= 0.15 for x in a), sum(0.15 < x <= 0.3 for x in a), sum(x > 0.3 for x in a),
                sum(abs(r["after"]) > abs(r["before"]) + 0.1 for r in v)]

    out = ["# The turns against the print's own rules", "",
           f"{len(rows)} of the {sum(turned.values())} pages safha turned carry a long straight printed rule inside their "
           "print (read on the page as scanned by [`bench/rules.py`](../rules.py), independently of safha's measures). "
           "After the turn the rule stands at its lean on the scan plus the turn.", "",
           "| book | pages turned | with a rule | within 0.15 deg of upright after | 0.15 to 0.3 | beyond 0.3 | "
           "further from upright than on the scan (by more than 0.1) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for book in sorted(turned):
        v = [r for r in rows if r["book"] == book]
        if v:
            c = count(v)
            out.append(f"| {book} | {turned[book]} | {c[0]} | {c[1]} | {c[2]} | {c[3]} | {c[4]} |")
    c = count(rows)
    out.append(f"| **all** | **{sum(turned.values())}** | **{c[0]}** | **{c[1]}** | **{c[2]}** | **{c[3]}** | **{c[4]}** |")
    worse = sorted((r for r in rows if abs(r["after"]) > abs(r["before"]) + 0.1), key=lambda r: abs(r["before"]) - abs(r["after"]))
    far = sorted((r for r in rows if abs(r["after"]) > 0.3), key=lambda r: -abs(r["after"]))
    if worse:
        out += ["", "Left further from upright than on the scan: " + "; ".join(
            f"{r['book']} p. {r['page']} ({r['before']:+.2f} to {r['after']:+.2f} deg)" for r in worse) + "."]
    if far:
        out += ["", "Beyond 0.3 degree after the turn: " + "; ".join(
            f"{r['book']} p. {r['page']} ({r['before']:+.2f} to {r['after']:+.2f} deg)" for r in far) + "."]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus")
    ap.add_argument("recipes")
    ap.add_argument("-o", "--output", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "rule-audit.json"))
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    tasks, turned = [], {}
    for name in sorted(os.listdir(a.recipes)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(a.recipes, name)
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        idx = [i for i, p in enumerate(rec["pages"]) if p["kind"] == "text" and p.get("skew")]
        turned[rec["source"]["file"]] = len(idx)
        tasks += [(a.corpus, path, idx[k:k + 20]) for k in range(0, len(idx), 20)]
    rows: list[dict] = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for part in ex.map(read_pages, tasks):
            rows += part
    rows.sort(key=lambda r: (r["book"], r["page"]))
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump({"pages_turned": turned, "rows": rows}, f, ensure_ascii=False, indent=1)
    md = summary(rows, turned)
    with open(os.path.splitext(a.output)[0] + ".md", "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
