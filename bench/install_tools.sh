#!/usr/bin/env bash
# Install the tools safha is compared with (Ubuntu 24.04). Versions used for the published numbers:
#   k2pdfopt 2.55, unpaper 7.0.0, OCRmyPDF 15.2.0 (tesseract 5.3.4, jbig2enc 0.28, pngquant 2.18),
#   pdfCropMargins 2.2.1, Briss 2.0-alpha-5.
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
"$UV" pip install -q --python "$TOOLS/pcm/bin/python" "pdfCropMargins==2.2.1"
if [ ! -d "$TOOLS/briss" ]; then
  curl -sL -o "$TOOLS/briss.zip" https://github.com/mbaeuerle/Briss-2.0/releases/download/v2.0-alpha-5/Briss-2.0.zip
  unzip -q -o "$TOOLS/briss.zip" -d "$TOOLS/briss"
fi
k2pdfopt -h 2>/dev/null | head -2 || true
unpaper --version; ocrmypdf --version; "$TOOLS/pcm/bin/pdf-crop-margins" --version 2>/dev/null || true
find "$TOOLS/briss" -name '*.jar' | head -3
