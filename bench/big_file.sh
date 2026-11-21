#!/usr/bin/env bash
# Time and peak memory of safha on a large file: a book joined to itself COPIES times (default 10), one page dropped
# (the copy, the incremental save and every check), then the original restored from the output and compared.
#   bench/big_file.sh BOOK.pdf [COPIES] [WORKDIR]
# Needs GNU time (/usr/bin/time). The README's figures: bench/big_file.sh CORPUS/in.ernet.dli.2015.207418.pdf
set -euo pipefail
BOOK=${1:?a PDF}; N=${2:-10}; W=${3:-$(mktemp -d)}
HERE=$(cd "$(dirname "$0")" && pwd); PY=${PY:-$HERE/../.venv/bin/python}
mkdir -p "$W"
"$PY" - "$BOOK" "$W/big.pdf" "$N" <<'PYEOF'
import sys

import pymupdf

src, dst, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
out = pymupdf.open()
for _ in range(n):  # the book opened anew each time, so its image streams are copied each time
    d = pymupdf.open(src)
    out.insert_pdf(d)
    d.close()
out.save(dst)
print(f"{out.page_count} pages")
PYEOF
echo "$(wc -c < "$W/big.pdf") bytes"
m() { /usr/bin/time -f "    %M KB of memory at peak, %e s" "$@"; }
m "$PY" -m safha drop "$W/big.pdf" --pages 1 --force -o "$W/out.pdf"
m "$PY" -m safha restore "$W/out.pdf" -o "$W/back.pdf"
cmp "$W/big.pdf" "$W/back.pdf" && echo "the restored file is the original, byte for byte"
rm -f "$W/big.pdf" "$W/out.pdf" "$W/back.pdf"
