#!/usr/bin/env bash
# Head-to-head of safha with pdfCropMargins, Briss, k2pdfopt, unpaper and OCRmyPDF --deskew on the same public-domain
# pages. Reproduce:
#   bench/install_tools.sh                       # the other tools and their optional helpers (Ubuntu 24.04)
#   python bench/fetch_corpus.py ~/safha-corpus  # public-domain scans from the Internet Archive
#   bench/compare.sh ~/safha-corpus ~/safha-compare
# Writes WORK/compare.json and bench/results/compare.md. Heavy: run it on a machine with a few cores to spare.
set -euo pipefail
CORPUS=${1:?corpus dir}; WORK=${2:?work dir}; PAGES=${PAGES:-40}
HERE=$(cd "$(dirname "$0")" && pwd); PY=${PY:-$HERE/../.venv/bin/python}
mkdir -p "$WORK/in"
# the same excerpt of each book for every tool: $PAGES pages copied object for object, from page 11 on (after the
# front matter); the dictionary from page 401 on (two columns with a printed rule between them: real truth for turns)
for spec in almuqaddimah00ibnk:10 chronologyofanci00biru:10 in.ernet.dli.2015.361017:10 arabicmanuscript28loui:10 \
            dictionnairefra00lagogoog:400; do
  id=${spec%%:*}; first=${spec##*:}
  [ -f "$WORK/in/$id.pdf" ] || "$PY" - "$CORPUS/$id.pdf" "$WORK/in/$id.pdf" "$PAGES" "$first" <<'PYEOF'
import sys, pymupdf
src, dst, n, first = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
d = pymupdf.open(src); o = pymupdf.open()
start = min(first, max(0, d.page_count - n))
o.insert_pdf(d, from_page=start, to_page=min(d.page_count, start + n) - 1)
o.save(dst, garbage=3)
PYEOF
done
"$PY" "$HERE/compare.py" "$WORK" "$WORK"/in/*.pdf
"$PY" "$HERE/compare_report.py" "$WORK"/compare*.json > "$HERE/results/compare.md"
cat "$HERE/results/compare.md"
