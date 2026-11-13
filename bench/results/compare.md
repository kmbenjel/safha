# Head-to-head on the same public-domain pages

Each book: a 40-page excerpt copied object for object from the Internet Archive scan. Size: output / input. Off-centre: median distance of the text block's centre from the page's centre; sway: its interquartile range from page to page (shares of the page width; lower is steadier). Text width: the text block's median share of the page width (higher is larger text on screen). safha runs with its default profile (crops when it pays) and with `--profile reader` (always crops).

## chronologyofanci00biru.pdf (40 pages, 2.50 MB, JPX)

Input: 1 page sizes, text off-centre 1.3 % (median), sways 2.8 % (IQR), text 76 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| safha | 38.4 | 100 % | 100 % | JPX | 1 | 1.4 % | 1.8 % | 81 % |
| safha-reader | 40.1 | 100 % | 100 % | JPX | 1 | 0.5 % | 1.1 % | 83 % |
| pdfCropMargins | 24.6 | 100 % | 100 % | JPX | 1 | 1.4 % | 2.8 % | 78 % |
| briss | 2.2 | 100 % | 100 % | JPX | 1 | 15.8 % | 1.4 % | 55 % |
| k2pdfopt | 309.9 | 326 % | 0 % | Flate | 1 | 0.5 % | 0.7 % | 98 % |
| unpaper | 152.1 | 715 % | 0 % | Flate | 1 | 0.6 % | 0.7 % | 68 % |
| ocrmypdf | 83.5 | 4917 % | 0 % | Flate | 1 | 1.3 % | 2.4 % | 76 % |

## arabicmanuscript28loui.pdf (40 pages, 13.12 MB, JPX)

Input: 18 page sizes, text off-centre 0.7 % (median), sways 1.1 % (IQR), text 67 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| safha | 155.9 | 102 % | 100 % | JPX | 1 | 0.3 % | 0.7 % | 79 % |
| safha-reader | 148.8 | 102 % | 100 % | JPX | 1 | 0.2 % | 0.5 % | 82 % |
| pdfCropMargins | 40.1 | 100 % | 100 % | JPX | 1 | 3.1 % | 1.4 % | 63 % |
| briss | 5.0 | 100 % | 100 % | JPX | 1 | 23.1 % | 1.3 % | 54 % |
| k2pdfopt | 989.6 | 25 % | 0 % | Flate | 1 | 1.9 % | 0.0 % | 73 % |
| unpaper | 355.9 | 541 % | 0 % | Flate | 1 | 1.8 % | 2.8 % | 66 % |
| ocrmypdf | 428.3 | 5414 % | 0 % | Flate | 18 | 0.8 % | 1.1 % | 67 % |

## almuqaddimah00ibnk.pdf (40 pages, 3.26 MB, JPX)

Input: 19 page sizes, text off-centre 2.8 % (median), sways 5.6 % (IQR), text 84 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| safha | 27.7 | 100 % | 100 % | JPX | 19 | 2.3 % | 5.1 % | 91 % |
| safha-reader | 28.0 | 100 % | 100 % | JPX | 19 | 2.3 % | 5.1 % | 91 % |
| pdfCropMargins | 67.8 | 100 % | 100 % | JPX | 1 | 2.7 % | 3.9 % | 81 % |
| briss | 6.1 | 100 % | 100 % | JPX | 1 | no text found | no text found | no text found |
| k2pdfopt | 500.8 | 260 % | 0 % | Flate | 1 | 1.4 % | 3.0 % | 85 % |
| unpaper | 323.6 | 783 % | 0 % | Flate | 1 | 2.8 % | 2.9 % | 77 % |
| ocrmypdf | 137.0 | 6551 % | 0 % | Flate | 19 | 2.9 % | 5.7 % | 83 % |

## in.ernet.dli.2015.361017.pdf (40 pages, 1.65 MB, CCITTFax)

Input: 1 page sizes, text off-centre 0.6 % (median), sways 0.9 % (IQR), text 79 % of the width

| tool | time s | size | image streams kept byte for byte | codecs out | page sizes | text off-centre | sway | text width |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| safha | 10.7 | 101 % | 100 % | CCITTFax | 1 | 0.1 % | 0.1 % | 88 % |
| safha-reader | 10.4 | 101 % | 100 % | CCITTFax | 1 | 0.0 % | 0.1 % | 91 % |
| pdfCropMargins | 1.4 | 100 % | 100 % | CCITTFax | 1 | 0.7 % | 1.2 % | 95 % |
| briss | 6.3 | 100 % | 100 % | CCITTFax | 2 | 0.6 % | 1.2 % | 94 % |
| k2pdfopt | 135.5 | 236 % | 0 % | Flate | 2 | 0.2 % | 0.0 % | 98 % |
| unpaper | 190.7 | 690 % | 0 % | Flate | 1 | 0.1 % | 0.3 % | 73 % |
| ocrmypdf | 8.0 | 286 % | 0 % | Flate | 1 | 0.6 % | 1.1 % | 79 % |

## Known truth: 3 pages tilted 1 deg, 3 warped pages (upper lines level, lower lines at 1.5 deg)

| tool | tilted pages levelled | warped pages wrongly turned |
|---|---:|---:|
| safha | 3/3 | 0/3 |
| safha-reader | 3/3 | 0/3 |
| pdfCropMargins | 0/3 | 0/3 |
| briss | 0/3 | 0/3 |
| k2pdfopt | n/a (pages reflowed) | n/a (pages reflowed) |
| unpaper | 0/3 | 2/3 |
| ocrmypdf | 3/3 | 3/3 |
