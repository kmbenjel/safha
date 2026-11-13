"""Head-to-head: safha and the tools it is compared with, on the same public-domain pages.

For each input book and each tool: wall time, output size, whether the original image streams survive byte for byte
(and the image codecs before and after), pixel fidelity (PSNR of level text pages against the input, after aligning),
consistency of the result across pages (distinct page sizes, the text block's place from page to page), and, on a
synthetic book with a known truth, turns: tilted pages levelled and warped pages (lines at two angles) wrongly turned.

Usage (see bench/compare.sh): python bench/compare.py WORKDIR BOOK.pdf [BOOK.pdf ...]
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
import pymupdf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
import synth
from safha.measure import marks
from safha.pdf import gray, image_filters
from safha.tilt import line_tracks, skew_of

TOOLS_DIR = os.environ.get("TOOLS", os.path.expanduser("~/safha-tools"))
SAFHA = os.environ.get("SAFHA", os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "safha"))


def native_dpi(path: str) -> int:
    d = pymupdf.open(path)
    vals = []
    for p in list(d)[: min(10, d.page_count)]:
        for x in p.get_image_info():
            w = x["bbox"][2] - x["bbox"][0]
            if w > 0.5 * p.rect.width:
                vals.append(x["width"] / w * 72)
    return int(min(400, max(150, np.median(vals) if vals else 300)))


def sh(cmd: str, timeout: int = 7200) -> None:
    subprocess.run(["bash", "-c", cmd], check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def run_tool(tool: str, src: str, dst: str, work: str) -> None:
    dpi = native_dpi(src)
    if tool in ("safha", "safha-reader"):
        prof = "reader" if tool == "safha-reader" else "warraq"
        sh(f'"{SAFHA}" crop "{src}" -o "{dst}" -q --jobs 4 --profile {prof}')
        if not os.path.exists(dst):  # nothing to do: the file left as it is
            shutil.copyfile(src, dst)
    elif tool == "k2pdfopt":
        sh(f'k2pdfopt "{src}" -ui- -x -as -o "{dst}"')  # its default: reflowed for an e-reader, auto-straightened
    elif tool == "pdfCropMargins":
        sh(f'"{TOOLS_DIR}/pcm/bin/pdf-crop-margins" -u -s -p 10 -o "{dst}" "{src}"')
    elif tool == "briss":
        jar = subprocess.run(["bash", "-c", f'find "{TOOLS_DIR}/briss" -name "*all.jar" | head -1'], capture_output=True,
                             text=True).stdout.strip()
        sh(f'java -Djava.awt.headless=true -jar "{jar}" -s "{src}" -d "{dst}"')
    elif tool == "unpaper":
        t = tempfile.mkdtemp(dir=work)
        sh(f'pdftoppm -r {dpi} -gray "{src}" "{t}/p" && cd "{t}" && for f in p-*.pgm; do '
           f'unpaper -q --overwrite "$f" "u${{f#p}}"; pnmtopng "u${{f#p}}" > "u${{f#p}}.png"; done && '
           f'img2pdf --pagesize A5 -o "{dst}" $(ls u-*.png | sort -V)')
        shutil.rmtree(t, ignore_errors=True)
    elif tool == "ocrmypdf":
        sh(f'ocrmypdf -q --force-ocr --deskew --tesseract-timeout 0 --output-type pdf "{src}" "{dst}"')
    else:
        raise ValueError(tool)


def stream_md5s(doc: pymupdf.Document) -> set[str]:
    out = set()
    for p in doc:
        for x in p.get_images(full=True):
            out.add(hashlib.md5(doc.xref_stream_raw(x[0]) or b"").hexdigest())
    return out


def kept_share(src: pymupdf.Document, dst: pymupdf.Document) -> float:
    a, b = stream_md5s(src), stream_md5s(dst)
    return len(a & b) / max(1, len(b))


def text_place(doc: pymupdf.Document) -> dict:
    """per output page: the text block's horizontal centre (share of the page width) and its share of the width"""
    cs, ws, sizes = [], [], set()
    for p in doc:
        sizes.add((round(p.rect.width), round(p.rect.height)))
        a, z = gray(p, 500)
        mk = marks(a, z, p.rect.width)
        t = mk.get("text")
        if t is None or mk["dark"] > 0.35:
            continue
        cs.append(((t[0] + t[2]) / 2 - p.rect.width / 2) / p.rect.width)
        ws.append((t[2] - t[0]) / p.rect.width)
    if not cs:
        return {"sizes": len(sizes)}
    q75, q25 = np.percentile(cs, [75, 25])
    return {"sizes": len(sizes), "offcentre_median": round(float(np.median(np.abs(cs))), 4),
            "sway_iqr": round(float(q75 - q25), 4), "text_width_share": round(float(np.median(ws)), 3)}


def _main_image(doc: pymupdf.Document, page: pymupdf.Page) -> tuple[str, np.ndarray] | None:
    """the page's largest image: (raw stream md5, decoded gray pixels)"""
    imgs = page.get_images(full=True)
    if not imgs:
        return None
    x = max(imgs, key=lambda t: t[2] * t[3])[0]
    raw = doc.xref_stream_raw(x) or b""
    pix = pymupdf.Pixmap(doc, x)
    if pix.n - pix.alpha != 1:
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width].astype(np.float32)
    return hashlib.md5(raw).hexdigest(), a


def psnr_image(A: np.ndarray, B: np.ndarray) -> float | None:
    """PSNR (dB) of B against A at the same pixel scale: the central 60 % of A found in B by phase correlation"""
    if abs(B.shape[0] / A.shape[0] - 1) > 0.03 or abs(B.shape[1] / A.shape[1] - 1) > 0.03:
        return None  # rescaled: pixels cannot be compared one to one
    h, w = A.shape
    C = A[int(0.2 * h):int(0.8 * h), int(0.2 * w):int(0.8 * w)]
    F = np.fft.rfft2(B - B.mean())
    G = np.fft.rfft2(C - C.mean(), s=B.shape)
    cc = np.fft.irfft2(F * np.conj(G), s=B.shape)
    dy, dx = np.unravel_index(int(np.argmax(cc)), cc.shape)
    ch, cw = C.shape
    if dy + ch > B.shape[0] or dx + cw > B.shape[1]:
        return None
    Bm = B[dy:dy + ch, dx:dx + cw]
    mse = float(((C - Bm) ** 2).mean())
    return 99.0 if mse == 0 else round(10 * np.log10(255 ** 2 / mse), 2)


def fidelity(src: str, dst: str, pages: list[int]) -> float | None:
    """median PSNR of the output's page images against the input's, on level text pages (99 = identical)"""
    a, b = pymupdf.open(src), pymupdf.open(dst)
    if a.page_count != b.page_count:
        return None
    vals = []
    for i in pages:
        ia, ib = _main_image(a, a[i]), _main_image(b, b[i])
        if ia is None or ib is None:
            continue
        if ia[0] == ib[0]:
            vals.append(99.0)
            continue
        v = psnr_image(ia[1], ib[1])
        if v is not None:
            vals.append(v)
    return round(float(np.median(vals)), 2) if vals else None


def level_pages(path: str, k: int = 3) -> list[int]:
    """text pages that read level (no tool should need to turn them): where pixels can be compared"""
    d = pymupdf.open(path)
    out = []
    for i in range(min(d.page_count, 30)):
        a, z = gray(d[i], 800)
        mk = marks(a, z, d[i].rect.width)
        if mk.get("text") is None or mk["dark"] > 0.35 or d[i].rect.width > 1.15 * d[i].rect.height:
            continue
        if abs(skew_of(mk["xy"], raw=True)[0]) <= 0.05:
            out.append(i)
        if len(out) >= k:
            break
    return out


def truth_book(path: str) -> list[str]:
    """six synthetic pages: three tilted 1 deg (should be levelled), three warped -- the upper lines level, the lower ones
    at 1.5 deg (no single turn fixes them: a turn makes the level lines lean)"""
    kinds = ["tilt", "warp", "tilt", "warp", "tilt", "warp"]
    ims = [synth.page(seed=10 + k, tilt=1.0 if t == "tilt" else 0.0, warp=1.5 if t == "warp" else 0.0)
           for k, t in enumerate(kinds)]
    synth.write(path, ims)
    return kinds


def turns(dst: str, kinds: list[str]) -> dict:
    """tilted pages levelled; warped pages whose level upper lines now lean (a wrong turn)"""
    d = pymupdf.open(dst)
    if d.page_count != len(kinds):
        return {"tilted_levelled": "n/a (pages reflowed)", "warped_wrongly_turned": "n/a (pages reflowed)"}
    levelled = wrong = 0
    for i, kind in enumerate(kinds):
        if i >= d.page_count:
            break
        a, z = gray(d[i], 1000)
        mk = marks(a, z, d[i].rect.width)
        if mk.get("text") is None:
            continue
        T = [t for t in line_tracks(a, mk["paper"], mk["text"], z) if t[3] <= 1.0 and t[4] >= 6 and t[2] >= 0.3]
        if not T:
            continue
        mid = (mk["text"][1] + mk["text"][3]) / 2
        if kind == "tilt":
            levelled += abs(float(np.median([t[1] for t in T]))) <= 0.2
        else:
            upper = [t[1] for t in T if t[0] < mid]
            wrong += sum(1 for v in upper if abs(v) > 0.35) >= 2
    return {"tilted_levelled": f"{levelled}/{kinds.count('tilt')}", "warped_wrongly_turned": f"{wrong}/{kinds.count('warp')}"}


TOOLS = ["safha", "safha-reader", "pdfCropMargins", "briss", "k2pdfopt", "unpaper", "ocrmypdf"]


def main() -> None:
    work, books = sys.argv[1], sys.argv[2:]
    os.makedirs(work, exist_ok=True)
    only = os.environ.get("ONLY_TOOLS")
    tools = only.split(",") if only else TOOLS
    truth = os.path.join(work, "truth-warped-tilted.pdf")
    kinds = truth_book(truth) if not os.environ.get("NO_TRUTH") else []
    rows = []
    for src in books + ([truth] if kinds else []):
        name = os.path.basename(src)
        sd = pymupdf.open(src)
        lv = level_pages(src) if src != truth else []
        base = {"book": name, "pages": sd.page_count, "bytes_in": os.path.getsize(src), "filters_in": image_filters(sd),
                "place_in": text_place(sd) if src != truth else None}
        print(json.dumps(base), flush=True)
        for tool in tools:
            dst = os.path.join(work, f"{os.path.splitext(name)[0]}.{tool}.pdf")
            row = {"book": name, "tool": tool}
            t0 = time.time()
            try:
                run_tool(tool, src, dst, work)
                row["seconds"] = round(time.time() - t0, 1)
                dd = pymupdf.open(dst)
                row.update(pages_out=dd.page_count, bytes_out=os.path.getsize(dst), filters_out=image_filters(dd),
                           kept_streams=round(kept_share(sd, dd), 3))
                if src == truth:
                    row.update(turns(dst, kinds))
                else:
                    row["place_out"] = text_place(dd)
                    row["psnr_level_pages"] = fidelity(src, dst, lv)
            except subprocess.CalledProcessError as e:
                row["error"] = (e.stderr or b"").decode(errors="replace")[-300:]
            except Exception as e:  # report and go on
                row["error"] = f"{type(e).__name__}: {e}"
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        rows.append({"book": name, "tool": "input", **base})
    with open(os.path.join(work, os.environ.get("OUT", "compare.json")), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
