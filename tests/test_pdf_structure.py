"""What a PDF may already carry: its own CropBox, /Rotate, encryption, links, an outline, an OCR text layer, content
streams that do not balance. The image streams stay byte for byte, the original restores by hash, the picture shown is
the one the recipe names."""

from __future__ import annotations

import hashlib

import numpy as np
import pymupdf
import pytest

import safha
import synth
from safha.cli import main
from safha.pdf import gray, images_of, open_book, raw_box, turned


def md5(path) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


@pytest.fixture(scope="module")
def base() -> bytes:
    """eight pages, the fourth tilted one degree"""
    return synth.book([synth.page(seed=i, tilt=(1.0 if i == 3 else 0)) for i in range(8)])


def run(tmp_path, name: str, data: bytes, **over):
    src = tmp_path / f"{name}.pdf"
    src.write_bytes(data)
    rec = safha.plan(str(src), safha.load_profile("reader", {"min_text_pages": 1, **over}))
    out = tmp_path / f"{name}.safha.pdf"
    rep = safha.apply_recipe(str(src), rec, str(out)) if rec["mode"] in ("crop", "level") else None
    return str(src), rec, str(out), rep


def same_picture(src: str, rec: dict, out: str, i: int) -> float:
    """correlation of output page i with the part of the reader's frame the recipe names (both blurred, 300 px wide)"""
    from PIL import Image
    from scipy import ndimage

    p = rec["pages"][i]
    doc = open_book(src, rec)
    mv = (p.get("move") or [0, 0]) if p.get("crop") else [0, 0]
    a, z = gray(turned(doc, i, p.get("skew") or 0, mv[0], mv[1], p.get("shear") or 0)[0], 600)
    a = np.array(a)
    x0, y0, x1, y1 = [int(round(v * z)) for v in p["show"]]
    pad = np.full((y1 - y0, x1 - x0), 255, np.uint8)
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(a.shape[1], x1), min(a.shape[0], y1)
    pad[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = a[sy0:sy1, sx0:sx1]
    b, _ = gray(pymupdf.open(out)[i], 300)
    A = ndimage.gaussian_filter(np.asarray(Image.fromarray(pad).resize((b.shape[1], b.shape[0]), Image.BILINEAR)).astype(float), 2.5)
    B = ndimage.gaussian_filter(np.array(b).astype(float), 2.5)
    va, vb = A - A.mean(), B - B.mean()
    return float((va * vb).sum() / np.sqrt((va * va).sum() * (vb * vb).sum()))


def check_lossless(src: str, rec: dict, out: str, rep: dict, tmp_path) -> None:
    a, b = pymupdf.open(src), pymupdf.open(out)
    assert [[x[1:] for x in r] for r in images_of(a)] == [[x[1:] for x in r] for r in images_of(b)]
    assert rep["reversible"]
    back = tmp_path / "back.pdf"
    safha.restore(out, str(back))
    assert md5(back) == md5(src)
    assert len({(round(p.rect.width, 2), round(p.rect.height, 2)) for p in b}) == 1
    for i in (0, 3):  # an untouched page and the turned one
        assert same_picture(src, rec, out, i) >= 0.93, f"page {i + 1} is not the part the recipe names"


def test_existing_cropbox_and_offset_mediabox(base, tmp_path):
    d = pymupdf.open("pdf", base)
    for p in d:  # a MediaBox whose origin is not zero, a CropBox inside it
        d.xref_set_key(p.xref, "MediaBox", "[-50 -30 482 654]")
        d.xref_set_key(p.xref, "CropBox", "[-20 -10 462 634]")
    src, rec, out, rep = run(tmp_path, "cropbox", d.tobytes())
    assert rec["mode"] == "crop" and rec["summary"]["turned"] == [4]
    check_lossless(src, rec, out, rep, tmp_path)


def test_cropbox_that_already_trims_the_scan(base, tmp_path):
    d = pymupdf.open("pdf", base)
    for p in d:
        d.xref_set_key(p.xref, "CropBox", "[40 30 412 604]")
    src, rec, out, rep = run(tmp_path, "trimmed", d.tobytes())
    check_lossless(src, rec, out, rep, tmp_path)


def test_boxes_written_the_unusual_ways(base, tmp_path):
    """a MediaBox kept in an object of its own, written from its top left to its bottom right corner, holding a number
    that is an object of its own, or inherited from the page tree: read all the same"""
    d = pymupdf.open("pdf", base)
    root = int(d.xref_get_key(d.pdf_catalog(), "Pages")[1].split()[0])
    box = d.xref_get_key(d[0].xref, "MediaBox")[1]
    v = box.strip("[] ").split()
    for i, p in enumerate(d):
        if i % 4 == 0:
            x = d.get_new_xref()
            d.update_object(x, box)
            d.xref_set_key(p.xref, "MediaBox", f"{x} 0 R")
        elif i % 4 == 1:
            d.xref_set_key(p.xref, "MediaBox", f"[{v[0]} {v[3]} {v[2]} {v[1]}]")
        elif i % 4 == 2:
            x = d.get_new_xref()
            d.update_object(x, v[3])
            d.xref_set_key(p.xref, "MediaBox", f"[{v[0]} {v[1]} {v[2]} {x} 0 R]")
        else:
            d.xref_set_key(p.xref, "MediaBox", "null")
    d.xref_set_key(root, "MediaBox", box)
    d = pymupdf.open("pdf", d.tobytes())
    for p in d:
        assert raw_box(d, p.xref, "MediaBox") == [float(x) for x in v], f"page {p.number + 1}"
        assert raw_box(d, p.xref, "CropBox") is None
    src, rec, out, rep = run(tmp_path, "boxes", d.tobytes())
    assert rec["mode"] == "crop" and rec["summary"]["turned"] == [4]
    check_lossless(src, rec, out, rep, tmp_path)


@pytest.mark.parametrize("enc", ["RC4_40", "AES_128", "AES_256"])
def test_owner_password_keeps_everything(base, tmp_path, enc):
    data = pymupdf.open("pdf", base).tobytes(encryption=getattr(pymupdf, "PDF_ENCRYPT_" + enc), owner_pw="owner", user_pw="")
    src, rec, out, rep = run(tmp_path, "enc", data)
    check_lossless(src, rec, out, rep, tmp_path)
    assert pymupdf.open(out).metadata["encryption"]  # still encrypted


def test_user_password_is_refused_plainly(base, tmp_path, capsys):
    src = tmp_path / "locked.pdf"
    src.write_bytes(pymupdf.open("pdf", base).tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u"))
    with pytest.raises(ValueError, match="password"):
        safha.plan(str(src))
    assert main(["crop", str(src), "-q"]) == 2
    assert "password" in capsys.readouterr().err


def test_links_outline_and_text_layer_stay(base, tmp_path):
    d = pymupdf.open("pdf", base)
    for p in d:
        p.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(150, 200, 260, 215), "uri": "https://example.org/"})
        for k in range(8):  # an OCR layer: invisible text over the scan
            p.insert_text((100 + 20 * k, 150 + 40 * k), f"word{k}", fontsize=10, render_mode=3)
    d.set_toc([[1, "One", 1], [1, "Two", 4], [2, "Two-a", 5], [1, "Three", 8]])
    src, rec, out, rep = run(tmp_path, "rich", d.tobytes())
    check_lossless(src, rec, out, rep, tmp_path)
    a, b = pymupdf.open(src), pymupdf.open(out)
    assert b.get_toc() == a.get_toc()
    assert [len(p.get_links()) for p in b] == [1] * 8
    for i in (0, 3):  # the text layer turns and moves with the scan: each word where it was on the picture
        ia, ib = pymupdf.Matrix(a[i].get_image_info()[0]["transform"]), pymupdf.Matrix(b[i].get_image_info()[0]["transform"])
        wa = {w[4]: w for w in a[i].get_text("words")}
        wb = {w[4]: w for w in b[i].get_text("words")}
        assert wa.keys() == wb.keys() and len(wa) == 8
        for k, w in wa.items():
            ca = pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2) * ~ia
            cb = pymupdf.Point((wb[k][0] + wb[k][2]) / 2, (wb[k][1] + wb[k][3]) / 2) * ~ib
            assert abs(ca.x - cb.x) < 2e-3 and abs(ca.y - cb.y) < 2e-3


def test_pages_turned_by_rotate_are_measured_as_they_are_shown(base, tmp_path):
    """a ``/Rotate`` on some pages (here they are shown on their side and upside down, as a careless scan is): every
    page is measured as the reader shows it, and the book still comes out at one page size, restorable"""
    d = pymupdf.open("pdf", base)
    d[2].set_rotation(90)
    d[5].set_rotation(180)
    src, rec, out, rep = run(tmp_path, "rot", d.tobytes())
    assert "rotated" not in rec["summary"]["kinds"] and rec["pages"][5]["kind"] == "text"
    assert rec["pages"][2]["w"] > rec["pages"][2]["h"]  # the page on its side, as shown
    b = pymupdf.open(out)
    assert len({(round(p.rect.width, 2), round(p.rect.height, 2)) for p in b}) == 1
    assert md5(tmp_path / "rot.pdf") == safha.restore(out, str(tmp_path / "b.pdf"))["md5"]
    assert same_picture(src, rec, out, 5) >= 0.93  # the page shown upside down: the part the recipe names, as shown


def test_a_page_whose_frame_cannot_be_followed_is_shown_whole(base, tmp_path, capsys, monkeypatch):
    """the way out for a page MuPDF shows otherwise than its boxes say: it is not measured, and is shown whole at the
    book's page size"""
    import safha.detect
    import safha.pages

    for module in (safha.detect, safha.pages):
        monkeypatch.setattr(module, "shown_as_computed", lambda page: not page.rotation)
    d = pymupdf.open("pdf", base)
    d[2].set_rotation(90)
    d[5].set_rotation(180)
    src, rec, out, rep = run(tmp_path, "rot", d.tobytes())
    assert rec["summary"]["kinds"] == {"rotated": 2, "text": 6}
    b = pymupdf.open(out)
    assert len({(round(p.rect.width, 2), round(p.rect.height, 2)) for p in b}) == 1  # one size all the same
    assert md5(tmp_path / "rot.pdf") == safha.restore(out, str(tmp_path / "b.pdf"))["md5"]
    for p in d:
        p.set_rotation(90)
    whole = tmp_path / "allrot.pdf"
    whole.write_bytes(d.tobytes())
    r = safha.plan(str(whole))
    assert r["mode"] == "skip" and "/Rotate" in r["why"]
    assert main(["crop", str(whole)]) == 0
    assert "--always" not in capsys.readouterr().out  # no advice that would not help


def test_content_that_does_not_balance(base, tmp_path):
    """a stray ``Q`` at the head of a page's content undoes any matrix set before it: a turn that does not take is
    never kept, and the picture shown is still the part the recipe names"""
    d = pymupdf.open("pdf", base)
    for p in d:
        x = p.get_contents()[0]
        d.update_stream(x, b"Q\n" + d.xref_stream(x))
    src, rec, out, rep = run(tmp_path, "stray", d.tobytes())
    assert not rec["summary"]["turned"]
    a, b = pymupdf.open(src), pymupdf.open(out)
    assert [[x[1:] for x in r] for r in images_of(a)] == [[x[1:] for x in r] for r in images_of(b)]
    assert same_picture(src, rec, out, 0) >= 0.93


def test_scan_in_strips(tmp_path):
    """each page's scan stored as four images, as many scanners write them"""
    import io

    d = pymupdf.open()
    for i in range(8):
        im = synth.page(seed=i, tilt=(1.0 if i == 3 else 0))
        w, h = im.size
        p = d.new_page(width=w * 72 / 150, height=h * 72 / 150)
        for k in range(4):
            buf = io.BytesIO()
            im.crop((0, k * h // 4, w, (k + 1) * h // 4)).save(buf, "PNG")
            p.insert_image(pymupdf.Rect(0, k * h // 4 * 72 / 150, w * 72 / 150, (k + 1) * h // 4 * 72 / 150), stream=buf.getvalue())
    src, rec, out, rep = run(tmp_path, "strips", d.tobytes())
    assert rec["summary"]["turned"] == [4]
    check_lossless(src, rec, out, rep, tmp_path)


def test_scan_inside_a_form(base, tmp_path):
    """each page draws a form that holds the scan (as files written by "print to PDF" and by some imposition tools
    do): the image inside the form is still listed, checked and untouched"""
    src_doc = pymupdf.open("pdf", base)
    d = pymupdf.open()
    for i in range(src_doc.page_count):
        p = d.new_page(width=src_doc[i].rect.width, height=src_doc[i].rect.height)
        p.show_pdf_page(p.rect, src_doc, i)
    src, rec, out, rep = run(tmp_path, "form", d.tobytes())
    assert rec["summary"]["turned"] == [4] and all(len(row) == 1 for row in images_of(pymupdf.open(src)))
    check_lossless(src, rec, out, rep, tmp_path)


def test_safha_on_its_own_output_restores_step_by_step(base, tmp_path):
    src, rec, out, rep = run(tmp_path, "one", base)
    rec2 = safha.plan(out, safha.load_profile("reader", {"min_text_pages": 1}))
    assert not rec2["summary"]["turned"]  # the page it levelled reads level
    out2 = tmp_path / "two.pdf"
    if rec2["mode"] in ("crop", "level"):
        safha.apply_recipe(out, rec2, str(out2))
        safha.restore(str(out2), str(tmp_path / "b1.pdf"))
        assert md5(tmp_path / "b1.pdf") == md5(out)
    safha.restore(out, str(tmp_path / "b0.pdf"))
    assert md5(tmp_path / "b0.pdf") == md5(src)


def test_split_says_where_the_order_came_from(books, prof, capsys):
    r = safha.plan(books["spread"], prof)
    assert r["direction"] == "ltr" and r["direction_from"] == "default"  # no text layer: nothing to tell it from
    from safha.cli import summary_lines

    assert any("--rtl" in ln for ln in summary_lines(r))
    r = safha.plan(books["spread"], prof.with_values(direction="rtl"))
    assert r["direction_from"] == "option" and not any("--rtl" in ln for ln in summary_lines(r))
