"""compare*.json -> a Markdown report (bench/results/compare.md)."""

from __future__ import annotations

import json
import sys

rows: list = []
for path in sys.argv[1:]:  # several runs (one per book, or one tool added later) merged; the first row of each kind is kept
    with open(path, encoding="utf-8") as fh:
        more = json.load(fh)
    seen = {(r["book"], r["tool"]) for r in rows}
    rows += [r for r in more if (r["book"], r["tool"]) not in seen]
inputs = {r["book"]: r for r in rows if r["tool"] == "input"}
ORDER = ["safha", "safha-reader", "pdfCropMargins", "briss", "k2pdfopt", "k2pdfopt-as", "unpaper", "ocrmypdf-pdfa", "ocrmypdf",
         "ocrmypdf-O2", "ocrmypdf-O3"]
NAMES = {"safha": "safha", "safha-reader": "safha `--profile reader`", "pdfCropMargins": "pdfCropMargins `-u -s`",
         "briss": "Briss", "k2pdfopt": "k2pdfopt (default: reflow)", "k2pdfopt-as": "k2pdfopt `-mode copy -as`",
         "unpaper": "unpaper (G4 / JPEG 85 out)", "ocrmypdf-pdfa": "OCRmyPDF `--deskew` (its default: PDF/A output)",
         "ocrmypdf": "OCRmyPDF `--deskew --output-type pdf`", "ocrmypdf-O2": "OCRmyPDF `--deskew --output-type pdf -O2`",
         "ocrmypdf-O3": "OCRmyPDF `--deskew --output-type pdf -O3`"}
tools = [t for t in ORDER if any(r["tool"] == t for r in rows)]


def codecs(f: dict | None) -> str:
    return "+".join(k.replace("Decode", "") for k in sorted(f or {})) or "none"


def row_of(book: str, tool: str) -> dict | None:
    return next((x for x in rows if x["book"] == book and x["tool"] == tool), None)


print("# Head-to-head on the same public-domain pages\n")
print("Each book: a 40-page excerpt copied object for object from the Internet Archive scan. Every tool runs the way a "
      "careful user would run it for this job (the commands are in [`bench/compare.py`](../compare.py), `run_tool`): "
      "OCRmyPDF with its optional helpers installed (jbig2enc, pngquant), first exactly as it runs by default (PDF/A "
      "output, written through Ghostscript), then writing a plain PDF at its default lossless optimisation and at its two "
      "lossy ones; unpaper at the scan's own resolution and kind, written back as CCITT G4 (1-bit pages) or JPEG 85; "
      "k2pdfopt in its default reflow mode and in copy mode with auto-straighten (one output page per source page). "
      "k2pdfopt's lossless trim mode (`-mode tm`, native PDF output) needs a build with MuPDF; the Ubuntu 24.04 package "
      "has none and writes no file in that mode, so it is not measured.\n")
print("Size: output / input. Off-centre: median distance of the text block's centre from the page's centre; sway: its "
      "interquartile range from page to page (shares of the page width; lower is steadier). Text width: the text block's "
      "median share of the page width (higher is larger text on screen). Times are wall-clock on a shared 32-core "
      "machine with several tools running at once: read them as orders of magnitude.\n")
for book, base in inputs.items():
    if book.startswith("truth"):
        continue
    pi = base.get("place_in") or {}
    print(f"## {book} ({base['pages']} pages, {base['bytes_in'] / 1e6:.2f} MB, {codecs(base['filters_in'])})\n")
    print(f"Input: {pi.get('sizes')} page sizes, text off-centre {pi.get('offcentre_median', 0) * 100:.1f} % (median), "
          f"sways {pi.get('sway_iqr', 0) * 100:.1f} % (IQR), text {pi.get('text_width_share', 0) * 100:.0f} % of the width\n")
    print("| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway "
          "| text width |")
    print("|---|---:|---:|---:|---|---:|---:|---:|---:|---:|")
    for t in tools:
        r = row_of(book, t)
        if r is None:
            continue
        if "error" in r:
            print(f"| {NAMES[t]} | failed | | | | | | | | |")
            continue
        po = r.get("place_out") or {}

        def pct(k: str, nd: int = 1) -> str:
            return f"{po[k] * 100:.{nd}f} %" if k in po else "no text found"

        print(f"| {NAMES[t]} | {r['seconds']:.0f} | {r['bytes_out'] / base['bytes_in'] * 100:.0f} % | "
              f"{r['kept_streams'] * 100:.0f} % | {codecs(r.get('filters_out'))} | {r['pages_out']} | {po.get('sizes', '')} | "
              f"{pct('offcentre_median')} | {pct('sway_iqr')} | {pct('text_width_share', 0)} |")
    print()
    ri = base.get("rule_in")
    if ri and ri.get("pages"):
        print(f"### Turns against the printed rule ({ri['pages']} pages of this excerpt carry a rule between their columns)\n")
        print("The rule is the print's own straight line: on a level page it stands upright. Its lean is read on every "
              "tool's output by [`bench/rules.py`](../rules.py), independently of safha's measures. \"Made worse\": the rule "
              "leans at least 0.1 degree more than on the scan; \"level made to lean\": a rule within 0.15 degree of upright "
              "on the scan, beyond 0.3 after.\n")
        print(f"On the scan: median lean {ri['median']:.2f} deg; {ri['le02']} of {ri['pages']} pages within 0.2 deg; "
              f"{ri['gt05']} beyond 0.5 deg.\n")
        print("| tool | pages read | median lean (deg) | within 0.2 deg | beyond 0.5 deg | made worse | level made to lean |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for t in tools:
            r = row_of(book, t)
            if r is None or "error" in r:
                continue
            ro, rc = r.get("rule_out"), r.get("rule_change")
            if not ro:
                print(f"| {NAMES[t]} | n/a (pages reflowed) | | | | | |")
                continue
            print(f"| {NAMES[t]} | {ro['pages']} | {ro['median']:.2f} | {ro['le02']} | {ro['gt05']} | {rc['worse']} | "
                  f"{rc['level_made_to_lean']} |")
        print()
truth = [r for r in rows if r["book"].startswith("truth") and r["tool"] != "input"]
if truth:
    print("## Known truth: 3 pages tilted 1 deg, 3 warped pages (upper lines level, lower lines at 1.5 deg)\n")
    print("A synthetic book (`tests/synth.py`): the tilted pages should be levelled; a warped page has no single turn, and a "
          "tool that turns it by its average makes the level upper lines lean.\n")
    print("| tool | size | tilted pages levelled | warped pages whose level lines were made to lean |")
    print("|---|---:|---:|---:|")
    tb = next((r for r in rows if r["book"].startswith("truth") and r["tool"] == "input"), None)
    for t in tools:
        r = next((x for x in truth if x["tool"] == t), None)
        if r is None:
            continue
        if "error" in r:
            print(f"| {NAMES[t]} | failed | | |")
        else:
            size = f"{r['bytes_out'] / tb['bytes_in'] * 100:.0f} %" if tb else ""
            print(f"| {NAMES[t]} | {size} | {r.get('tilted_levelled')} | {r.get('warped_wrongly_turned')} |")
