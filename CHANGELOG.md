# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Pages kept sideways and shown upright by `/Rotate`, and pages counted in another unit (`/UserUnit`), are measured as
  a reader shows them and written back in the file's own coordinates: turned, cropped and split like any other page.
- A MediaBox or CropBox kept in an object of its own, written from its top left to its bottom right corner, holding a
  number that is an object of its own, or inherited from the page tree is read all the same.
- `safha bench --recipes DIR` keeps each book's recipe and uses a recipe already there (same file, safha version and
  profile) instead of planning again; the report gives pages per CPU-second beside the wall clock.
- `--pages` takes open ranges (`10-`: from page 10 to the last).
- `safha profiles -v` says what every setting does; every command's `--help` opens with what the command does and
  closes with examples.
- Python 3.14 and 3.15 are tested; so are the oldest dependencies the package allows (CI job `lowest`).
- Benchmark: `bench/rule_audit.py` holds every turn of a corpus run against the print's own rules; the head-to-head
  judges turns with readers that owe nothing to safha's measures (`bench/rules.py`), on a known-truth book of level,
  tilted and warped pages drawn at scan resolution; it records the version of every tool that ran and runs the
  current OCRmyPDF release beside the distribution's; `bench/compare_report.py --summary` prints the README's table,
  `bench/docs_numbers.py` every other number the docs quote, and `bench/big_file.sh` measures a large file.

### Changed
- A leaf lying askew on a dark scanner bed, or on a microfilm's black field, is turned level and cropped like its
  neighbours: the scanner bands of a turned page are read behind the blank wedge the turn leaves at its edges.
- A sheet of another size (a quarter larger than the median page: a plate, a chart, a frame filmed at another scale)
  is shown whole, drawn smaller, and has no say in whether one box fits the book.
- The output is written and checked under a temporary name and takes its own only when every check has passed: a
  refused run leaves nothing on disk, and an output that was there before stays as it was.
- One plain line and exit status 2 for every ordinary mistake: a recipe that is missing, no JSON, no recipe or a newer
  safha's; an output folder that does not exist; a folder or an image given for the book; page lists that are no
  numbers or go beyond the book. Profile settings are checked when they are set.
- A file left as it is says why in quiet mode too; a book shorter than `min_text_pages` is told the setting that
  crops it. A damaged file is named as such; one MuPDF could repair is written whole, and the run says that
  `safha restore` cannot give the original back from it.
- The progress is told as the pages are worked, a few at a time; a failed page stops the run at once.
- `safha drop --blank` reads a blank leaf inside its scanner bands: a blank leaf on a dark bed is blank.
- The original's bytes are compared and restored a megabyte at a time (books of several gigabytes).
- PyMuPDF 1.25 or newer is required: the oldest release with which the method gives the recipes the tests hold it to.

## [0.1.0] - 2026-11-13

### Added
- `safha crop`: lossless crop of scanned book PDFs: one box size for the whole book, placed on each page's text; page
  images are never decoded or re-encoded (CropBox and drawing matrices only).
- Deskew by a lossless `cm` matrix, kept only when two independent measures read the turned page level; pages whose
  lines lie at two angles (warped leaves) are left as scanned; a printed frame decides its page's tilt; a sheared print
  (parallelogram frame) is sheared level.
- Pages in two columns with a printed rule between them (dictionaries, indexes, journals) are turned by that rule; on
  any page the text's margins and its printed rules can refuse a turn (`edge_guard`), and the page is then left as
  scanned and listed.
- Two-page spreads split into two pages (LTR or RTL order), wrap-around covers split.
- Scanner bands, edge shadows, specks, dust, photocopy borders, streaks and blots kept outside the box; marginal notes,
  figures and printed rules kept inside it.
- One page size for the whole book; pages that hold more than the box are shown whole, drawn smaller.
- No line of print is cut: after the box is placed, the page image itself is read around its edge (letters the edge
  runs through, rows that go on beyond it, running heads and last lines above and below it) and the box slides, grows
  or gives way to the whole page.
- Recipes: `safha plan` writes the per-page decisions as JSON; `safha apply` writes them into a copy, checked (same
  pages, same image streams, one page size).
- Reversible output: the original bytes stay at the start of the file; `safha restore` gives them back (MD5 checked).
- `safha drop` (blank pages, covers), `safha inspect`, `safha sheet` (before | after contact sheet, HTML review),
  `safha bench`, `safha same-scan`, `safha demo`, `safha profiles`.
- Profiles `warraq` (default), `reader`, `eink`, `crop-only`; every threshold settable (`--set`, TOML/JSON files).
