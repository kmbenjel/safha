#!/usr/bin/env bash
# Head-to-head of safha with pdfCropMargins, Briss, k2pdfopt, unpaper and OCRmyPDF --deskew on the same public-domain
# pages. Reproduce:
#   bench/install_tools.sh                       # the other tools, pinned versions (Ubuntu 24.04)
#   python bench/fetch_corpus.py ~/safha-corpus  # public-domain scans from the Internet Archive
#   bench/compare.sh ~/safha-corpus ~/safha-compare
# Writes WORK/compare.json and bench/results/compare.md. Heavy: run it on a machine with a few cores to spare.
set -euo pipefail
CORPUS=${1:?corpus dir}; WORK=${2:?work dir}; PAGES=${PAGES:-40}
HERE=$(cd "$(dirname "$0")" && pwd); PY=${PY:-$HERE/../.venv/bin/python}
mkdir -p "$WORK/in"
# the same excerpt of each book for every tool: the first $PAGES pages after the front matter, copied object for object
for id in almuqaddimah00ibnk chronologyofanci00biru in.ernet.dli.2015.361017 arabicmanuscript28loui; do
  [ -f "$WORK/in/$id.pdf" ] || "$PY" - "$CORPUS/$id.pdf" "$WORK/in/$id.pdf" "$PAGES" <<'PYEOF'
import sys, pymupdf
src, dst, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
d = pymupdf.open(src); o = pymupdf.open()
start = min(10, max(0, d.page_count - n))
o.insert_pdf(d, from_page=start, to_page=min(d.page_count, start + n) - 1)
o.save(dst, garbage=3)
PYEOF
done
"$PY" "$HERE/compare.py" "$WORK" "$WORK"/in/*.pdf
"$PY" "$HERE/compare_report.py" "$WORK"/compare*.json > "$HERE/results/compare.md"
cat "$HERE/results/compare.md"
