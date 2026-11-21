#!/usr/bin/env bash
# Head-to-head of safha with pdfCropMargins, Briss, k2pdfopt, unpaper and OCRmyPDF --deskew on the same public-domain
# pages. Reproduce:
#   bench/install_tools.sh                       # the other tools and their optional helpers (Ubuntu 24.04)
#   python bench/fetch_corpus.py ~/safha-corpus  # public-domain scans from the Internet Archive
#   bench/compare.sh ~/safha-corpus ~/safha-compare
# Writes one JSON per book to bench/results/compare/ and the report bench/results/compare.md; the README's table is
# `python bench/compare_report.py --summary bench/results/compare/*.json`. Heavy (an hour or more): run it on a machine
# with cores to spare. PAR books run at once (default 3), each tool with JOBS worker processes (default 8).
set -euo pipefail
CORPUS=${1:?corpus dir}; WORK=${2:?work dir}; PAGES=${PAGES:-40}; PAR=${PAR:-3}
HERE=$(cd "$(dirname "$0")" && pwd); PY=${PY:-$HERE/../.venv/bin/python}
export KEEP_BOOKS=${KEEP_BOOKS:-chronologyofanci00biru}   # the outputs scripts/make_media.py draws from are kept
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
# one run per book, $PAR at a time, then the book with a known truth
running=0
for f in "$WORK"/in/*.pdf; do
  b=$(basename "$f" .pdf)
  ( NO_TRUTH=1 OUT="compare-$b.json" "$PY" "$HERE/compare.py" "$WORK" "$f" > "$WORK/compare-$b.log" 2>&1 ) &
  running=$((running + 1))
  if [ "$running" -ge "$PAR" ]; then wait -n || true; running=$((running - 1)); fi
done
wait
OUT=compare-truth.json "$PY" "$HERE/compare.py" "$WORK" > "$WORK/compare-truth.log" 2>&1
mkdir -p "$HERE/results/compare"
cp "$WORK"/compare-*.json "$HERE/results/compare/"
"$PY" "$HERE/compare_report.py" "$HERE"/results/compare/compare-*.json > "$HERE/results/compare.md"
cat "$HERE/results/compare.md"
