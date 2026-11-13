"""Benchmark: run safha over many books and report speed, size before and after, and what it did.

    safha bench books/ -o results.json --book-jobs 8 --jobs 4

Writes ``results.json`` (one row per book) and ``results.md`` (a table and the totals).
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import pymupdf

from .profile import Profile


def _books(paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                out += [os.path.join(root, f) for f in sorted(files) if f.lower().endswith(".pdf")]
        elif p.lower().endswith(".pdf"):
            out.append(p)
    return sorted(out)


def one(args: tuple) -> dict[str, Any]:
    path, prof, jobs, keep, compact = args
    from .apply import apply_recipe
    from .engine import plan
    from .pdf import image_filters

    row: dict[str, Any] = {"book": os.path.basename(path), "bytes_in": os.path.getsize(path)}
    try:
        d = pymupdf.open(path)
        row["pages_in"] = d.page_count
        row["filters"] = image_filters(d)
        d.close()
        t0 = time.time()
        rec = plan(path, prof, jobs=jobs)
        row["plan_s"] = round(time.time() - t0, 2)
        s = rec["summary"]
        row.update(mode=rec["mode"], why=rec.get("why"), reasons=rec.get("reasons"), pages=s["pages"], text=s["text"],
                   turned=len(s["turned"]), sheared=len(s["sheared"]), frame_turn=len(s["frame_turn"]),
                   two_angles=len(s["two_angles"]), unsure=len(s["unsure_tilt"]) + len(s["untreated_tilt"]),
                   whole=len(s["whole"]), split=len(rec.get("split") or {}), gain=rec.get("gain"), size=rec.get("size"))
        out_dir = keep or tempfile.mkdtemp(prefix="safha-bench-")
        dst = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".safha.pdf")
        if rec["mode"] in ("crop", "level") or rec.get("split"):
            t1 = time.time()
            rep = apply_recipe(path, rec, dst, compact=compact)
            row["apply_s"] = round(time.time() - t1, 2)
            row["bytes_out"] = rep["bytes_out"]
            d = pymupdf.open(dst)
            row["filters_out"] = image_filters(d)
            row["sizes_out"] = len({(round(p.rect.width, 1), round(p.rect.height, 1)) for p in d})
            d.close()
            if not keep:
                os.remove(dst)
        else:
            row["bytes_out"] = row["bytes_in"]
        if not keep:
            with contextlib.suppress(OSError):
                os.rmdir(out_dir)
        row["seconds"] = round(time.time() - t0, 2)
        row["pages_per_s"] = round(row["pages"] / max(row["seconds"], 1e-6), 2)
    except Exception as e:  # a broken book is a result too
        row["error"] = f"{type(e).__name__}: {e}"
    return row


def bench(paths: list[str], prof: Profile, out: str | None = None, jobs: int = 1, book_jobs: int = 1,
          keep: str | None = None, compact: bool = False) -> list[dict[str, Any]]:
    books = _books(paths)
    if not books:
        raise ValueError("no PDF found")
    if keep:
        os.makedirs(keep, exist_ok=True)
    t0 = time.time()
    args = [(b, prof, jobs, keep, compact) for b in books]
    rows: list[dict[str, Any]] = []
    if book_jobs > 1:
        with ProcessPoolExecutor(book_jobs) as ex:
            for r in ex.map(one, args):
                rows.append(r)
                print(_line(r), flush=True)
    else:
        for a in args:
            r = one(a)
            rows.append(r)
            print(_line(r), flush=True)
    wall = time.time() - t0
    md = report(rows, prof, wall, jobs, book_jobs)
    print(md)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"profile": prof.name, "wall_s": round(wall, 1), "jobs": jobs, "book_jobs": book_jobs,
                       "cpus": os.cpu_count(), "rows": rows}, f, ensure_ascii=False, indent=1)
        with open(os.path.splitext(out)[0] + ".md", "w", encoding="utf-8") as f:
            f.write(md)
    return rows


def _line(r: dict) -> str:
    if "error" in r:
        return f"ERROR {r['book']}: {r['error']}"
    return (f"{r['book'][:48]:<48} {r['pages']:>5} p  {r['mode']:<5} turned {r['turned']:>3}  "
            f"{r['bytes_in'] / 1e6:7.2f} -> {r['bytes_out'] / 1e6:7.2f} MB  {r['pages_per_s']:6.2f} p/s")


def report(rows: list[dict], prof: Profile, wall: float, jobs: int, book_jobs: int) -> str:
    ok = [r for r in rows if "error" not in r]
    pages = sum(r["pages"] for r in ok)
    cpu = sum(r["seconds"] for r in ok)
    bi, bo = sum(r["bytes_in"] for r in ok), sum(r["bytes_out"] for r in ok)
    changed = [r for r in ok if r["mode"] in ("crop", "level")]
    same_codecs = sum(1 for r in changed if r.get("filters") == r.get("filters_out"))
    lines = [f"# safha bench ({prof.name} profile)", "",
             "| book | pages | mode | turned | two angles | whole | MB in | MB out | pages/s |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['book']} | | error | | | | | | |")
            continue
        lines.append(f"| {r['book']} | {r['pages']} | {r['mode']} | {r['turned']} | {r['two_angles']} | {r['whole']} | "
                     f"{r['bytes_in'] / 1e6:.2f} | {r['bytes_out'] / 1e6:.2f} | {r['pages_per_s']:.2f} |")
    lines += ["", f"- books: {len(rows)} ({len(rows) - len(ok)} errors); pages: {pages}; cropped or levelled: {len(changed)}",
              f"- speed: {pages / max(cpu, 1e-6):.2f} pages/s per book worker ({jobs} page workers each); wall {wall:.0f} s "
              f"with {book_jobs} books at once: {pages / max(wall, 1e-6):.1f} pages/s",
              f"- size: {bi / 1e6:.1f} MB in, {bo / 1e6:.1f} MB out ({(bo - bi) / max(bi, 1) * 100:+.2f} %)",
              f"- image codecs unchanged in {same_codecs} of {len(changed)} written books",
              f"- pages turned: {sum(r['turned'] for r in ok)} of {sum(r['text'] for r in ok)} text pages "
              f"({sum(r['turned'] for r in ok) / max(1, sum(r['text'] for r in ok)) * 100:.1f} %); "
              f"left as scanned for lines at two angles: {sum(r['two_angles'] for r in ok)}; "
              f"sheared prints levelled: {sum(r['sheared'] for r in ok)}"]
    return "\n".join(lines) + "\n"
