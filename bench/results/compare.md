# Head-to-head on the same public-domain pages

Each book: a 40-page excerpt copied object for object from the Internet Archive scan. Every tool runs the way a careful user would run it for this job (the commands are in [`bench/compare.py`](../compare.py), `run_tool`): OCRmyPDF with its optional helpers installed (jbig2enc, pngquant), first exactly as it runs by default (PDF/A output, written through Ghostscript), then writing a plain PDF at its default lossless optimisation and at its two lossy ones; unpaper at the scan's own resolution and kind, written back as CCITT G4 (1-bit pages) or JPEG 85; k2pdfopt in its default reflow mode and in copy mode with auto-straighten (one output page per source page). k2pdfopt's lossless trim mode (`-mode tm`, native PDF output) needs a build with MuPDF; the Ubuntu 24.04 package has none and writes no file in that mode, so it is not measured.

Size: output / input. Off-centre: median distance of the text block's centre from the page's centre; sway: its interquartile range from page to page (shares of the page width; lower is steadier). Text width: the text block's median share of the page width (higher is larger text on screen). Times are wall-clock on a shared 32-core machine with several tools running at once: read them as orders of magnitude.

## almuqaddimah00ibnk.pdf (40 pages, 3.26 MB, JPX)

Input: 19 page sizes, text off-centre 2.8 % (median), sways 5.6 % (IQR), text 84 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 27 | 100 % | 100 % | JPX | 40 | 19 | 2.8 % | 5.6 % | 84 % |
| safha `--profile reader` | 27 | 100 % | 100 % | JPX | 40 | 19 | 2.8 % | 5.6 % | 84 % |
| pdfCropMargins `-u -s` | 37 | 100 % | 100 % | JPX | 40 | 1 | 2.7 % | 3.9 % | 81 % |
| Briss | 3 | 100 % | 100 % | JPX | 40 | 1 | no text found | no text found | no text found |
| k2pdfopt (default: reflow) | 253 | 260 % | 0 % | Flate | 46 | 1 | 1.4 % | 3.0 % | 85 % |
| k2pdfopt `-mode copy -as` | 147 | 1177 % | 0 % | Flate | 40 | 19 | 2.2 % | 5.5 % | 82 % |
| unpaper (G4 / JPEG 85 out) | 209 | 830 % | 0 % | DCT | 40 | 16 | 2.3 % | 5.4 % | 83 % |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 166 | 783 % | 0 % | Flate | 40 | 19 | 2.7 % | 5.2 % | 83 % |
| OCRmyPDF `--deskew --output-type pdf` | 124 | 6551 % | 0 % | Flate | 40 | 19 | 2.9 % | 5.7 % | 83 % |
| OCRmyPDF `--deskew --output-type pdf -O2` | 153 | 2980 % | 0 % | Flate | 40 | 19 | 2.5 % | 5.7 % | 83 % |
| OCRmyPDF `--deskew --output-type pdf -O3` | 169 | 1907 % | 0 % | Flate | 40 | 19 | 2.5 % | 5.7 % | 83 % |

## chronologyofanci00biru.pdf (40 pages, 2.50 MB, JPX)

Input: 1 page sizes, text off-centre 1.3 % (median), sways 2.8 % (IQR), text 76 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 39 | 100 % | 100 % | JPX | 40 | 1 | 1.3 % | 1.6 % | 81 % |
| safha `--profile reader` | 39 | 100 % | 100 % | JPX | 40 | 1 | 0.5 % | 1.1 % | 83 % |
| pdfCropMargins `-u -s` | 27 | 100 % | 100 % | JPX | 40 | 1 | 1.4 % | 2.8 % | 78 % |
| Briss | 2 | 100 % | 100 % | JPX | 40 | 1 | 15.8 % | 1.4 % | 55 % |
| k2pdfopt (default: reflow) | 248 | 326 % | 0 % | Flate | 88 | 1 | 0.5 % | 0.7 % | 98 % |
| k2pdfopt `-mode copy -as` | 133 | 620 % | 0 % | Flate | 39 | 1 | 1.2 % | 2.5 % | 77 % |
| unpaper (G4 / JPEG 85 out) | 101 | 860 % | 0 % | DCT | 40 | 1 | 0.7 % | 1.0 % | 77 % |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 121 | 810 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.4 % | 76 % |
| OCRmyPDF `--deskew --output-type pdf` | 78 | 4917 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.4 % | 76 % |
| OCRmyPDF `--deskew --output-type pdf -O2` | 90 | 2135 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.7 % | 76 % |
| OCRmyPDF `--deskew --output-type pdf -O3` | 104 | 1565 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.7 % | 76 % |

## in.ernet.dli.2015.361017.pdf (40 pages, 1.65 MB, CCITTFax)

Input: 1 page sizes, text off-centre 0.6 % (median), sways 0.9 % (IQR), text 79 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 11 | 101 % | 100 % | CCITTFax | 40 | 1 | 0.1 % | 0.1 % | 88 % |
| safha `--profile reader` | 12 | 101 % | 100 % | CCITTFax | 40 | 1 | 0.0 % | 0.1 % | 91 % |
| pdfCropMargins `-u -s` | 1 | 100 % | 100 % | CCITTFax | 40 | 1 | 0.7 % | 1.2 % | 95 % |
| Briss | 6 | 100 % | 100 % | CCITTFax | 40 | 2 | 0.6 % | 1.2 % | 94 % |
| k2pdfopt (default: reflow) | 131 | 236 % | 0 % | Flate | 70 | 2 | 0.2 % | 0.0 % | 98 % |
| k2pdfopt `-mode copy -as` | 73 | 368 % | 0 % | Flate | 40 | 1 | 0.7 % | 1.0 % | 78 % |
| unpaper (G4 / JPEG 85 out) | 141 | 79 % | 0 % | CCITTFax | 40 | 1 | 0.2 % | 0.3 % | 79 % |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 20 | 73 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF `--deskew --output-type pdf` | 19 | 79 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF `--deskew --output-type pdf -O2` | 20 | 79 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF `--deskew --output-type pdf -O3` | 19 | 79 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |

## arabicmanuscript28loui.pdf (40 pages, 13.12 MB, JPX)

Input: 18 page sizes, text off-centre 0.7 % (median), sways 1.1 % (IQR), text 67 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 155 | 102 % | 100 % | JPX | 79 | 1 | 0.3 % | 0.7 % | 79 % |
| safha `--profile reader` | 131 | 102 % | 100 % | JPX | 79 | 1 | 0.2 % | 0.5 % | 82 % |
| pdfCropMargins `-u -s` | 48 | 100 % | 100 % | JPX | 40 | 1 | 3.1 % | 1.4 % | 63 % |
| Briss | 5 | 100 % | 100 % | JPX | 40 | 1 | 23.1 % | 1.3 % | 54 % |
| k2pdfopt (default: reflow) | 1012 | 25 % | 0 % | Flate | 23 | 1 | 1.9 % | 0.0 % | 73 % |
| k2pdfopt `-mode copy -as` | 313 | 330 % | 0 % | Flate | 40 | 18 | 0.5 % | 1.3 % | 67 % |
| unpaper (G4 / JPEG 85 out) | 494 | 426 % | 0 % | DCT | 40 | 18 | 1.4 % | 2.7 % | 66 % |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 786 | 1453 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF `--deskew --output-type pdf` | 673 | 5414 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF `--deskew --output-type pdf -O2` | 752 | 2214 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF `--deskew --output-type pdf -O3` | 792 | 2395 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |

## dictionnairefra00lagogoog.pdf (40 pages, 1.19 MB, JBIG2)

Input: 1 page sizes, text off-centre 3.6 % (median), sways 7.0 % (IQR), text 81 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 16 | 101 % | 100 % | JBIG2 | 40 | 1 | 0.1 % | 0.1 % | 87 % |
| safha `--profile reader` | 13 | 101 % | 100 % | JBIG2 | 40 | 1 | 0.1 % | 0.1 % | 90 % |
| pdfCropMargins `-u -s` | 2 | 100 % | 100 % | JBIG2 | 40 | 1 | 3.7 % | 7.1 % | 82 % |
| Briss | 13 | 100 % | 100 % | JBIG2 | 40 | 2 | 1.3 % | 2.6 % | 90 % |
| k2pdfopt (default: reflow) | 167 | 296 % | 0 % | Flate | 62 | 1 | 3.3 % | 5.5 % | 88 % |
| k2pdfopt `-mode copy -as` | 77 | 840 % | 0 % | Flate | 40 | 1 | 3.7 % | 7.2 % | 82 % |
| unpaper (G4 / JPEG 85 out) | 214 | 140 % | 0 % | CCITTFax | 40 | 1 | 0.1 % | 0.2 % | 81 % |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 28 | 131 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF `--deskew --output-type pdf` | 20 | 138 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF `--deskew --output-type pdf -O2` | 24 | 138 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF `--deskew --output-type pdf -O3` | 17 | 138 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |

### Turns against the printed rule (39 pages of this excerpt carry a rule between their columns)

The rule is the print's own straight line: on a level page it stands upright. Its lean is read on every tool's output by [`bench/rules.py`](../rules.py), independently of safha's measures. "Made worse": the rule leans at least 0.1 degree more than on the scan; "level made to lean": a rule within 0.15 degree of upright on the scan, beyond 0.3 after.

On the scan: median lean 0.21 deg; 18 of 39 pages within 0.2 deg; 10 beyond 0.5 deg.

| tool | pages read | median lean (deg) | within 0.2 deg | beyond 0.5 deg | made worse | level made to lean |
|---|---:|---:|---:|---:|---:|---:|
| safha | 38 | 0.10 | 29 | 2 | 0 | 0 |
| safha `--profile reader` | 38 | 0.09 | 29 | 2 | 0 | 0 |
| pdfCropMargins `-u -s` | 38 | 0.21 | 18 | 9 | 0 | 0 |
| Briss | 39 | 0.21 | 19 | 9 | 0 | 0 |
| k2pdfopt (default: reflow) | n/a (pages reflowed) | | | | | |
| k2pdfopt `-mode copy -as` | 39 | 0.35 | 11 | 15 | 21 | 10 |
| unpaper (G4 / JPEG 85 out) | 39 | 0.14 | 29 | 0 | 6 | 1 |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF `--deskew --output-type pdf` | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF `--deskew --output-type pdf -O2` | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF `--deskew --output-type pdf -O3` | 39 | 0.06 | 35 | 0 | 1 | 0 |

## Known truth: 3 pages tilted 1 deg, 3 warped pages (upper lines level, lower lines at 1.5 deg)

A synthetic book (`tests/synth.py`): the tilted pages should be levelled; a warped page has no single turn, and a tool that turns it by its average makes the level upper lines lean.

| tool | size | tilted pages levelled | warped pages whose level lines were made to lean |
|---|---:|---:|---:|
| safha | 100 % | 3/3 | 0/3 |
| safha `--profile reader` | 100 % | 3/3 | 0/3 |
| pdfCropMargins `-u -s` | 100 % | 0/3 | 0/3 |
| Briss | 100 % | 0/3 | 0/3 |
| k2pdfopt (default: reflow) | 151 % | n/a (pages reflowed) | n/a (pages reflowed) |
| k2pdfopt `-mode copy -as` | 70 % | 3/3 | 1/3 |
| unpaper (G4 / JPEG 85 out) | 129 % | 0/3 | 2/3 |
| OCRmyPDF `--deskew` (its default: PDF/A output) | 87 % | 3/3 | 3/3 |
| OCRmyPDF `--deskew --output-type pdf` | 310 % | 3/3 | 3/3 |
| OCRmyPDF `--deskew --output-type pdf -O2` | 80 % | 3/3 | 3/3 |
| OCRmyPDF `--deskew --output-type pdf -O3` | 60 % | 3/3 | 3/3 |
