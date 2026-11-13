"""Make the README and docs media by running safha on public-domain pages (run where the bench ran: it plans books).

  python scripts/make_media.py COMPARE_WORKDIR OUTDIR

Writes: hero.webp (a microfilm spread before | the two pages safha made), deskew.gif (a tilted page: the scan, the box,
the result), compare.webp (one page by every tool, with a magnified word), card.webp (1200 x 750 for the docs site),
sheet-*.webp (contact sheets of the test fixtures) and terminal.svg (a `safha crop` run).
"""

from __future__ import annotations

import html
import io
import os
import subprocess
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFont

import safha
from safha.sheet import Pair, contact_sheet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG, INK, RED, MUTED = (250, 250, 247), (25, 25, 25), (200, 30, 30), (110, 110, 110)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for f in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def render(page: pymupdf.Page, height: int) -> Image.Image:
    z = height / page.rect.height
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def save_webp(im: Image.Image, path: str, limit_kb: int = 300) -> None:
    for q in (82, 74, 66, 58, 50, 42):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() <= limit_kb * 1024 or q == 42:
            with open(path, "wb") as f:
                f.write(buf.getvalue())
            return


def label(d: ImageDraw.ImageDraw, xy: tuple, text: str, size: int = 22, fill=INK, bold: bool = True) -> None:
    d.text(xy, text, font=font(size, bold), fill=fill)


def hero(spreads: str, out: str, H: int = 520) -> Image.Image:
    """a microfilm frame (two manuscript pages on a black field) | the two pages safha made from it"""
    prof = safha.load_profile(None, {"direction": "rtl", "min_text_pages": 1})
    rec = safha.plan(spreads, prof, jobs=4)
    tmp = out + ".tmp.pdf"
    safha.apply_recipe(spreads, rec, tmp)
    src, dst = pymupdf.open(spreads), pymupdf.open(tmp)
    k = min(2, src.page_count - 1)
    before = render(src[k], H)
    right, left = render(dst[2 * k], H), render(dst[2 * k + 1], H)  # RTL: the right-hand page comes first
    gap = 18
    W = before.width + 90 + left.width + right.width + gap + 40
    im = Image.new("RGB", (W, H + 84), BG)
    im.paste(before, (20, 50))
    x = 20 + before.width + 70
    im.paste(left, (x, 50))
    im.paste(right, (x + left.width + gap, 50))
    d = ImageDraw.Draw(im)
    label(d, (20, 12), "the scan: one microfilm frame, two pages", 20)
    label(d, (x, 12), "safha: two pages, one size, centred", 20)
    ax = 20 + before.width + 18
    d.polygon([(ax, 50 + H // 2 - 14), (ax + 34, 50 + H // 2), (ax, 50 + H // 2 + 14)], fill=RED)
    label(d, (20, H + 58), "lossless: the scan's image stream is untouched, only the page boxes and matrices change",
          15, MUTED, False)
    os.remove(tmp)
    save_webp(im, out, 260)
    return im


def deskew_gif(book: str, out: str, H: int = 560) -> None:
    """the most tilted page safha turned: the scan with its box (red), then what a reader shows"""
    prof = safha.load_profile(None, {"min_text_pages": 1})
    rec = safha.plan(book, prof, jobs=4)
    turned = sorted((p for p in rec["pages"] if p.get("skew") and p["kind"] == "text" and (p.get("after") or [9])[0] <= 0.15),
                    key=lambda p: -abs(p["skew"]))
    if not turned:
        print("no turned page in", book)
        return
    i = turned[0]["n"] - 1
    pr = Pair(book, rec)
    before, after = pr.images(i, px=int(H * 0.68))
    pr.close()
    W = max(before.width, after.width) + 40

    def frame(img: Image.Image, title: str) -> Image.Image:
        f = Image.new("RGB", (W, H + 60), BG)
        f.paste(img, ((W - img.width) // 2, 48))
        label(ImageDraw.Draw(f), (16, 12), title, 18)
        return f

    a = frame(before, f"scan: tilted {abs(turned[0]['skew']):.2f} deg, the box in red")
    b = frame(after, "safha: turned level, cropped, centred")
    frames = [a] * 6 + [Image.blend(a, b, t / 5) for t in range(1, 5)] + [b] * 8 + [Image.blend(b, a, t / 5) for t in range(1, 5)]
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=96) for f in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=180, loop=0, optimize=True)


def compare_image(work: str, book: str, out: str, page: int = 6, H: int = 360) -> None:
    """one page as each tool leaves it, with a magnified word: the scan's pixels kept or redrawn"""
    tools = ["input", "safha", "pdfCropMargins", "briss", "k2pdfopt", "unpaper", "ocrmypdf"]
    tiles = []
    for t in tools:
        f = os.path.join(work, "in", book + ".pdf") if t == "input" else os.path.join(work, f"{book}.{t}.pdf")
        if not os.path.exists(f):
            continue
        d = pymupdf.open(f)
        k = min(page, d.page_count - 1)
        im = render(d[k], H)
        z = 4 * H / d[k].rect.height
        r = d[k].rect
        clip = pymupdf.Rect(r.x0 + 0.45 * r.width, r.y0 + 0.30 * r.height, r.x0 + 0.60 * r.width, r.y0 + 0.36 * r.height)
        pix = d[k].get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip, alpha=False)
        zoom = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        zoom = zoom.resize((im.width, max(1, int(zoom.height * im.width / max(1, zoom.width)))), Image.NEAREST)
        tile = Image.new("RGB", (im.width + 16, H + zoom.height + 56), BG)
        tile.paste(im, (8, 34))
        tile.paste(zoom, (8, 40 + H))
        label(ImageDraw.Draw(tile), (8, 6), "scan (input)" if t == "input" else t, 17)
        tiles.append(tile)
    if not tiles:
        return
    W = sum(t.width for t in tiles) + 8
    im = Image.new("RGB", (W, max(t.height for t in tiles) + 30), BG)
    x = 4
    for t in tiles:
        im.paste(t, (x, 0))
        x += t.width
    label(ImageDraw.Draw(im), (10, im.height - 24), "bottom row: one word magnified 4x, nearest-neighbour (no smoothing)",
          14, MUTED, False)
    save_webp(im, out, 400)


def card(hero_im: Image.Image, out: str) -> None:
    W, H = 1200, 750
    c = Image.new("RGB", (W, H), BG)
    s = min((W - 40) / hero_im.width, (H - 150) / hero_im.height)
    h2 = hero_im.resize((int(hero_im.width * s), int(hero_im.height * s)), Image.LANCZOS)
    c.paste(h2, ((W - h2.width) // 2, 130))
    d = ImageDraw.Draw(c)
    label(d, (40, 30), "safha", 54)
    label(d, (40, 92), "lossless crop, deskew and split for scanned books", 24, MUTED, False)
    save_webp(c, out, 195)


def terminal_svg(cmd: str, text: str, out: str) -> None:
    lines = [f"$ {cmd}"] + text.rstrip().splitlines()
    w, lh = 1000, 21
    h = 46 + lh * len(lines)
    body = []
    for k, ln in enumerate(lines):
        col = "#7ee787" if k == 0 else ("#e6edf3" if not ln.startswith("  ") else "#c9d1d9")
        body.append(f'<text x="18" y="{40 + k * lh}" fill="{col}">{html.escape(ln)}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<rect width="{w}" height="{h}" rx="10" fill="#0d1117"/>'
           '<circle cx="20" cy="16" r="6" fill="#ff5f56"/><circle cx="40" cy="16" r="6" fill="#ffbd2e"/>'
           '<circle cx="60" cy="16" r="6" fill="#27c93f"/>'
           f'<g font-family="DejaVu Sans Mono,Menlo,Consolas,monospace" font-size="14">{"".join(body)}</g></svg>')
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)


def main() -> None:
    work, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    fx = os.path.join(ROOT, "tests", "fixtures")
    h = hero(os.path.join(fx, "spreads.pdf"), os.path.join(outdir, "hero.webp"))
    card(h, os.path.join(outdir, "card.webp"))
    deskew_gif(os.path.join(work, "in", "almuqaddimah00ibnk.pdf"), os.path.join(outdir, "deskew.gif"))
    compare_image(work, "chronologyofanci00biru", os.path.join(outdir, "compare.webp"))
    for name, opts in (("latin-jbig2", {}), ("arabic-leiden", {}), ("urdu-ccitt", {})):
        src = os.path.join(fx, name + ".pdf")
        rec = safha.plan(src, safha.load_profile(None, {"min_text_pages": 1, **opts}))
        tmp = os.path.join(outdir, f"sheet-{name}.png")
        contact_sheet(src, rec, tmp, px=300)
        save_webp(Image.open(tmp).convert("RGB"), tmp[:-4] + ".webp", 220)
        os.remove(tmp)
    sample = os.path.join(ROOT, "src", "safha", "data", "sample-latin.pdf")
    run = subprocess.run([sys.executable, "-m", "safha", "crop", sample, "-o", "/tmp/sample-latin.safha.pdf", "-q"],
                         capture_output=True, text=True)
    txt = subprocess.run([sys.executable, "-m", "safha", "crop", sample, "-o", "/tmp/sample-latin.safha.pdf",
                          "--set", "min_text_pages=1"], capture_output=True, text=True).stdout
    terminal_svg("safha crop sample-latin.pdf", txt.replace("/tmp/", ""), os.path.join(outdir, "terminal.svg"))
    del run
    for f in sorted(os.listdir(outdir)):
        print(f, os.path.getsize(os.path.join(outdir, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
