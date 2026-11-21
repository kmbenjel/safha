"""Every number the README and the Arabic docs quote, read from the result files in bench/results/.

Usage: python bench/docs_numbers.py [RESULTS_DIR]     (default: bench/results beside this script)
The files: bench.json and bench-compact.json (`safha bench`), rule-audit.json (bench/rule_audit.py),
compare/compare-*.json (bench/compare.sh). Run it after a new measurement and hold the docs against what it prints.
"""

from __future__ import annotations

import glob
import json
import os
import sys

here = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(name: str) -> dict | list | None:
    path = os.path.join(here, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


b, c, ra = load("bench.json"), load("bench-compact.json"), load("rule-audit.json")
if isinstance(b, dict):
    rows = [r for r in b["rows"] if "error" not in r]
    pages, text, turned = sum(r["pages"] for r in rows), sum(r["text"] for r in rows), sum(r["turned"] for r in rows)
    bi, bo = sum(r["bytes_in"] for r in rows), sum(r["bytes_out"] for r in rows)
    modes = {m: sum(1 for r in rows if r["mode"] == m) for m in ("crop", "level", "skip")}
    kinds: dict[str, int] = {}
    for r in rows:
        for k, v in (r.get("filters") or {}).items():
            kinds[k] = kinds.get(k, 0) + v
    print("== corpus bench (bench.json)")
    print(f"books {len(b['rows'])} (errors {len(b['rows']) - len(rows)}), pages {pages:,}, text pages {text:,}")
    print(f"written: {modes['crop']} cropped, {modes['level']} levelled only, {modes['skip']} left as they are")
    print(f"image codecs unchanged in {sum(1 for r in rows if r.get('filters') == r.get('filters_out'))} of "
          f"{sum(1 for r in rows if 'filters_out' in r)} written books; image streams by filter: {kinds}")
    print(f"size: {bi / 1e6:.1f} MB in, {bo / 1e6:.1f} MB out ({(bo - bi) / bi * 100:+.2f} %, reversible)")
    print(f"pages turned: {turned:,} of {text:,} text pages ({turned / text * 100:.1f} %), by a column rule "
          f"{sum(r.get('by_columns', 0) for r in rows)}, sheared {sum(r['sheared'] for r in rows)}, by a frame "
          f"{sum(r.get('frame_turn', 0) for r in rows)}")
    print(f"left as scanned: lines at two angles {sum(r['two_angles'] for r in rows)}, witnesses disagree "
          f"{sum(r.get('disputed', 0) for r in rows)}, a tilt seen and not confirmed {sum(r['unsure'] for r in rows)}")
    print(f"pages shown whole: {sum(r['whole'] for r in rows)}; sheets split: {sum(r['split'] for r in rows)}")
    secs = sum(r["seconds"] for r in rows)
    print(f"speed: {pages / secs:.2f} pages/s per book ({b['jobs']} page workers each); wall {b['wall_s']:.0f} s with "
          f"{b['book_jobs']} books at once = {pages / b['wall_s']:.1f} pages/s; {b.get('cpus')} logical processors")
    fresh = [r for r in rows if "cpu_s" in r]
    if fresh:
        per = sorted(r["pages"] / r["cpu_s"] for r in fresh)
        print(f"processor time: {sum(r['pages'] for r in fresh) / sum(r['cpu_s'] for r in fresh):.2f} pages per CPU-second over "
              f"all books; by book from {per[0]:.2f} to {per[-1]:.2f}")
if isinstance(c, dict):
    rows = [r for r in c["rows"] if "error" not in r]
    bi, bo = sum(r["bytes_in"] for r in rows), sum(r["bytes_out"] for r in rows)
    print(f"== the same written whole (bench-compact.json): {bi / 1e6:.1f} MB in, {bo / 1e6:.1f} MB out ({(bo - bi) / bi * 100:+.2f} %)")
if isinstance(ra, dict):
    rr = ra["rows"]
    a = [abs(r["after"]) for r in rr]
    worse = [r for r in rr if abs(r["after"]) > abs(r["before"]) + 0.1]
    print("== the turns against the printed rules (rule-audit.json)")
    print(f"turned pages {sum(ra['pages_turned'].values()):,}; with a long straight rule inside their print {len(rr)}; after the "
          f"turn within 0.15 deg of upright {sum(x <= 0.15 for x in a)}, within 0.3 deg {sum(x <= 0.3 for x in a)}, beyond 0.3 "
          f"deg {sum(x > 0.3 for x in a)}; left further from upright than on the scan {len(worse)}"
          + (f" (the worst by {max(abs(r['after']) - abs(r['before']) for r in worse):.2f} deg)" if worse else ""))
cmp_rows: list = []
for path in sorted(glob.glob(os.path.join(here, "compare", "compare-*.json"))):
    with open(path, encoding="utf-8") as f:
        cmp_rows += json.load(f)
if cmp_rows:
    inputs = {r["book"]: r for r in cmp_rows if r["tool"] == "input"}
    print("== head-to-head (compare/*.json): the place of the text, by safha's own text-block measure on every output")
    for book, base in inputs.items():
        pi = base.get("place_in")
        if not pi or "text_width_share" not in pi:
            continue
        line = [f"scan: width {pi['text_width_share'] * 100:.0f} %, off-centre {pi['offcentre_median'] * 100:.1f} %, sway "
                f"{pi['sway_iqr'] * 100:.1f} %, {pi['sizes']} page sizes"]
        for t in ("safha", "safha-reader", "pdfCropMargins", "briss"):
            r = next((x for x in cmp_rows if x["book"] == book and x["tool"] == t and "error" not in x), None)
            po = (r or {}).get("place_out") or {}
            if "text_width_share" in po:
                line.append(f"{t}: width {po['text_width_share'] * 100:.0f} %, off-centre {po['offcentre_median'] * 100:.1f} %, "
                            f"sway {po['sway_iqr'] * 100:.1f} %, {po['sizes']} sizes")
        print(f"{book}: " + " | ".join(line))
    print("(the table of all tools: python bench/compare_report.py --summary bench/results/compare/*.json)")
