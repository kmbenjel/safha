"""Synthetic scanned pages with a known truth: tilt, warp, frame, shear, spreads, blank pages, stains."""

from __future__ import annotations

import io
import math
import random

import pymupdf
from PIL import Image, ImageDraw, ImageFont

_TEXT = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna "
    "aliqua enim ad minim veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea commodo consequat duis "
    "aute irure in reprehenderit voluptate velit esse cillum fugiat nulla pariatur"
)
WORDS = _TEXT.split()


def font(size: int) -> ImageFont.ImageFont:
    for f in ("DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def text_block(w: int, h: int, seed: int, size: int = 22, lines: int | None = None, folio: int | None = None) -> Image.Image:
    """an upright block of justified-looking lines on white, w x h px"""
    rnd = random.Random(seed)
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    f = font(size)
    pitch = int(size * 1.55)
    n = lines or (h - 2 * pitch) // pitch
    y = pitch if folio is None else int(2.2 * pitch)
    if folio is not None:
        d.text((w // 2 - size, 0), str(folio), font=f, fill=0)
    for k in range(n):
        x = 0
        last = k == n - 1
        while True:
            wd = rnd.choice(WORDS)
            tw = d.textlength(wd, font=f)
            if x + tw > (w * 0.55 if last else w):
                break
            d.text((x, y), wd, font=f, fill=0)
            x += tw + d.textlength(" ", font=f)
        y += pitch
    return im


def page(w: int = 900, h: int = 1300, tilt: float = 0.0, seed: int = 0, margin: tuple = (150, 160, 150, 170),
         warp: float = 0.0, frame: bool = False, shear: float = 0.0, stain: bool = False, folio: int | None = None,
         blank: bool = False, size: int = 22) -> Image.Image:
    """one scanned page (L mode): a text block inside margins (left, top, right, bottom), turned by ``tilt`` degrees
    (counter-clockwise positive); ``warp``: the lower half's lines turned by that many degrees more (a warped leaf);
    ``frame``: a printed rectangle round the text; ``shear``: rows tilted by that angle, columns upright"""
    im = Image.new("L", (w, h), 250)
    if blank:
        return im
    l, t, r, b = margin
    bw, bh = w - l - r, h - t - b
    blk = text_block(bw, bh, seed, size=size, folio=folio)
    if warp:
        lower = blk.crop((0, bh // 2, bw, bh))
        lower = lower.rotate(warp, resample=Image.BICUBIC, fillcolor=255, center=(0, 0))
        blk.paste(lower, (0, bh // 2))
    im.paste(blk, (l, t))
    d = ImageDraw.Draw(im)
    if frame:
        d.rectangle([l - 25, t - 25, w - r + 25, h - b + 25], outline=0, width=4)
    if stain:
        rnd = random.Random(seed + 7)
        cx, cy = w - r // 2 + 10, t + bh // 3
        for _ in range(60):
            x, y = cx + rnd.gauss(0, 9), cy + rnd.gauss(0, 14)
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=60)
    if shear:
        k = math.tan(math.radians(shear))
        # y' = y - k (x - cx): the right end goes up for a positive angle (rows tilted, columns upright)
        im = im.transform(im.size, Image.AFFINE, (1, 0, 0, k, 1, -k * w / 2), resample=Image.BICUBIC, fillcolor=250)
    if tilt:
        im = im.rotate(tilt, resample=Image.BICUBIC, fillcolor=250)
    return im


def spread(seed: int = 0, w: int = 900, h: int = 1300) -> Image.Image:
    """two book pages on one sheet, with a gutter between them; the right page carries a mark (a 3 x 3 dot grid at
    its top) so a test can tell the halves apart"""
    left, right = page(w, h, seed=seed), page(w, h, seed=seed + 1)
    d = ImageDraw.Draw(right)
    for i in range(3):
        for j in range(3):
            d.rectangle([w // 2 - 40 + 30 * i, 60 + 30 * j, w // 2 - 25 + 30 * i, 75 + 30 * j], fill=0)
    im = Image.new("L", (2 * w, h), 250)
    im.paste(left, (0, 0))
    im.paste(right, (w, 0))
    return im


def book(images: list[Image.Image], dpi: float = 150, fmt: str = "PNG") -> bytes:
    """a PDF with one image per page"""
    doc = pymupdf.open()
    for im in images:
        buf = io.BytesIO()
        im.save(buf, fmt, **({"quality": 80} if fmt == "JPEG" else {}))
        p = doc.new_page(width=im.width * 72 / dpi, height=im.height * 72 / dpi)
        p.insert_image(p.rect, stream=buf.getvalue())
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out


def write(path, images: list[Image.Image], **kw) -> str:
    with open(path, "wb") as f:
        f.write(book(images, **kw))
    return str(path)
