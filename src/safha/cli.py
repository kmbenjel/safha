"""safha command line. Run ``safha --help`` or ``safha COMMAND --help``."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from . import __version__
from .profile import PROFILES, load_profile

EPILOG = """examples:
  safha crop book.pdf                       writes book.safha.pdf next to it (lossless)
  safha crop book.pdf -o out.pdf --profile eink --jobs 4
  safha plan book.pdf -o book.recipe.json   measure and decide only; review or edit the recipe
  safha apply book.pdf book.recipe.json -o out.pdf
  safha inspect book.pdf                    page by page: kind, tilt, turn, flags
  safha sheet book.pdf -o sheet.png         before | after contact sheet of the telling pages
  safha restore book.safha.pdf -o original.pdf
  safha demo                                runs on the bundled public-domain sample in under a minute

profiles: warraq (default: crop when it pays), reader (always crop, smaller margins), eink (tight margins),
          crop-only (never turn a page); any setting: --set margin=0.05 --set skew_min=0.3
"""


def _profile(a: argparse.Namespace) -> Any:
    over: dict[str, Any] = {}
    for kv in a.set or []:
        if "=" not in kv:
            raise SystemExit(f"--set expects NAME=VALUE, got {kv!r}")
        k, v = kv.split("=", 1)
        over[k.strip().replace("-", "_")] = v.strip()
    if getattr(a, "always", False):
        over["always"] = "true"
    if getattr(a, "no_deskew", False):
        over["deskew"] = "false"
    if getattr(a, "rtl", False):
        over["direction"] = "rtl"
    if getattr(a, "ltr", False):
        over["direction"] = "ltr"
    if getattr(a, "split", None):
        over["split"] = a.split
    try:
        return load_profile(a.profile, over)
    except ValueError as e:
        raise SystemExit(f"safha: {e}") from None


def _pages(spec: str | None) -> list[int]:
    out: set[int] = set()
    for part in (spec or "").split(","):
        if not part.strip():
            continue
        lo, _, hi = part.partition("-")
        out |= set(range(int(lo), int(hi or lo) + 1))
    return sorted(out)


class _Bar:
    def __init__(self, quiet: bool):
        self.quiet = quiet or not sys.stderr.isatty()
        self.t0 = time.time()

    def __call__(self, stage: str, done: int, n: int) -> None:
        if self.quiet:
            return
        w = 28
        k = int(w * done / max(1, n))
        sys.stderr.write(f"\r{stage:>8} [{'#' * k}{'.' * (w - k)}] {done}/{n} pages  {time.time() - self.t0:5.1f}s")
        if done >= n:
            sys.stderr.write("\n")
        sys.stderr.flush()


def _mb(n: int) -> str:
    return f"{n / 1e6:.2f} MB" if n >= 1e5 else f"{n / 1e3:.1f} KB"


def summary_lines(rec: dict) -> list[str]:
    s = rec["summary"]
    out = [f"{rec['source']['file']}: {s['pages']} pages ({s['text']} text), mode {rec['mode'].upper()}"
           + (f" -- {rec['why']}" if rec.get("why") else "")]
    if rec.get("reasons"):
        out.append("  why: " + "; ".join(rec["reasons"]))
    if rec.get("size"):
        out.append(f"  one page size {rec['size'][0]:.1f} x {rec['size'][1]:.1f} pt, text {round((rec['gain'] - 1) * 100)} % "
                   f"larger on screen" + ("; framed" if rec.get("framed") else "")
                   + ("; clean margins" if rec.get("clean_margins") else ""))
    if rec.get("split"):
        order = {"rtl": "right page first", "ltr": "left page first"}.get(rec.get("direction"), "")
        out.append(f"  split {len(rec['split'])} two-page sheets ({rec.get('direction')}: {order})"
                   + ("; the file has no text layer to tell the reading order from: for right-to-left books add --rtl"
                      if rec.get("direction_from") == "default" else ""))
    lab = {"turned": "turned level", "sheared": "sheared level", "frame_turn": "squared by a printed frame",
           "by_columns": "two columns, turned by the printed rule between them",
           "tilt_disputed": "the witnesses of the tilt disagree, left as scanned",
           "two_angles": "lines at two angles, left as scanned", "unsure_tilt": "tilt not confirmed, left as scanned",
           "untreated_tilt": "tilt seen but no safe turn", "whole": "content wider than the box, shown whole",
           "curved": "curved, levelled as far as one turn can", "moved": "content moved to stay centred",
           "print_held": "box moved or grown to keep a line of print whole"}
    for k, v in lab.items():
        if s.get(k):
            pg = ", ".join(map(str, s[k][:12])) + (" ..." if len(s[k]) > 12 else "")
            out.append(f"  {len(s[k]):>4} {v}: p. {pg}")
    return out


def cmd_plan(a: argparse.Namespace) -> int:
    from .engine import plan

    rec = plan(a.pdf, _profile(a), jobs=a.jobs, progress=_Bar(a.quiet), drop=_pages(a.drop))
    out = a.output or os.path.splitext(a.pdf)[0] + ".recipe.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1 if a.pretty else None)
    if not a.quiet:
        print("\n".join(summary_lines(rec)))
        print(f"recipe: {out}")
    return 0


def _apply_report(rep: dict) -> str:
    d = rep["bytes_out"] - rep["bytes_in"]
    return (f"  {rep['pages']} pages: {rep['cropped']} cropped, {rep['turned']} turned/moved, {rep['scaled']} scaled"
            + (f", {rep['dropped']} dropped" if rep.get("dropped") else "")
            + f"; {_mb(rep['bytes_in'])} -> {_mb(rep['bytes_out'])} ({'+' if d >= 0 else ''}{_mb(d)}); images untouched"
            + ("; reversible (safha restore)" if rep.get("reversible") else ""))


def cmd_crop(a: argparse.Namespace) -> int:
    from .apply import ApplyError, apply_recipe
    from .engine import plan

    rec = plan(a.pdf, _profile(a), jobs=a.jobs, progress=_Bar(a.quiet), drop=_pages(a.drop))
    if not a.quiet:
        print("\n".join(summary_lines(rec)))
    if a.recipe:
        with open(a.recipe, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    if rec["mode"] == "skip" and not rec.get("drop") and not rec.get("split"):
        print("  nothing to do: the file is left as it is"
              + (" (crop anyway: --profile reader or --always)" if "good scan" in (rec.get("why") or "") else ""))
        return 0
    out = a.output or os.path.splitext(a.pdf)[0] + ".safha.pdf"
    try:
        rep = apply_recipe(a.pdf, rec, out, compact=a.compact)
    except ApplyError as e:
        print(f"safha: {e}", file=sys.stderr)
        return 2
    if not a.quiet:
        print(_apply_report(rep))
        print(f"written: {out}")
    if a.sheet:
        from .sheet import contact_sheet

        print(f"sheet: {contact_sheet(a.pdf, rec, a.sheet)}")
    return 0


def cmd_apply(a: argparse.Namespace) -> int:
    from .apply import ApplyError, apply_recipe

    with open(a.recipe, encoding="utf-8") as f:
        rec = json.load(f)
    out = a.output or os.path.splitext(a.pdf)[0] + ".safha.pdf"
    try:
        rep = apply_recipe(a.pdf, rec, out, compact=a.compact, check_source=not a.force)
    except ApplyError as e:
        print(f"safha: {e}", file=sys.stderr)
        return 2
    print(_apply_report(rep))
    print(f"written: {out}")
    return 0


def cmd_inspect(a: argparse.Namespace) -> int:
    from .engine import plan

    if a.pdf.endswith(".json"):
        with open(a.pdf, encoding="utf-8") as f:
            rec = json.load(f)
    else:
        rec = plan(a.pdf, _profile(a), jobs=a.jobs, progress=_Bar(a.quiet))
    if a.json:
        json.dump(rec, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    print("\n".join(summary_lines(rec)))
    print(f"\n{'page':>5} {'kind':<8} {'tilt':>7} {'turn':>7} {'after':>12}  {'shown part (pt)':<28} flags")
    for p in rec["pages"]:
        tilt = f"{p['tilt']:+.2f}" if p.get("tilt") is not None else ""
        turn = f"{p['skew']:+.3f}" if p.get("skew") else ""
        if p.get("shear"):
            turn += f" sh{p['shear']:+.2f}"
        after = "/".join(f"{v:.2f}" for v in p["after"]) if p.get("after") else ""
        sh = p.get("show") or p.get("crop")
        box = " ".join(f"{v:.0f}" for v in sh) if sh else "whole page"
        print(f"{p['n']:>5} {p['kind']:<8} {tilt:>7} {turn:>7} {after:>12}  {box:<28} {' '.join(p.get('flags') or [])}")
    return 0


def cmd_sheet(a: argparse.Namespace) -> int:
    from .engine import plan
    from .sheet import contact_sheet, html_review

    if a.recipe:
        with open(a.recipe, encoding="utf-8") as f:
            rec = json.load(f)
    else:
        rec = plan(a.pdf, _profile(a), jobs=a.jobs, progress=_Bar(a.quiet))
    if a.html:
        out = html_review(a.pdf, rec, a.html, every=a.all)
        print(f"review page: {out}")
    if a.cards:
        from .sheet import review_cards

        print(f"review cards: {review_cards(a.pdf, rec, a.cards)}")
    if a.output or not (a.html or a.cards):
        pages = [(n - 1, "asked") for n in _pages(a.pages)] if a.pages else None
        out = contact_sheet(a.pdf, rec, a.output or os.path.splitext(a.pdf)[0] + ".sheet.jpg", pages, px=a.px, cols=a.cols)
        print(f"sheet: {out}")
    return 0


def cmd_restore(a: argparse.Namespace) -> int:
    from .apply import ApplyError, restore

    out = a.output or a.pdf.replace(".safha.pdf", "") + ".restored.pdf"
    try:
        r = restore(a.pdf, out)
    except ApplyError as e:
        print(f"safha: {e}", file=sys.stderr)
        return 2
    print(f"restored {r['bytes']} bytes (MD5 {r['md5']} checked): {out}")
    return 0


def cmd_drop(a: argparse.Namespace) -> int:
    """drop pages losslessly (blank pages and outer covers that put the numbering out of step)"""
    import pymupdf

    from .apply import ApplyError, apply_recipe
    from .engine import file_md5
    from .pages import ink_share

    pages = _pages(a.pages)
    doc = pymupdf.open(a.pdf)
    if a.blank:
        n = doc.page_count
        lead = []
        for i in list(range(min(4, n))) + list(range(max(0, n - 4), n)):
            if ink_share(doc[i]) < 0.001:
                lead.append(i + 1)
        pages = sorted(set(pages) | set(lead))
    for k in pages:
        if not 1 <= k <= doc.page_count:
            raise SystemExit(f"safha: page {k} is not in the file ({doc.page_count} pages)")
        e = ink_share(doc[k - 1])
        if e > 0.001 and not a.force:
            raise SystemExit(f"safha: page {k} is not blank (ink {e:.2%}); add --force to drop it anyway")
    n0 = doc.page_count
    doc.close()
    if not pages:
        print("no page to drop")
        return 0
    rec = {"mode": "skip", "pages": [{}] * n0, "drop": pages,
           "source": {"md5": file_md5(a.pdf)}}
    out = a.output or os.path.splitext(a.pdf)[0] + ".safha.pdf"
    try:
        rep = apply_recipe(a.pdf, rec, out)
    except ApplyError as e:
        print(f"safha: {e}", file=sys.stderr)
        return 2
    print(f"dropped p. {', '.join(map(str, pages))}: {n0} -> {rep['pages']} pages, reversible; written: {out}")
    return 0


def cmd_bench(a: argparse.Namespace) -> int:
    from .bench import bench

    bench(a.paths, _profile(a), out=a.output, jobs=a.jobs, book_jobs=a.book_jobs, keep=a.keep, compact=a.compact)
    return 0


def cmd_same(a: argparse.Namespace) -> int:
    from .samescan import compare

    r = compare(a.a, a.b)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["verdict"] == "same scan" else 1


def cmd_demo(a: argparse.Namespace) -> int:
    from .demo import run_demo

    return run_demo(a.output, jobs=a.jobs)


def cmd_profiles(a: argparse.Namespace) -> int:
    for name, p in PROFILES.items():
        d = p.diff()
        print(f"{name:<10} " + (", ".join(f"{k}={v}" for k, v in d.items()) if d else "(the default)"))
    if a.verbose:
        print()
        for k, v in PROFILES["warraq"].to_dict().items():
            print(f"  {k} = {v}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="safha", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EPILOG,
        description="Lossless crop, deskew and split for scanned book PDFs. The page images are never re-encoded: "
                    "only each page's visible box and drawing matrix change, so the file keeps its quality and size.")
    ap.add_argument("--version", action="version", version=f"safha {__version__}")
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND")

    def common(p: argparse.ArgumentParser, out: str | None = "output PDF") -> None:
        p.add_argument("--profile", "-p", metavar="NAME|FILE", help="warraq (default), reader, eink, crop-only, or a .toml/.json file")
        p.add_argument("--set", action="append", metavar="NAME=VALUE", help="change one setting (see `safha profiles -v`)")
        p.add_argument("--jobs", "-j", type=int, default=max(1, min(4, (os.cpu_count() or 2) - 1)), help="worker processes")
        p.add_argument("--quiet", "-q", action="store_true")
        p.add_argument("--always", action="store_true", help="crop even a well-made scan the crop changes little")
        p.add_argument("--no-deskew", action="store_true", help="never turn a page")
        p.add_argument("--split", choices=("auto", "always", "never"), help="two-page spreads (default auto)")
        g = p.add_mutually_exclusive_group()
        g.add_argument("--rtl", action="store_true", help="split spreads right page first (Arabic, Hebrew, ...)")
        g.add_argument("--ltr", action="store_true", help="split spreads left page first")
        if out:
            p.add_argument("--output", "-o", metavar="FILE", help=out)

    p = sub.add_parser("crop", help="measure, decide and write the cropped PDF (lossless)")
    p.add_argument("pdf")
    common(p, "output PDF (default: <name>.safha.pdf)")
    p.add_argument("--recipe", metavar="FILE", help="also save the recipe (JSON)")
    p.add_argument("--sheet", metavar="IMAGE", help="also write a before | after contact sheet")
    p.add_argument("--drop", metavar="PAGES", help="drop these pages too, e.g. 1,2 or 1-3 (numbered after a split)")
    p.add_argument("--compact", action="store_true", help="rewrite the file (smaller; not restorable by truncation)")
    p.set_defaults(fn=cmd_crop)

    p = sub.add_parser("plan", help="measure and decide only: write the recipe (JSON)")
    p.add_argument("pdf")
    common(p, "recipe file (default: <name>.recipe.json)")
    p.add_argument("--drop", metavar="PAGES", help="pages to drop, e.g. 1,2")
    p.add_argument("--pretty", action="store_true", help="indented JSON")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("apply", help="write a recipe into a copy of the PDF (lossless, checked)")
    p.add_argument("pdf")
    p.add_argument("recipe")
    p.add_argument("--output", "-o", metavar="FILE")
    p.add_argument("--compact", action="store_true", help="rewrite the file (smaller; not restorable by truncation)")
    p.add_argument("--force", action="store_true", help="apply even if the PDF is not the one the recipe was made from")
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("inspect", help="page by page: kind, measured tilt, turn, shown part, flags")
    p.add_argument("pdf", help="a PDF, or a recipe .json")
    common(p, None)
    p.add_argument("--json", action="store_true", help="the whole recipe as JSON on stdout")
    p.set_defaults(fn=cmd_inspect)

    p = sub.add_parser("sheet", help="before | after contact sheet (PNG/JPEG/WebP) or an HTML review folder")
    p.add_argument("pdf")
    common(p, "image file (default: <name>.sheet.jpg)")
    p.add_argument("--recipe", metavar="FILE", help="use this recipe instead of planning again")
    p.add_argument("--pages", metavar="PAGES", help="these pages instead of the telling ones, e.g. 3,10-12")
    p.add_argument("--html", metavar="DIR", help="write an HTML review folder")
    p.add_argument("--all", action="store_true", help="every page in the HTML review")
    p.add_argument("--cards", metavar="DIR", help="write review cards (cards.jsonl + images) for a review page")
    p.add_argument("--px", type=int, default=360, help="width of each image")
    p.add_argument("--cols", type=int, default=2, help="pairs per row")
    p.set_defaults(fn=cmd_sheet)

    p = sub.add_parser("restore", help="the original file back from a safha output (byte for byte, MD5 checked)")
    p.add_argument("pdf")
    p.add_argument("--output", "-o", metavar="FILE")
    p.set_defaults(fn=cmd_restore)

    p = sub.add_parser("drop", help="drop blank pages or covers losslessly (reversible)")
    p.add_argument("pdf")
    p.add_argument("--pages", metavar="PAGES", help="1-based, e.g. 1 or 1,2 or 1-3")
    p.add_argument("--blank", action="store_true", help="also every blank page among the first and last four")
    p.add_argument("--force", action="store_true", help="drop a page that is not blank (a cover)")
    p.add_argument("--output", "-o", metavar="FILE")
    p.set_defaults(fn=cmd_drop)

    p = sub.add_parser("bench", help="run over PDFs or folders: pages/s, size before/after, pages turned")
    p.add_argument("paths", nargs="+")
    common(p, "write the results here (.json and .md next to it)")
    p.add_argument("--book-jobs", type=int, default=1, help="books processed at once")
    p.add_argument("--keep", metavar="DIR", help="keep the output PDFs here")
    p.add_argument("--compact", action="store_true")
    p.set_defaults(fn=cmd_bench)

    p = sub.add_parser("same-scan", help="are two PDFs the same scan? (page images compared by their raw streams)")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(fn=cmd_same)

    p = sub.add_parser("demo", help="crop the bundled public-domain samples and write a before | after sheet")
    p.add_argument("--output", "-o", default="safha-demo", metavar="DIR")
    p.add_argument("--jobs", "-j", type=int, default=2)
    p.set_defaults(fn=cmd_demo)

    p = sub.add_parser("profiles", help="list the built-in profiles (-v: every setting)")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_profiles)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    for k in ("pdf",):
        v = getattr(a, k, None)
        if v and not os.path.exists(v):
            print(f"safha: no such file: {v}", file=sys.stderr)
            return 2
    try:
        return int(a.fn(a) or 0)
    except KeyboardInterrupt:
        return 130
    except (ValueError, RuntimeError) as e:
        print(f"safha: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
