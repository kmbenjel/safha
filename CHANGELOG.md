# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-13

### Added
- `safha crop`: lossless crop of scanned book PDFs: one box size for the whole book, placed on each page's text; page
  images are never decoded or re-encoded (CropBox and drawing matrices only).
- Deskew by a lossless `cm` matrix, kept only when two independent measures read the turned page level; pages whose
  lines lie at two angles (warped leaves) are left as scanned; a printed frame decides its page's tilt; a sheared print
  (parallelogram frame) is sheared level.
- Two-page spreads split into two pages (LTR or RTL order), wrap-around covers split.
- Scanner bands, edge shadows, specks, dust, photocopy borders, streaks and blots kept outside the box; marginal notes,
  figures and printed rules kept inside it.
- One page size for the whole book; pages that hold more than the box are shown whole, drawn smaller.
- Recipes: `safha plan` writes the per-page decisions as JSON; `safha apply` writes them into a copy, checked (same
  pages, same image streams, one page size).
- Reversible output: the original bytes stay at the start of the file; `safha restore` gives them back (MD5 checked).
- `safha drop` (blank pages, covers), `safha inspect`, `safha sheet` (before | after contact sheet, HTML review),
  `safha bench`, `safha same-scan`, `safha demo`, `safha profiles`.
- Profiles `warraq` (default), `reader`, `eink`, `crop-only`; every threshold settable (`--set`, TOML/JSON files).
