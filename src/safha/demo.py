"""``safha demo``: crop the two bundled public-domain samples and write before | after sheets, in under a minute.

* sample-latin.pdf: six pages of al-Biruni, *The Chronology of Ancient Nations* (London, 1879), bitonal JBIG2;
* sample-spreads.pdf: five two-page microfilm frames of an Arabic manuscript (UCLA Library), split right page first.
Sources: docs/media/SOURCES.md.
"""

from __future__ import annotations

import json
import os
import time
from importlib import resources

from .apply import apply_recipe
from .engine import plan
from .profile import load_profile
from .sheet import contact_sheet

SAMPLES = [("sample-latin.pdf", {}), ("sample-spreads.pdf", {"direction": "rtl"})]


def run_demo(outdir: str = "safha-demo", jobs: int = 2) -> int:
    from .cli import _apply_report, summary_lines

    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    for name, opts in SAMPLES:
        src = str(resources.files("safha") / "data" / name)
        prof = load_profile(None, {"min_text_pages": 1, **opts})
        rec = plan(src, prof, jobs=jobs)
        stem = os.path.join(outdir, name[:-4])
        with open(stem + ".recipe.json", "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        rep = apply_recipe(src, rec, stem + ".safha.pdf")
        sheet = contact_sheet(src, rec, stem + ".sheet.jpg")
        print("\n".join(summary_lines(rec)))
        print(_apply_report(rep))
        print(f"  -> {stem}.safha.pdf, {sheet}\n")
    print(f"done in {time.time() - t0:.0f} s. Open the .sheet.jpg files: the scan with the box in red | what a reader shows.")
    return 0
