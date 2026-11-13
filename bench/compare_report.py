"""compare.json -> a Markdown table (bench/results/compare.md)."""

from __future__ import annotations

import json
import sys

rows: list = []
for path in sys.argv[1:]:  # several runs (e.g. one tool added later) merged; the first run's input rows are kept
    with open(path, encoding="utf-8") as fh:
        more = json.load(fh)
    seen = {(r["book"], r["tool"]) for r in rows}
    rows += [r for r in more if (r["book"], r["tool"]) not in seen]
inputs = {r["book"]: r for r in rows if r["tool"] == "input"}
tools = []
for r in rows:
    if r["tool"] != "input" and r["tool"] not in tools:
        tools.append(r["tool"])


def codecs(f: dict | None) -> str:
    return "+".join(k.replace("Decode", "") for k in sorted(f or {})) or "none"


print("# Head-to-head on the same public-domain pages\n")
print("Each book: a 40-page excerpt copied object for object from the Internet Archive scan. Size: output / input. "
      "Off-centre: median distance of the text block's centre from the page's centre; sway: its interquartile range "
      "from page to page (shares of the page width; lower is steadier). Text width: the text block's median share of "
      "the page width (higher is larger text on screen). safha runs with its default profile (crops when it pays) and "
      "with `--profile reader` (always crops).\n")
for book, base in inputs.items():
    if book.startswith("truth"):
        continue
    pi = base.get("place_in") or {}
    print(f"## {book} ({base['pages']} pages, {base['bytes_in'] / 1e6:.2f} MB, {codecs(base['filters_in'])})\n")
    print(f"Input: {pi.get('sizes')} page sizes, text off-centre {pi.get('offcentre_median', 0) * 100:.1f} % (median), "
          f"sways {pi.get('sway_iqr', 0) * 100:.1f} % (IQR), text {pi.get('text_width_share', 0) * 100:.0f} % of the width\n")
    print("| tool | time s | size | image streams kept byte for byte | codecs out | page sizes | text off-centre | sway | text width |")
    print("|---|---:|---:|---:|---|---:|---:|---:|---:|")
    for t in tools:
        r = next((x for x in rows if x["book"] == book and x["tool"] == t), None)
        if r is None:
            continue
        if "error" in r:
            print(f"| {t} | failed | | | | | | | |")
            continue
        po = r.get("place_out") or {}

        def pct(k: str, nd: int = 1) -> str:
            return f"{po[k] * 100:.{nd}f} %" if k in po else "no text found"

        print(f"| {t} | {r['seconds']:.1f} | {r['bytes_out'] / base['bytes_in'] * 100:.0f} % | {r['kept_streams'] * 100:.0f} % | "
              f"{codecs(r.get('filters_out'))} | {po.get('sizes', '')} | {pct('offcentre_median')} | {pct('sway_iqr')} | "
              f"{pct('text_width_share', 0)} |")
    print()
truth = [r for r in rows if r["book"].startswith("truth") and r["tool"] != "input"]
if truth:
    print("## Known truth: 3 pages tilted 1 deg, 3 warped pages (upper lines level, lower lines at 1.5 deg)\n")
    print("| tool | tilted pages levelled | warped pages wrongly turned |")
    print("|---|---:|---:|")
    for r in truth:
        if "error" in r:
            print(f"| {r['tool']} | failed | failed |")
        else:
            print(f"| {r['tool']} | {r.get('tilted_levelled')} | {r.get('warped_wrongly_turned')} |")
