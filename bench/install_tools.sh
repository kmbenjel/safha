#!/usr/bin/env bash
# Install the tools safha is compared with (Ubuntu 24.04): k2pdfopt, unpaper, OCRmyPDF (with tesseract, jbig2enc and
# pngquant), pdfCropMargins and Briss, and beside the distribution's OCRmyPDF its current release from PyPI. The
# versions that ran are written with every result (bench/compare.py, versions) and printed in the report.
# ScanTailor Advanced has no batch command line (GUI only) and is compared from its documentation.
set -euo pipefail
TOOLS=${TOOLS:-$HOME/safha-tools}
mkdir -p "$TOOLS"
sudo apt-get update -qq
# jbig2 (jbig2enc) and pngquant are OCRmyPDF's optional helpers: with them it writes 1-bit pages as lossless JBIG2 and
# can quantise PNGs (--optimize 2/3); a careful user installs both, so the comparison does too.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq k2pdfopt unpaper ocrmypdf tesseract-ocr ghostscript \
  poppler-utils img2pdf netpbm default-jre-headless unzip jbig2 pngquant >/dev/null
UV=${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}
"$UV" venv -q --python 3.12 "$TOOLS/pcm"
"$UV" pip install -q --python "$TOOLS/pcm/bin/python" "pdfCropMargins==${PDFCROPMARGINS:-2.2.1}"
# the current OCRmyPDF release beside the distribution's: the comparison runs both
"$UV" venv -q --python 3.12 "$TOOLS/ocrmypdf-new"
"$UV" pip install -q --python "$TOOLS/ocrmypdf-new/bin/python" "ocrmypdf==${OCRMYPDF_NEW:-17.14.2}"
if [ ! -d "$TOOLS/briss" ]; then
  curl -sL -o "$TOOLS/briss.zip" https://github.com/mbaeuerle/Briss-2.0/releases/download/v2.0-alpha-5/Briss-2.0.zip
  unzip -q -o "$TOOLS/briss.zip" -d "$TOOLS/briss"
fi
k2pdfopt -? 2>/dev/null | head -1 || true
unpaper --version; ocrmypdf --version; "$TOOLS/ocrmypdf-new/bin/ocrmypdf" --version
"$TOOLS/pcm/bin/pdf-crop-margins" --version 2>/dev/null || true
find "$TOOLS/briss" -name '*.jar' | head -3
