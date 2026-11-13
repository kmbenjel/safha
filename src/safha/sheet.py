"""Review sheets: what the method did, page by page, drawn on the scan and shown as the reader will see it.

``before``: the page as scanned, the box in red (drawn back onto the scan, so a turned page shows its box turned), stains
left out in orange, scanner edge noise in purple, a whole page's shown part dashed blue. ``after``: what the reader shows.
A contact sheet puts before | after pairs side by side; an HTML page lists every page with its flags.
"""

from __future__ import annotations

import html
import json
import os
from typing import Any

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from .geometry import inside
from .pdf import back_to_scan, open_book

WHY = {"turned": "turned level", "found_in_check": "tilt found by the second look", "frame_turn": "squared by its frame",
       "frame_shear": "sheared print levelled", "two_angles": "lines at two angles: left as scanned",
       "unsure_tilt": "tilt not confirmed: left as scanned", "untreated_tilt": "tilt seen, no safe turn",
       "whole": "content wider than the box: shown whole", "own_centre": "odd page centred on its own content",
       "dodged": "box slid away from a stain", "check_moved": "box moved by the second look", "curved": "curved page",
       "mid": "a page from the middle", "stain": "stains left out", "cover": "cover", "spread": "split from a spread"}


def _font(size: int) -> ImageFont.ImageFont:
    for f in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _pix(page: pymupdf.Page, z: float, clip: Any = None) -> Image.Image:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def pick_pages(rec: dict, k: int = 8) -> list[tuple[int, str]]:
    """the pages worth looking at: turned ones (most tilted first), frame turns, pages left whole, pages with stains, two
    facing pages from the middle, a cover"""
    P = rec["pages"]
    out: list[tuple[int, str]] = []
    text = [i for i, p in enumerate(P) if p["kind"] == "text"]
    if text:
        mid = text[len(text) // 2]
        out += [(mid, "mid")]
        if mid + 1 < len(P) and P[mid + 1]["kind"] == "text":
            out.append((mid + 1, "mid"))
    for f in ("frame_shear", "frame_turn", "two_angles", "whole", "found_in_check", "unsure_tilt"):
        out += [(i, f) for i, p in enumerate(P) if f in (p.get("flags") or [])][:1]
    sk = sorted((i for i, p in enumerate(P) if p.get("skew")), key=lambda i: -abs(P[i]["skew"]))
    out += [(i, "turned") for i in sk[:2]]
    bl = sorted((i for i, p in enumerate(P) if p.get("blots") and p.get("crop")), key=lambda i: -len(P[i]["blots"]))
    out += [(i, "stain") for i in bl[:1]]
    out += [(i, "cover") for i, p in enumerate(P) if p["kind"] == "cover"][:1]
    seen: set[int] = set()
    res = []
    for i, why in out:
        if i not in seen:
            seen.add(i)
            res.append((i, why))
    return sorted(res[:k])


class Pair:
    """before | after images of a book's pages: the recipe applied once to a temporary copy, so the "after" image is
    exactly what a reader shows"""

    def __init__(self, src: str, rec: dict):
        import tempfile

        from .apply import apply_recipe

        self.src, self.rec = src, rec
        self.tmpdir = tempfile.TemporaryDirectory(prefix="safha-sheet-")
        r2 = dict(rec)
        r2.pop("drop", None)
        self.out = os.path.join(self.tmpdir.name, "after.pdf")
        if rec.get("mode") in ("crop", "level") or rec.get("split"):
            apply_recipe(src, r2, self.out, check_source=False)
            self.after = pymupdf.open(self.out)
        else:
            self.after = open_book(src, rec)
        self.doc = open_book(src, rec)

    def images(self, i: int, px: int = 480) -> tuple[Image.Image, Image.Image]:
        p = self.rec["pages"][i]
        tmp = pymupdf.open()
        tmp.insert_pdf(self.doc, from_page=i, to_page=i)
        tp = tmp[0]
        z0 = px / tp.rect.width
        bk = back_to_scan(tp, p)
        sh = tp.new_shape()

        def poly(r: list) -> list:
            return [bk(r[0], r[1]), bk(r[2], r[1]), bk(r[2], r[3]), bk(r[0], r[3]), bk(r[0], r[1])]

        lw = max(1.5, 2.2 / z0)
        if p.get("crop"):
            sh.draw_polyline(poly(p["crop"]))
            sh.finish(color=(0.85, 0, 0), width=lw)
        if p.get("show") and (not p.get("crop") or any(abs(a - b) > 1 for a, b in zip(p["show"], p["crop"]))):
            sh.draw_polyline(poly(p["show"]))
            sh.finish(color=(0, 0.35, 1), width=lw * 0.7, dashes="[6 4] 0")
        for b in p.get("blots") or []:
            sh.draw_polyline(poly([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]))
            sh.finish(color=(1, 0.55, 0), width=lw)
        for b in p.get("edge") or []:
            if p.get("crop") and not inside(b, p["crop"], 0):
                sh.draw_polyline(poly([b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2]))
                sh.finish(color=(0.6, 0, 0.8), width=lw * 0.6)
        sh.commit()
        before = _pix(tp, z0)
        tmp.close()
        ap = self.after[i]
        after = _pix(ap, px / ap.rect.width)
        return before, after

    def close(self) -> None:
        self.after.close()
        self.doc.close()
        self.tmpdir.cleanup()


def page_images(src: str, rec: dict, i: int, px: int = 480) -> tuple[Image.Image, Image.Image]:
    """(before, after) images of page i of the (split) book"""
    pr = Pair(src, rec)
    try:
        return pr.images(i, px)
    finally:
        pr.close()


def contact_sheet(src: str, rec: dict, out: str, pages: list[tuple[int, str]] | None = None, px: int = 360,
                  cols: int = 2) -> str:
    """a PNG/JPEG/WebP of before | after pairs with a caption per page"""
    pages = pages or pick_pages(rec)
    if not pages:
        raise ValueError("no page to show")
    font, small = _font(15), _font(12)
    tiles = []
    pr = Pair(src, rec)
    for i, why in pages:
        b, a = pr.images(i, px)
        h = max(b.height, a.height)
        tile = Image.new("RGB", (2 * px + 30, h + 46), "white")
        tile.paste(b, (8, 38))
        tile.paste(a, (px + 22, 38 + (h - a.height) // 2))
        d = ImageDraw.Draw(tile)
        d.line([(px + 15, 38), (px + 15, 38 + h)], fill=(120, 120, 120), width=1)
        p = rec["pages"][i]
        turn = f"  turn {p['skew']:+.2f} deg" if p.get("skew") else ""
        shear = f"  shear {p['shear']:+.2f} deg" if p.get("shear") else ""
        d.text((8, 6), f"p. {p['n']}  {WHY.get(why, why)}{turn}{shear}", fill=(20, 20, 20), font=font)
        d.text((8, 23), "before (box in red)", fill=(140, 0, 0), font=small)
        d.text((px + 22, 23), "after", fill=(0, 90, 0), font=small)
        tiles.append(tile)
    pr.close()
    tw = max(t.width for t in tiles)
    rows = [tiles[k:k + cols] for k in range(0, len(tiles), cols)]
    H = sum(max(t.height for t in r) for r in rows)
    sheet = Image.new("RGB", (tw * min(cols, len(tiles)), H), (235, 235, 235))
    y = 0
    for r in rows:
        for k, t in enumerate(r):
            sheet.paste(t, (k * tw, y))
        y += max(t.height for t in r)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out, quality=82) if out.lower().endswith((".jpg", ".jpeg", ".webp")) else sheet.save(out, optimize=True)
    return out


def html_review(src: str, rec: dict, outdir: str, px: int = 300, every: bool = False) -> str:
    """a self-contained review folder: index.html (lazy-loaded thumbnails, before | after, flags) + JPEGs"""
    os.makedirs(outdir, exist_ok=True)
    P = rec["pages"]
    idx = range(len(P)) if every else [i for i, _ in pick_pages(rec, k=40)]
    rows = []
    pr = Pair(src, rec)
    for i in idx:
        b, a = pr.images(i, px)
        fb, fa = f"p{i + 1:04d}-before.jpg", f"p{i + 1:04d}-after.jpg"
        b.save(os.path.join(outdir, fb), quality=72)
        a.save(os.path.join(outdir, fa), quality=72)
        p = P[i]
        fl = ", ".join(WHY.get(f, f) for f in p.get("flags") or [])
        turn = f"turn {p['skew']:+.3f}&deg;" if p.get("skew") else ""
        rows.append(f'<figure><figcaption><b>p. {p["n"]}</b> {html.escape(p["kind"])} {turn} {html.escape(fl)}</figcaption>'
                    f'<img loading="lazy" src="{fb}" alt="before"><span class="rule"></span>'
                    f'<img loading="lazy" src="{fa}" alt="after"></figure>')
    pr.close()
    head = {k: rec.get(k) for k in ("mode", "why", "reasons", "size", "gain", "framed", "clean_margins")}
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>safha review: {html.escape(rec['source']['file'])}</title><style>
body{{font:14px system-ui,sans-serif;margin:16px;background:#f4f4f2;color:#222}}
figure{{display:inline-block;margin:8px;padding:8px;background:#fff;border:1px solid #ddd;vertical-align:top}}
figure img{{width:{px}px;vertical-align:middle}} .rule{{display:inline-block;width:1px;height:{px}px;background:#888;margin:0 6px}}
pre{{background:#fff;padding:8px;border:1px solid #ddd;white-space:pre-wrap}}
@media (prefers-color-scheme: dark){{body{{background:#1b1b1b;color:#ddd}}figure,pre{{background:#262626;border-color:#444}}}}
</style></head><body><h1>{html.escape(rec['source']['file'])}</h1>
<pre>{html.escape(json.dumps(head, ensure_ascii=False, indent=1))}</pre>
{''.join(rows)}</body></html>"""
    out = os.path.join(outdir, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return out
