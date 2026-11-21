"""Pages stored sideways and shown upright by ``/Rotate``, or counted in another unit (``/UserUnit``), are measured and
written like any other: the same scans stored either way give the same recipe and the same pages."""

from __future__ import annotations

import hashlib
import io

import numpy as np
import pymupdf
import pytest
from PIL import Image
from scipy import ndimage

import safha
import synth
from safha.pdf import display_matrix, gray, images_of, open_book, plain, shown_as_computed

STORED = {0: None, 90: Image.ROTATE_90, 180: Image.ROTATE_180, 270: Image.ROTATE_270}


def stored(images: list[Image.Image], rot: int | list[int] = 0, unit: float = 1.0, boxes: bool = False, dpi: float = 150) -> bytes:
    """the scans as a book whose pages are stored turned and shown upright by ``/Rotate rot`` (one value, or one per
    page), their coordinates counted in units of ``unit`` points; ``boxes``: a MediaBox that goes beyond the scan on
    every side, by other amounts, and a CropBox on the scan"""
    doc = pymupdf.open()
    for k, im in enumerate(images):
        r = rot[k % len(rot)] if isinstance(rot, list) else rot
        s = im if not r else im.transpose(STORED[r])
        buf = io.BytesIO()
        s.save(buf, "PNG")
        w, h = s.width * 72 / dpi / unit, s.height * 72 / dpi / unit
        p = doc.new_page(width=w, height=h)
        p.insert_image(p.rect, stream=buf.getvalue())
        if boxes:
            doc.xref_set_key(p.xref, "MediaBox", f"[-20 -31.5 {w + 44:.2f} {h + 12:.2f}]")
            doc.xref_set_key(p.xref, "CropBox", f"[0 0 {w:.2f} {h:.2f}]")
        if r:
            doc.xref_set_key(p.xref, "Rotate", str(r))
        if unit != 1.0:
            doc.xref_set_key(p.xref, "UserUnit", f"{unit:g}")
    return doc.tobytes(garbage=3, deflate=True)


def write(tmp_path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def md5(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def alike(a: pymupdf.Page, b: pymupdf.Page) -> float:
    """how alike two shown pages are: the correlation of their pictures (blurred, 300 px wide)"""
    A, B = (ndimage.gaussian_filter(np.array(gray(p, 300)[0]).astype(float), 3) for p in (a, b))
    h, w = min(A.shape[0], B.shape[0]), min(A.shape[1], B.shape[1])
    va, vb = A[:h, :w] - A[:h, :w].mean(), B[:h, :w] - B[:h, :w].mean()
    return float((va * vb).sum() / max(1e-9, np.sqrt((va * va).sum() * (vb * vb).sum())))


def same_result(tmp_path, images: list, prof, name: str, **how) -> tuple[dict, dict]:
    """the book stored upright and stored as ``how`` says: the same decisions, the same pages shown"""
    up = write(tmp_path, f"{name}-up.pdf", stored(images))
    tw = write(tmp_path, f"{name}-tw.pdf", stored(images, **how))
    a, b = safha.plan(up, prof), safha.plan(tw, prof)
    assert b["mode"] == a["mode"] and b["mode"] in ("crop", "level")
    assert (a.get("split") or {}).keys() == (b.get("split") or {}).keys()
    if a.get("size"):
        assert all(abs(u - v) <= 1.5 for u, v in zip(a["size"], b["size"]))
    assert a["summary"]["kinds"] == b["summary"]["kinds"] and "rotated" not in b["summary"]["kinds"]
    for p, q in zip(a["pages"], b["pages"], strict=True):
        for k in ("skew", "shear"):
            assert (p.get(k) is None) == (q.get(k) is None) and abs((p.get(k) or 0) - (q.get(k) or 0)) <= 0.08, \
                f"page {p['n']} {k}: {p.get(k)} upright, {q.get(k)} stored otherwise"
        for k in ("show", "crop", "move"):
            assert (p.get(k) is None) == (q.get(k) is None), f"page {p['n']} {k}"
            if p.get(k):
                assert all(abs(u - v) <= 2.5 for u, v in zip(p[k], q[k])), f"page {p['n']} {k}: {p[k]} / {q[k]}"
    ou, ot = str(tmp_path / f"{name}-up.out.pdf"), str(tmp_path / f"{name}-tw.out.pdf")
    safha.apply_recipe(up, a, ou)
    rep = safha.apply_recipe(tw, b, ot)
    du, dt = pymupdf.open(ou), pymupdf.open(ot)
    assert du.page_count == dt.page_count
    for pu, pt in zip(du, dt):
        assert abs(pu.rect.width - pt.rect.width) <= 1.6 and abs(pu.rect.height - pt.rect.height) <= 1.6
        assert alike(pu, pt) >= 0.9, f"page {pu.number + 1} is not the page the upright book shows"
    if b["mode"] == "crop":
        assert len({(round(p.rect.width, 1), round(p.rect.height, 1)) for p in dt}) == 1  # one page size
    src = pymupdf.open(tw)  # lossless and restorable all the same
    want = images_of(src)
    if b.get("split"):
        want = [im for i, im in enumerate(want) for _ in range(2 if str(i) in b["split"] else 1)]
    assert [[x[1:] for x in r] for r in images_of(dt)] == [[x[1:] for x in r] for r in want]
    assert rep["reversible"]
    safha.restore(ot, str(tmp_path / "back.pdf"))
    assert md5(str(tmp_path / "back.pdf")) == md5(tw)
    return a, b


@pytest.fixture(scope="module")
def tilted() -> list[Image.Image]:
    return [synth.page(seed=i, tilt=(1.0 if i == 2 else 0)) for i in range(5)]


@pytest.mark.parametrize("rot", [0, 90, 180, 270])
@pytest.mark.parametrize("unit", [1.0, 2.5])
@pytest.mark.parametrize("boxes", [False, True])
def test_display_matrix_is_what_mupdf_draws(rot, unit, boxes):
    """a mark at a known place of the scan: where the matrix says it is shown is where the rendered page has it"""
    im = Image.new("L", (600, 900), 255)
    im.paste(0, (130, 250, 190, 290))  # the mark, upright: 60 x 40 px at (130, 250)
    d = pymupdf.open("pdf", stored([im], rot, unit, boxes))
    page = d[0]
    assert shown_as_computed(page) and plain(page) == (rot == 0 and unit == 1.0)
    assert abs(page.rect.width - 600 * 72 / 150) < 0.05 and abs(page.rect.height - 900 * 72 / 150) < 0.05
    a = np.array(gray(page, 600)[0])  # one pixel of the scan per pixel
    ys, xs = np.nonzero(a < 128)
    assert abs(xs.min() - 130) <= 1 and abs(xs.max() - 189) <= 1 and abs(ys.min() - 250) <= 1 and abs(ys.max() - 289) <= 1
    # the mark's corners in the stored scan, in PDF coordinates (the scan lies on [0 0 w h], y upward)
    s = im if not rot else im.transpose(STORED[rot])
    sy, sx = np.nonzero(np.array(s) < 128)
    k = 72 / 150 / unit
    pts = [pymupdf.Point(x * k, (s.height - y) * k) * display_matrix(page)
           for x in (sx.min(), sx.max() + 1) for y in (sy.min(), sy.max() + 1)]
    got = [min(q.x for q in pts), min(q.y for q in pts), max(q.x for q in pts), max(q.y for q in pts)]
    want = [v * 72 / 150 for v in (130, 250, 190, 290)]
    assert all(abs(g - w) < 0.01 for g, w in zip(got, want)), f"{got} is not {want}"


@pytest.mark.parametrize("rot", [90, 180, 270])
def test_a_book_stored_sideways_comes_out_the_same(tilted, tmp_path, prof, rot):
    a, b = same_result(tmp_path, tilted, prof, f"rot{rot}", rot=rot)
    assert b["mode"] == "crop" and b["summary"]["turned"] == [3]


def test_only_some_pages_stored_sideways_and_boxes_off_the_scan(tilted, tmp_path, prof):
    a, b = same_result(tmp_path, tilted, prof, "mixed", rot=[0, 90, 270, 180, 90], boxes=True)
    assert b["summary"]["turned"] == [3]


def test_another_unit(tilted, tmp_path, prof):
    """/UserUnit: the page is 2.5 times what its numbers say; alone and with a /Rotate"""
    a, b = same_result(tmp_path, tilted, prof, "unit", unit=2.5)
    assert b["summary"]["turned"] == [3]
    same_result(tmp_path, tilted, prof, "unit-rot", unit=2.5, rot=90, boxes=True)


def test_sheared_print_stored_sideways(tmp_path, prof):
    ims = [synth.page(seed=i, frame=True, shear=(1.6 if i == 2 else 0)) for i in range(5)]
    a, b = same_result(tmp_path, ims, prof, "shear", rot=90)
    assert b["summary"]["sheared"] == [3]


def test_spreads_stored_sideways_are_split_in_the_right_order(tmp_path, prof):
    ims = [synth.spread(seed=i) for i in range(3)]
    rtl = prof.with_values(direction="rtl")
    a, b = same_result(tmp_path, ims, rtl, "spread", rot=270)
    assert len(b["split"]) == 3 and len(b["pages"]) == 6
    # the right page carries a mark at its top (a 3 x 3 dot grid): it comes first right to left, second left to right
    tw = str(tmp_path / "spread-tw.pdf")

    def has_mark(page: pymupdf.Page) -> bool:
        a_ = np.array(gray(page, 450)[0])
        return bool((a_[int(0.03 * a_.shape[0]):int(0.09 * a_.shape[0])] < 100).mean() > 0.01)

    d = open_book(tw, b)
    assert has_mark(d[0]) and not has_mark(d[1])
    d = open_book(tw, dict(b, direction="ltr"))
    assert not has_mark(d[0]) and has_mark(d[1])


def test_content_moved_on_white_paper_stored_sideways(tmp_path, prof):
    """text against the sheet's edge: on white paper the content moves into the box; the move is that of the page as
    shown"""
    ims = [synth.page(seed=i, margin=(24, 160, 276, 170)) for i in range(5)]
    a, b = same_result(tmp_path, ims, prof, "moved", rot=90, unit=2.5)
    assert a["summary"]["moved"] and b["summary"]["moved"] == a["summary"]["moved"]


def test_level_only_on_grey_paper_stored_sideways(tmp_path):
    ims = [synth.page(seed=i, tilt=(2.5 if i == 2 else 0), margin=(40, 40, 40, 40)).point(lambda v: min(v, 215)) for i in range(6)]
    prof = safha.load_profile(None, {"min_text_pages": 1, "gain_min": 9.0, "offcentre": 1.0, "sway": 1.0})
    a, b = same_result(tmp_path, ims, prof, "grey", rot=180)
    assert b["mode"] == "level" and b["level_trim"] and b["summary"]["turned"] == [3]


def test_leaf_askew_on_the_bed_stored_sideways(tmp_path, prof):
    ims = [synth.on_bed(i, {2: 1.2, 4: -0.9}.get(i, 0.0)) for i in range(6)]
    a, b = same_result(tmp_path, ims, prof, "bed", rot=90)
    assert b["mode"] == "crop" and b["summary"]["turned"] == [3, 5] and not b["summary"]["whole"]


def test_review_sheet_of_a_book_stored_sideways(tilted, tmp_path, prof):
    """the box drawn on the scan lies on the text, as on the upright book's sheet"""
    from safha.sheet import contact_sheet

    sheets = []
    for name, how in (("up", {}), ("tw", {"rot": 90, "unit": 2.5, "boxes": True})):
        path = write(tmp_path, f"{name}.pdf", stored(tilted, **how))
        out = contact_sheet(path, safha.plan(path, prof), str(tmp_path / f"{name}.png"), [(1, "asked"), (2, "asked")])
        sheets.append(np.asarray(Image.open(out).convert("RGB")).astype(int))
    a, b = sheets
    assert a.shape == b.shape
    red = [(s[..., 0] > 150) & (s[..., 1] < 90) & (s[..., 2] < 90) for s in (a, b)]  # the box's red line
    assert red[0].sum() > 500 and abs(int(red[0].sum()) - int(red[1].sum())) < 0.2 * red[0].sum()
    ya, xa = np.nonzero(red[0])
    yb, xb = np.nonzero(red[1])
    for u, v in ((xa.min(), xb.min()), (xa.max(), xb.max()), (ya.min(), yb.min()), (ya.max(), yb.max())):
        assert abs(int(u) - int(v)) <= 4
