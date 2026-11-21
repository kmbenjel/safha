# Contributing to safha

Thank you for helping. Bug reports with a page that went wrong are the most useful contribution of all.

## Reporting a page the method got wrong
1. Run `safha sheet book.pdf --pages N -o page.jpg` and attach the image (or `safha inspect book.pdf` for the numbers).
2. Say what you expected: "the footnote was cut", "this page is tilted and was not turned", "this page was turned and
   now its upper lines lean".
3. If the book is public domain, link it. Never attach a copyrighted scan.

Each fixed report becomes a test: a synthetic page in `tests/synth.py` with the same shape, or a page of a
public-domain fixture with a golden recipe in `tests/golden/`.

## Development
```bash
git clone https://github.com/kmbenjel/safha && cd safha
make install          # uv venv + editable install with the dev tools
make lint test
```
- Python 3.10+, type hints, `ruff check .` clean.
- A change to a measure (`measure.py`, `tilt.py`) or a decision (`decide.py`, `detect.py`) must keep the golden
  recipes (`make golden`, then review `git diff tests/golden/` page by page: a moved box or a new turn needs a reason).
- A change that could turn more pages must be checked on real books, not only on the regression cases: compare the
  turns before and after over a corpus and look at the pages that changed. `safha bench CORPUS --recipes DIR` keeps
  every book's recipe (run it before and after, into two folders, and compare them page by page);
  `python bench/rule_audit.py CORPUS DIR` holds every turn against the print's own rules; `safha sheet book.pdf --recipe
  book.recipe.json --pages N` shows a page. Regression cases only cover pages that were once wrong; a new false turn
  elsewhere is invisible to them.
- The declared dependency floors are tested (CI job `lowest`): `uv pip install --resolution lowest-direct -e ".[dev]"`.
- The images are never decoded and re-encoded: any feature that would need it does not belong in safha.

## Releases
Semantic versioning; every change is listed in `CHANGELOG.md`.
