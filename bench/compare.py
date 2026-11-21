"""Head-to-head: safha and the tools it is compared with, on the same public-domain pages.

For each input book and each tool: wall time, output size, whether the original image streams survive byte for byte
(and the image codecs before and after), pixel fidelity (PSNR of level text pages against the input, after aligning),
consistency of the result across pages (distinct page sizes, the text block's place from page to page), and turns:

* on real pages that carry their own truth -- a two-column dictionary with a printed rule between the columns: the
  rule's lean after each tool;
* on a book drawn with a known truth (``truth_book``): level pages left level, tilted pages levelled, and warped pages
  (lines at two angles) wrongly turned.

Who judges. The turns are judged by ``bench/rules.py``, which owes nothing to safha's own measures (a rule followed and
fitted; the projection profile of the lines). Sizes, streams and codecs are read from the files. The place of the text
on the page (off-centre, sway, width) is read on every tool's output alike with safha's own text-block measure
(``safha.measure.marks``): it describes the outputs, it is no truth, and the report says so.

Every tool runs the way a careful user would run it for this job (see ``run_tool``): the options that keep its output
small and its pages whole. Where a tool has a lossless and a smaller lossy setting, both are run and both are published.
The versions of everything that ran are written with the results.

Usage (see bench/compare.sh): python bench/compare.py WORKDIR BOOK.pdf [BOOK.pdf ...]
Environment: TOOLS (where bench/install_tools.sh put the tools), SAFHA (the safha to run), ONLY_TOOLS (a,b,c),
NO_TRUTH=1 (books only), OUT (the JSON's name), KEEP=1 (keep every tool's output PDF; else only the truth book's and
those of the books named in KEEP_BOOKS, which the media script draws from).
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
sys.path.insert(0, os.path.dirname(__file__))
from rules import column_rule_lean, lines_lean

import synth
from safha.measure import marks
from safha.pdf import gray, image_filters
from safha.tilt import skew_of

TOOLS_DIR = os.environ.get("TOOLS", os.path.expanduser("~/safha-tools"))
SAFHA = os.environ.get("SAFHA", os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "safha"))
JOBS = int(os.environ.get("JOBS", "8"))  # worker processes for the tools that take a number


def versions() -> dict[str, str]:
    """the version each tool reports, and of what it leans on: written with the results"""
    def first(cmd: str, last: bool = False) -> str:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
        lines = [ln.strip() for ln in (r.stdout or r.stderr).splitlines() if ln.strip()]
        line = (lines[-1] if last else lines[0]) if lines else ""
        return "".join(ch for ch in line.replace("\x1b[0m", "").replace("\x1b[36m", "") if ch.isprintable())[:80]

    jar = first(f'find "{TOOLS_DIR}/briss" -name "*all.jar" | head -1')
    out = {
        "safha": first(f'"{SAFHA}" --version'), "PyMuPDF": pymupdf.VersionBind, "MuPDF": pymupdf.mupdf_version,
        "pdfCropMargins": first(f'"{TOOLS_DIR}/pcm/bin/pdf-crop-margins" --version 2>/dev/null', last=True),
        "Briss": os.path.basename(jar),
        "k2pdfopt": first("k2pdfopt -? | head -1"), "unpaper": first("unpaper --version"),
        "OCRmyPDF": first("ocrmypdf --version"), "OCRmyPDF (new)": first(f'"{TOOLS_DIR}/ocrmypdf-new/bin/ocrmypdf" --version'),
        "tesseract": first("tesseract --version | head -1"), "Ghostscript": first("gs --version"),
        "jbig2enc": first("jbig2 --version"), "pngquant": first("pngquant --version"), "poppler": first("pdftoppm -v 2>&1"),
        "img2pdf": first("img2pdf --version"),
    }
    return {k: v for k, v in out.items() if v and "No such file" not in v and "not found" not in v}


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


def page_kind(path: str) -> str:
    """what the scan's pages hold: ``mono`` (1-bit images only), ``gray`` or ``color``"""
    d = pymupdf.open(path)
    bpc, cs = set(), set()
    for p in list(d)[: min(10, d.page_count)]:
        for x in p.get_images(full=True):
            bpc.add(x[4])
            cs.add(str(x[5]))
    if bpc == {1}:
        return "mono"
    return "gray" if cs <= {"DeviceGray", "", "None"} else "color"


def _unpaper(src: str, dst: str, work: str, dpi: int, opts: str = "") -> None:
    """unpaper works on images: the pages are rendered at the scan's own resolution and kind (1-bit, gray or colour),
    cleaned, and wrapped again the way a careful user would: 1-bit pages as CCITT G4 (lossless), the others as JPEG 85,
    at the page's own size"""
    from PIL import Image

    kind = page_kind(src)
    flag, ext = {"mono": ("-mono", "pbm"), "gray": ("-gray", "pgm"), "color": ("", "ppm")}[kind]
    t = tempfile.mkdtemp(dir=work)
    sh(f'pdftoppm -r {dpi} {flag} "{src}" "{t}/p" && cd "{t}" && for f in p-*.{ext}; do '
       f'unpaper -q --overwrite {opts} "$f" "u${{f#p}}"; done')
    outs = []
    for f in sorted((x for x in os.listdir(t) if x.startswith("u-")), key=lambda x: int("".join(c for c in x if c.isdigit()))):
        im = Image.open(os.path.join(t, f))
        if kind == "mono":
            o = os.path.join(t, f + ".tif")
            im.convert("1").save(o, compression="group4", dpi=(dpi, dpi))
        else:
            o = os.path.join(t, f + ".jpg")
            im.convert("L" if kind == "gray" else "RGB").save(o, quality=85, dpi=(dpi, dpi))
        outs.append(o)
    sh("img2pdf -o " + f'"{dst}" ' + " ".join(f'"{o}"' for o in outs))
    shutil.rmtree(t, ignore_errors=True)


def run_tool(tool: str, src: str, dst: str, work: str) -> None:
    dpi = native_dpi(src)
    if tool in ("safha", "safha-reader"):
        prof = "reader" if tool == "safha-reader" else "warraq"
        sh(f'"{SAFHA}" crop "{src}" -o "{dst}" -q --jobs {min(4, JOBS)} --profile {prof}')
        if not os.path.exists(dst):  # nothing to do: the file left as it is
            shutil.copyfile(src, dst)
    elif tool == "k2pdfopt":
        sh(f'k2pdfopt "{src}" -ui- -x -as -o "{dst}"')  # its default: reflowed for an e-reader, auto-straightened
    elif tool == "k2pdfopt-tm":
        sh(f'k2pdfopt "{src}" -ui- -x -mode tm -o "{dst}"')  # trim margins: its lossless mode (native PDF output)
    elif tool == "k2pdfopt-as":
        # one output page per source page at the scan's resolution, auto-straightened: its deskew without the reflow
        sh(f'k2pdfopt "{src}" -ui- -x -mode copy -as -dpi {dpi} -idpi {dpi} -o "{dst}"')
    elif tool == "pdfCropMargins":
        sh(f'"{TOOLS_DIR}/pcm/bin/pdf-crop-margins" -u -s -p 10 -o "{dst}" "{src}"')
    elif tool == "briss":
        jar = subprocess.run(["bash", "-c", f'find "{TOOLS_DIR}/briss" -name "*all.jar" | head -1'], capture_output=True,
                             text=True).stdout.strip()
        sh(f'java -Djava.awt.headless=true -jar "{jar}" -s "{src}" -d "{dst}"')
    elif tool == "unpaper":
        _unpaper(src, dst, work, dpi)
    elif tool.startswith("ocrmypdf"):
        # --force-ocr: the corpus files carry a text layer and --deskew needs the page rasterised; --tesseract-timeout 0
        # skips the recognition itself (only the deskew is measured). "ocrmypdf-pdfa" is the tool's own default (PDF/A
        # output through Ghostscript, which may re-encode images as JPEG); the others write a plain PDF: -O1 is its
        # default optimisation (lossless), -O2/-O3 its lossy settings; jbig2enc and pngquant are installed
        # (bench/install_tools.sh), --jbig2-lossy stays off. "ocrmypdf-new-*": the same two main settings with the
        # current release from PyPI beside the distribution's package
        exe = f'"{TOOLS_DIR}/ocrmypdf-new/bin/ocrmypdf"' if tool.startswith("ocrmypdf-new") else "ocrmypdf"
        opt = {"ocrmypdf-pdfa": "", "ocrmypdf": "--output-type pdf", "ocrmypdf-O2": "--output-type pdf --optimize 2",
               "ocrmypdf-O3": "--output-type pdf --optimize 3", "ocrmypdf-new-pdfa": "",
               "ocrmypdf-new": "--output-type pdf"}[tool]
        sh(f'{exe} -q --jobs {JOBS} --force-ocr --deskew --tesseract-timeout 0 {opt} "{src}" "{dst}"')
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


TRUTH_TILTS = (0.5, -0.5, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0)
TRUTH_WARPS = (1.0, -1.0, 1.5, -1.5, 2.0, -2.0, 2.5, -2.5)


def truth_book(path: str) -> list[tuple[str, float]]:
    """A book with a known truth, drawn as a 300 dpi scan: 24 pages in turn level, tilted and warped.

    * 8 level pages: a tool has nothing to turn;
    * 8 tilted pages, by 0.5 to 3 degrees either way: a tool should level them;
    * 8 warped pages: the upper half's lines level, the lower half's turned by 1 to 2.5 degrees either way. No
      single turn levels such a page: a turn by its average makes the level upper lines lean.
    -> [(kind, angle)] page by page"""
    kinds: list[tuple[str, float]] = []
    for k in range(8):
        kinds += [("level", 0.0), ("tilt", TRUTH_TILTS[k]), ("warp", TRUTH_WARPS[k])]
    ims = [synth.page(w=1800, h=2600, size=44, margin=(300, 320, 300, 340), seed=10 + k, tilt=v if t == "tilt" else 0.0,
                      warp=v if t == "warp" else 0.0) for k, (t, v) in enumerate(kinds)]
    synth.write(path, ims, dpi=300)
    return kinds


def page_image(page: pymupdf.Page, px: int = 1400) -> np.ndarray:
    z = px / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]


def turns(dst: str, kinds: list[tuple[str, float]]) -> dict:
    """what a tool did with the truth book, read on its output by ``rules.lines_lean`` (the projection profile: nothing of
    safha's own): level pages still level and tilted pages levelled (the page's lines within 0.2 deg of level); warped
    pages whose level upper lines the tool made lean (beyond 0.35 deg)"""
    d = pymupdf.open(dst)
    n = {k: sum(1 for t, _ in kinds if t == k) for k in ("level", "tilt", "warp")}
    if d.page_count != len(kinds):
        return {k: "n/a (pages reflowed)" for k in ("level_kept", "tilted_levelled", "warped_wrongly_turned")}
    kept = levelled = wrong = 0
    leans = []
    for i, (kind, _) in enumerate(kinds):
        a = page_image(d[i])
        whole, upper = lines_lean(a), lines_lean(a, 0.05, 0.45)
        leans.append([None if v is None else v + 0.0 for v in (whole, upper)])
        if kind == "level":
            kept += whole is not None and abs(whole) <= 0.2
        elif kind == "tilt":
            levelled += whole is not None and abs(whole) <= 0.2
        else:
            wrong += upper is not None and abs(upper) > 0.35
    return {"level_kept": f"{kept}/{n['level']}", "tilted_levelled": f"{levelled}/{n['tilt']}",
            "warped_wrongly_turned": f"{wrong}/{n['warp']}", "leans": leans}


def rule_truth(path: str) -> dict:
    """pages with a printed column rule: how far the rule stands from upright (degrees). -> {"pages": with a rule,
    "median": median |lean|, "le02": pages within 0.2 deg, "gt05": pages beyond 0.5 deg, "leans": the leans by page}"""
    d = pymupdf.open(path)
    leans: dict[int, float] = {}
    for i, p in enumerate(d):
        z = 1400 / p.rect.width
        pix = p.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csGRAY, alpha=False)
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
        v = column_rule_lean(a)
        if v is not None:
            leans[i] = v
    v = [abs(x) for x in leans.values()]
    return {"pages": len(v), "median": round(float(np.median(v)), 3) if v else None, "le02": sum(1 for x in v if x <= 0.2),
            "gt05": sum(1 for x in v if x > 0.5), "leans": {str(k): x for k, x in leans.items()}}


def rule_change(before: dict, after: dict) -> dict:
    """page by page (those with a rule in both): pages the tool left further from upright than they were (by more than
    0.1 deg), and level pages (within 0.15 deg) it left beyond 0.3 deg"""
    both = [(before["leans"][k], after["leans"][k]) for k in before["leans"] if k in after["leans"]]
    return {"both": len(both), "worse": sum(1 for b, a in both if abs(a) > abs(b) + 0.1),
            "level_made_to_lean": sum(1 for b, a in both if abs(b) <= 0.15 and abs(a) > 0.3)}


# k2pdfopt-tm (its "trim margins" mode, native PDF output) is run only on request (ONLY_TOOLS): it needs a k2pdfopt
# built with MuPDF, and the Ubuntu 24.04 package (Ghostscript only) writes no file in that mode
TOOLS = ["safha", "safha-reader", "pdfCropMargins", "briss", "k2pdfopt", "k2pdfopt-as", "unpaper",
         "ocrmypdf-pdfa", "ocrmypdf", "ocrmypdf-O2", "ocrmypdf-O3", "ocrmypdf-new-pdfa", "ocrmypdf-new"]
RULE_BOOKS = ("dictionnairefra00lagogoog",)  # excerpts whose pages carry a printed column rule: real truth for turns


def main() -> None:
    work, books = sys.argv[1], sys.argv[2:]
    os.makedirs(work, exist_ok=True)
    only = os.environ.get("ONLY_TOOLS")
    tools = only.split(",") if only else TOOLS
    truth = os.path.join(work, "truth.pdf")
    kinds = truth_book(truth) if not os.environ.get("NO_TRUTH") else []
    keep_all = bool(os.environ.get("KEEP"))
    keep_books = tuple(b for b in os.environ.get("KEEP_BOOKS", "").split(",") if b)
    rows: list[dict] = [{"book": "", "tool": "versions", **versions()}]
    print(json.dumps(rows[0], ensure_ascii=False), flush=True)
    for src in books + ([truth] if kinds else []):
        name = os.path.basename(src)
        sd = pymupdf.open(src)
        lv = level_pages(src) if src != truth else []
        ruled = name.startswith(RULE_BOOKS)
        rt_in = rule_truth(src) if ruled else None
        base = {"book": name, "pages": sd.page_count, "bytes_in": os.path.getsize(src), "filters_in": image_filters(sd),
                "place_in": text_place(sd) if src != truth else None, "rule_in": rt_in}
        if src == truth:
            base.update(turns(src, kinds))  # (the judge on the book as drawn: nothing levelled, nothing made to lean)
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
                    if ruled and dd.page_count == sd.page_count:
                        row["rule_out"] = rule_truth(dst)
                        row["rule_change"] = rule_change(rt_in, row["rule_out"])
            except subprocess.CalledProcessError as e:
                row["error"] = (e.stderr or b"").decode(errors="replace")[-300:]
            except Exception as e:  # report and go on
                row["error"] = f"{type(e).__name__}: {e}"
            if not (keep_all or src == truth or name.startswith(keep_books or ("\0",))) and os.path.exists(dst):
                os.remove(dst)  # (some outputs are hundreds of megabytes)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        rows.append({"book": name, "tool": "input", **base})
    with open(os.path.join(work, os.environ.get("OUT", "compare.json")), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
