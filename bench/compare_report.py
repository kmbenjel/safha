"""compare*.json -> a Markdown report (bench/results/compare.md), or the summary table the README prints.

Usage: python bench/compare_report.py [--summary] RESULTS.json [RESULTS.json ...]
Several result files are merged (one per book, as bench/compare.sh writes them); the first row of each (book, tool)
is kept.
"""

from __future__ import annotations

import json
import sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SUMMARY = "--summary" in sys.argv
rows: list = []
for path in args:
    with open(path, encoding="utf-8") as fh:
        more = json.load(fh)
    seen = {(r["book"], r["tool"]) for r in rows}
    rows += [r for r in more if (r["book"], r["tool"]) not in seen]
inputs = {r["book"]: r for r in rows if r["tool"] == "input"}
versions = next((r for r in rows if r["tool"] == "versions"), {})
ORDER = ["safha", "safha-reader", "pdfCropMargins", "briss", "k2pdfopt", "k2pdfopt-as", "unpaper", "ocrmypdf-pdfa", "ocrmypdf",
         "ocrmypdf-O2", "ocrmypdf-O3", "ocrmypdf-new-pdfa", "ocrmypdf-new"]


def short(key: str) -> str:
    """a version as a number: the first word of the tool's own version line that begins with a digit (or v + digit)"""
    for w in str(versions.get(key, "")).replace(",", " ").split():
        w = w.lstrip("v")
        if w[:1].isdigit():
            return w.split("+")[0]
    return ""


OLD, NEW = short("OCRmyPDF"), short("OCRmyPDF (new)")
NAMES = {"safha": "safha", "safha-reader": "safha `--profile reader`", "pdfCropMargins": "pdfCropMargins `-u -s`",
         "briss": "Briss", "k2pdfopt": "k2pdfopt (default: reflow)", "k2pdfopt-as": "k2pdfopt `-mode copy -as`",
         "unpaper": "unpaper (G4 / JPEG 85 out)", "ocrmypdf-pdfa": f"OCRmyPDF {OLD} `--deskew` (its default: PDF/A output)",
         "ocrmypdf": f"OCRmyPDF {OLD} `--deskew --output-type pdf`", "ocrmypdf-O2": f"OCRmyPDF {OLD} `--deskew --output-type pdf -O2`",
         "ocrmypdf-O3": f"OCRmyPDF {OLD} `--deskew --output-type pdf -O3`",
         "ocrmypdf-new-pdfa": f"OCRmyPDF {NEW} `--deskew` (its default: PDF/A output)",
         "ocrmypdf-new": f"OCRmyPDF {NEW} `--deskew --output-type pdf`"}
tools = [t for t in ORDER if any(r["tool"] == t for r in rows)]
books = [b for b in inputs if not b.startswith("truth")]
truth_in = next((r for b, r in inputs.items() if b.startswith("truth")), None)


def codecs(f: dict | None) -> str:
    return "+".join(k.replace("Decode", "") for k in sorted(f or {})) or "none"


def row_of(book: str, tool: str) -> dict | None:
    return next((x for x in rows if x["book"] == book and x["tool"] == tool), None)


def summary() -> None:
    """one row per tool over every book: the table of the README"""
    ruled = next((b for b in books if inputs[b].get("rule_in") and inputs[b]["rule_in"].get("pages")), None)
    ri = inputs[ruled]["rule_in"] if ruled else None
    print("| | size of the output | image streams kept byte for byte | level pages left level | tilted pages levelled | "
          "warped pages wrongly turned | ruled pages upright after | ruled pages made worse |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    if ri:
        print(f"| the scans as they are | | | {(truth_in or {}).get('level_kept', '')} | {(truth_in or {}).get('tilted_levelled', '')} | "
              f"{(truth_in or {}).get('warped_wrongly_turned', '')} | {ri['le02']} of {ri['pages']} | |")
    for t in tools:
        rr = [r for b in books if (r := row_of(b, t)) is not None and "error" not in r]
        if not rr:
            continue
        size = [100 * r["bytes_out"] / inputs[r["book"]]["bytes_in"] for r in rr]
        kept = [100 * r["kept_streams"] for r in rr]
        tr = next((r for r in rows if r["book"].startswith("truth") and r["tool"] == t and "error" not in r), {})
        ro = row_of(ruled, t) if ruled else None
        rule = ("n/a", "n/a")
        if ro and ro.get("rule_out"):
            n = ro["rule_out"]["pages"]
            rule = (f"{ro['rule_out']['le02']}" + (f" (of {n} read)" if ri and n != ri["pages"] else ""), str(ro["rule_change"]["worse"]))
        sz = f"{min(size):.0f}-{max(size):.0f} %" if round(min(size)) != round(max(size)) else f"{min(size):.0f} %"
        kp = f"{min(kept):.0f}-{max(kept):.0f} %" if round(min(kept)) != round(max(kept)) else f"{min(kept):.0f} %"
        print(f"| {NAMES[t]} | {sz} | {kp} | {tr.get('level_kept', '')} | {tr.get('tilted_levelled', '')} | "
              f"{tr.get('warped_wrongly_turned', '')} | {rule[0]} | {rule[1]} |")


if SUMMARY:
    summary()
    sys.exit(0)

print("# Head-to-head on the same public-domain pages\n")
print("Each book: a 40-page excerpt copied object for object from the Internet Archive scan. Every tool runs the way a "
      "careful user would run it for this job (the commands are in [`bench/compare.py`](../compare.py), `run_tool`): "
      "OCRmyPDF with its optional helpers installed (jbig2enc, pngquant), first exactly as it runs by default (PDF/A "
      "output, written through Ghostscript), then writing a plain PDF at its default lossless optimisation and at its two "
      "lossy ones, in the version the distribution packages and, for the two main settings, in the current release; "
      "unpaper on the pages rendered by poppler (`pdftoppm`) at the scan's own resolution and kind, written back as "
      "CCITT G4 (1-bit pages) or JPEG 85 (poppler's 1-bit rendering is not the same twice, so unpaper's figures on "
      "bitonal scans move by a page or two from one run to the next); "
      "k2pdfopt in its default reflow mode and in copy mode with auto-straighten (one output page per source page). "
      "k2pdfopt's lossless trim mode (`-mode tm`, native PDF output) needs a build with MuPDF; the Ubuntu 24.04 package "
      "has none and writes no file in that mode, so it is not measured.\n")
if versions:
    print("Versions that ran: " + "; ".join(v if str(v).lower().startswith(k.lower()) else f"{k} {v}"
                                            for k, v in versions.items() if k not in ("book", "tool")) + ".\n")
print("Who judges: sizes, streams and codecs are read from the files; the turns are judged by "
      "[`bench/rules.py`](../rules.py), which owes nothing to safha's own measures; the place of the text (the last three "
      "columns) is read on every tool's output alike with safha's own text-block measure, and describes the outputs.\n")
print("Size: output / input. Off-centre: median distance of the text block's centre from the page's centre; sway: its "
      "interquartile range from page to page (shares of the page width; lower is steadier). Text width: the text block's "
      "median share of the page width (higher is larger text on screen). Times are wall-clock on a shared machine with "
      "several tools running at once: read them as orders of magnitude.\n")
print("## All books in one table\n")
summary()
print("\nLevel, tilted, warped: the book with a known truth (below). Ruled pages: the dictionary's pages that carry a "
      "printed rule between their columns (\"upright\": within 0.2 degree; \"made worse\": at least 0.1 degree further "
      "from upright than on the scan).\n")
for book in books:
    base = inputs[book]
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
truth = [r for r in rows if r["book"].startswith("truth") and r["tool"] not in ("input", "versions")]
if truth and truth_in:
    print("## Known truth: a book drawn as a 300 dpi scan, 8 pages level, 8 tilted, 8 warped\n")
    print("A synthetic book ([`bench/compare.py`](../compare.py), `truth_book`; pages drawn by `tests/synth.py`). The tilted "
          "pages lean by 0.5, 1, 2 and 3 degrees either way and should be levelled. The warped pages have their upper half's "
          "lines level and their lower half's turned by 1 to 2.5 degrees: no single turn levels such a page, and a tool that "
          "turns it by its average makes the level upper lines lean. The level pages should stay level.\n")
    print("Read on every output by the projection profile of its lines (`rules.lines_lean`: nothing of safha's own): a page "
          "is level when its lines lie within 0.2 degree; a warped page is wrongly turned when its upper lines, level on the "
          "scan, lean by more than 0.35 degree.\n")
    print("| tool | size | level pages left level | tilted pages levelled | warped pages whose level lines were made to lean |")
    print("|---|---:|---:|---:|---:|")
    print(f"| the book as drawn | | {truth_in.get('level_kept')} | {truth_in.get('tilted_levelled')} | "
          f"{truth_in.get('warped_wrongly_turned')} |")
    for t in tools:
        r = next((x for x in truth if x["tool"] == t), None)
        if r is None:
            continue
        if "error" in r:
            print(f"| {NAMES[t]} | failed | | | |")
        else:
            size = f"{r['bytes_out'] / truth_in['bytes_in'] * 100:.0f} %"
            print(f"| {NAMES[t]} | {size} | {r.get('level_kept')} | {r.get('tilted_levelled')} | {r.get('warped_wrongly_turned')} |")
