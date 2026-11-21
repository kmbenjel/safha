# Head-to-head on the same public-domain pages

Each book: a 40-page excerpt copied object for object from the Internet Archive scan. Every tool runs the way a careful user would run it for this job (the commands are in [`bench/compare.py`](../compare.py), `run_tool`): OCRmyPDF with its optional helpers installed (jbig2enc, pngquant), first exactly as it runs by default (PDF/A output, written through Ghostscript), then writing a plain PDF at its default lossless optimisation and at its two lossy ones, in the version the distribution packages and, for the two main settings, in the current release; unpaper on the pages rendered by poppler (`pdftoppm`) at the scan's own resolution and kind, written back as CCITT G4 (1-bit pages) or JPEG 85 (poppler's 1-bit rendering is not the same twice, so unpaper's figures on bitonal scans move by a page or two from one run to the next); k2pdfopt in its default reflow mode and in copy mode with auto-straighten (one output page per source page). k2pdfopt's lossless trim mode (`-mode tm`, native PDF output) needs a build with MuPDF; the Ubuntu 24.04 package has none and writes no file in that mode, so it is not measured.

Versions that ran: safha 0.1.0; PyMuPDF 2.1; MuPDF 1.28.6; pdfCropMargins 2.2.1; Briss-2.0-all.jar; k2pdfopt v2.55 (w/DjVuLibre,OCR) (c) 2024, GPLv3, http://willus.com; unpaper 7.0.0; OCRmyPDF 15.2.0+dfsg1; OCRmyPDF (new) 17.14.2; tesseract 5.3.4; Ghostscript 10.02.1; jbig2enc 0.28; pngquant 2.18.0 (January 2023); poppler pdftoppm version 24.02.0; img2pdf 0.5.1.

Who judges: sizes, streams and codecs are read from the files; the turns are judged by [`bench/rules.py`](../rules.py), which owes nothing to safha's own measures; the place of the text (the last three columns) is read on every tool's output alike with safha's own text-block measure, and describes the outputs.

Size: output / input. Off-centre: median distance of the text block's centre from the page's centre; sway: its interquartile range from page to page (shares of the page width; lower is steadier). Text width: the text block's median share of the page width (higher is larger text on screen). Times are wall-clock on a shared machine with several tools running at once: read them as orders of magnitude.

## All books in one table

| | size of the output | image streams kept byte for byte | level pages left level | tilted pages levelled | warped pages wrongly turned | ruled pages upright after | ruled pages made worse |
|---|---:|---:|---:|---:|---:|---:|---:|
| the scans as they are | | | 8/8 | 0/8 | 0/8 | 18 of 39 | |
| safha | 100-102 % | 100 % | 8/8 | 8/8 | 0/8 | 29 (of 38 read) | 0 |
| safha `--profile reader` | 100-102 % | 100 % | 8/8 | 8/8 | 0/8 | 29 (of 38 read) | 0 |
| pdfCropMargins `-u -s` | 100 % | 100 % | 8/8 | 0/8 | 0/8 | 18 (of 38 read) | 0 |
| Briss | 100 % | 100 % | 8/8 | 0/8 | 0/8 | 19 | 0 |
| k2pdfopt (default: reflow) | 25-326 % | 0 % | n/a (pages reflowed) | n/a (pages reflowed) | n/a (pages reflowed) | n/a | n/a |
| k2pdfopt `-mode copy -as` | 330-1177 % | 0 % | 8/8 | 8/8 | 2/8 | 11 | 21 |
| unpaper (G4 / JPEG 85 out) | 79-860 % | 0 % | 6/8 | 2/8 | 4/8 | 27 | 5 |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 73-1453 % | 0 % | 8/8 | 8/8 | 4/8 | 35 | 1 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 79-6551 % | 0 % | 8/8 | 8/8 | 4/8 | 35 | 1 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 79-2980 % | 0 % | 8/8 | 8/8 | 4/8 | 35 | 1 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 79-2311 % | 0 % | 8/8 | 8/8 | 4/8 | 35 | 1 |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 91-834 % | 0 % | 8/8 | 8/8 | 4/8 | 35 | 1 |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 91-6306 % | 0 % | 8/8 | 8/8 | 4/8 | 35 | 1 |

Level, tilted, warped: the book with a known truth (below). Ruled pages: the dictionary's pages that carry a printed rule between their columns ("upright": within 0.2 degree; "made worse": at least 0.1 degree further from upright than on the scan).

## almuqaddimah00ibnk.pdf (40 pages, 3.26 MB, JPX)

Input: 19 page sizes, text off-centre 2.8 % (median), sways 5.6 % (IQR), text 84 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 21 | 100 % | 100 % | JPX | 40 | 19 | 2.8 % | 5.6 % | 84 % |
| safha `--profile reader` | 29 | 100 % | 100 % | JPX | 40 | 19 | 2.8 % | 5.6 % | 84 % |
| pdfCropMargins `-u -s` | 23 | 100 % | 100 % | JPX | 40 | 1 | 2.7 % | 3.9 % | 81 % |
| Briss | 2 | 100 % | 100 % | JPX | 40 | 1 | no text found | no text found | no text found |
| k2pdfopt (default: reflow) | 209 | 260 % | 0 % | Flate | 46 | 1 | 1.4 % | 3.0 % | 85 % |
| k2pdfopt `-mode copy -as` | 112 | 1177 % | 0 % | Flate | 40 | 19 | 2.2 % | 5.5 % | 82 % |
| unpaper (G4 / JPEG 85 out) | 193 | 830 % | 0 % | DCT | 40 | 16 | 2.3 % | 5.4 % | 83 % |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 161 | 783 % | 0 % | Flate | 40 | 19 | 2.7 % | 5.2 % | 83 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 190 | 6551 % | 0 % | Flate | 40 | 19 | 2.9 % | 5.7 % | 83 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 248 | 2980 % | 0 % | Flate | 40 | 19 | 2.5 % | 5.7 % | 83 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 220 | 1907 % | 0 % | Flate | 40 | 19 | 2.5 % | 5.7 % | 83 % |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 64 | 728 % | 0 % | Flate | 40 | 19 | 2.9 % | 5.7 % | 83 % |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 56 | 6306 % | 0 % | Flate | 40 | 19 | 2.9 % | 5.6 % | 83 % |

## arabicmanuscript28loui.pdf (40 pages, 13.12 MB, JPX)

Input: 18 page sizes, text off-centre 0.7 % (median), sways 1.1 % (IQR), text 67 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 124 | 102 % | 100 % | JPX | 79 | 1 | 0.3 % | 0.7 % | 79 % |
| safha `--profile reader` | 111 | 102 % | 100 % | JPX | 79 | 1 | 0.2 % | 0.4 % | 82 % |
| pdfCropMargins `-u -s` | 30 | 100 % | 100 % | JPX | 40 | 1 | 3.1 % | 1.4 % | 63 % |
| Briss | 4 | 100 % | 100 % | JPX | 40 | 1 | 23.1 % | 1.3 % | 54 % |
| k2pdfopt (default: reflow) | 965 | 25 % | 0 % | Flate | 23 | 1 | 1.9 % | 0.0 % | 73 % |
| k2pdfopt `-mode copy -as` | 202 | 330 % | 0 % | Flate | 40 | 18 | 0.5 % | 1.3 % | 67 % |
| unpaper (G4 / JPEG 85 out) | 321 | 426 % | 0 % | DCT | 40 | 18 | 1.4 % | 2.7 % | 66 % |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 795 | 1453 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 712 | 5414 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 901 | 2214 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 953 | 2311 % | 0 % | Flate | 40 | 18 | 0.8 % | 1.1 % | 67 % |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 173 | 655 % | 0 % | Flate | 40 | 18 | 0.6 % | 1.2 % | 67 % |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 156 | 3422 % | 0 % | Flate | 40 | 18 | 0.6 % | 1.2 % | 67 % |

## chronologyofanci00biru.pdf (40 pages, 2.50 MB, JPX)

Input: 1 page sizes, text off-centre 1.3 % (median), sways 2.8 % (IQR), text 76 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 30 | 100 % | 100 % | JPX | 40 | 1 | 1.3 % | 1.6 % | 81 % |
| safha `--profile reader` | 40 | 100 % | 100 % | JPX | 40 | 1 | 0.5 % | 1.1 % | 83 % |
| pdfCropMargins `-u -s` | 19 | 100 % | 100 % | JPX | 40 | 1 | 1.4 % | 2.8 % | 78 % |
| Briss | 2 | 100 % | 100 % | JPX | 40 | 1 | 15.8 % | 1.4 % | 55 % |
| k2pdfopt (default: reflow) | 224 | 326 % | 0 % | Flate | 88 | 1 | 0.5 % | 0.7 % | 98 % |
| k2pdfopt `-mode copy -as` | 83 | 620 % | 0 % | Flate | 39 | 1 | 1.2 % | 2.5 % | 77 % |
| unpaper (G4 / JPEG 85 out) | 94 | 860 % | 0 % | DCT | 40 | 1 | 0.7 % | 1.0 % | 77 % |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 100 | 810 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.4 % | 76 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 93 | 4917 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.4 % | 76 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 138 | 2135 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.7 % | 76 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 159 | 1565 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.7 % | 76 % |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 55 | 834 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.4 % | 76 % |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 43 | 4846 % | 0 % | Flate | 40 | 1 | 1.3 % | 2.4 % | 76 % |

## dictionnairefra00lagogoog.pdf (40 pages, 1.19 MB, JBIG2)

Input: 1 page sizes, text off-centre 3.6 % (median), sways 7.0 % (IQR), text 81 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 11 | 101 % | 100 % | JBIG2 | 40 | 1 | 0.1 % | 0.1 % | 87 % |
| safha `--profile reader` | 8 | 101 % | 100 % | JBIG2 | 40 | 1 | 0.1 % | 0.1 % | 90 % |
| pdfCropMargins `-u -s` | 2 | 100 % | 100 % | JBIG2 | 40 | 1 | 3.7 % | 7.1 % | 82 % |
| Briss | 10 | 100 % | 100 % | JBIG2 | 40 | 2 | 1.3 % | 2.6 % | 90 % |
| k2pdfopt (default: reflow) | 130 | 296 % | 0 % | Flate | 62 | 1 | 3.3 % | 5.5 % | 88 % |
| k2pdfopt `-mode copy -as` | 68 | 840 % | 0 % | Flate | 40 | 1 | 3.7 % | 7.2 % | 82 % |
| unpaper (G4 / JPEG 85 out) | 142 | 140 % | 0 % | CCITTFax | 40 | 1 | 0.1 % | 0.3 % | 81 % |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 21 | 131 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 23 | 138 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 26 | 138 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 23 | 138 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.1 % | 81 % |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 26 | 171 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.2 % | 81 % |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 26 | 171 % | 0 % | JBIG2 | 40 | 1 | 3.6 % | 7.2 % | 81 % |

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
| unpaper (G4 / JPEG 85 out) | 39 | 0.08 | 27 | 2 | 5 | 3 |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 39 | 0.06 | 35 | 0 | 1 | 0 |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 39 | 0.06 | 35 | 0 | 1 | 0 |

## in.ernet.dli.2015.361017.pdf (40 pages, 1.65 MB, CCITTFax)

Input: 1 page sizes, text off-centre 0.6 % (median), sways 0.9 % (IQR), text 79 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | pages | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| safha | 6 | 101 % | 100 % | CCITTFax | 40 | 1 | 0.1 % | 0.1 % | 88 % |
| safha `--profile reader` | 7 | 101 % | 100 % | CCITTFax | 40 | 1 | 0.0 % | 0.1 % | 91 % |
| pdfCropMargins `-u -s` | 1 | 100 % | 100 % | CCITTFax | 40 | 1 | 0.7 % | 1.2 % | 95 % |
| Briss | 7 | 100 % | 100 % | CCITTFax | 40 | 2 | 0.6 % | 1.2 % | 94 % |
| k2pdfopt (default: reflow) | 108 | 236 % | 0 % | Flate | 70 | 2 | 0.2 % | 0.0 % | 98 % |
| k2pdfopt `-mode copy -as` | 52 | 368 % | 0 % | Flate | 40 | 1 | 0.7 % | 1.0 % | 78 % |
| unpaper (G4 / JPEG 85 out) | 132 | 79 % | 0 % | CCITTFax | 40 | 1 | 0.2 % | 0.3 % | 79 % |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 20 | 73 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 22 | 79 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 22 | 79 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 23 | 79 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 1.1 % | 79 % |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 17 | 91 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 0.9 % | 79 % |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 20 | 91 % | 0 % | JBIG2 | 40 | 1 | 0.6 % | 0.9 % | 79 % |

## Known truth: a book drawn as a 300 dpi scan, 8 pages level, 8 tilted, 8 warped

A synthetic book ([`bench/compare.py`](../compare.py), `truth_book`; pages drawn by `tests/synth.py`). The tilted pages lean by 0.5, 1, 2 and 3 degrees either way and should be levelled. The warped pages have their upper half's lines level and their lower half's turned by 1 to 2.5 degrees: no single turn levels such a page, and a tool that turns it by its average makes the level upper lines lean. The level pages should stay level.

Read on every output by the projection profile of its lines (`rules.lines_lean`: nothing of safha's own): a page is level when its lines lie within 0.2 degree; a warped page is wrongly turned when its upper lines, level on the scan, lean by more than 0.35 degree.

| tool | size | level pages left level | tilted pages levelled | warped pages whose level lines were made to lean |
|---|---:|---:|---:|---:|
| the book as drawn | | 8/8 | 0/8 | 0/8 |
| safha | 100 % | 8/8 | 8/8 | 0/8 |
| safha `--profile reader` | 100 % | 8/8 | 8/8 | 0/8 |
| pdfCropMargins `-u -s` | 100 % | 8/8 | 0/8 | 0/8 |
| Briss | 100 % | 8/8 | 0/8 | 0/8 |
| k2pdfopt (default: reflow) | 44 % | n/a (pages reflowed) | n/a (pages reflowed) | n/a (pages reflowed) |
| k2pdfopt `-mode copy -as` | 67 % | 8/8 | 8/8 | 2/8 |
| unpaper (G4 / JPEG 85 out) | 167 % | 6/8 | 2/8 | 4/8 |
| OCRmyPDF 15.2.0 `--deskew` (its default: PDF/A output) | 103 % | 8/8 | 8/8 | 4/8 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf` | 284 % | 8/8 | 8/8 | 4/8 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O2` | 79 % | 8/8 | 8/8 | 4/8 |
| OCRmyPDF 15.2.0 `--deskew --output-type pdf -O3` | 59 % | 8/8 | 8/8 | 4/8 |
| OCRmyPDF 17.14.2 `--deskew` (its default: PDF/A output) | 117 % | 8/8 | 8/8 | 4/8 |
| OCRmyPDF 17.14.2 `--deskew --output-type pdf` | 335 % | 8/8 | 8/8 | 4/8 |
