"""Crop: one box per book, centred on the text; spreads split; blank pages and stains."""

from __future__ import annotations

import json

import pymupdf

import safha
from safha.geometry import inside


def test_one_page_size_for_the_whole_book(books, plans, tmp_path):
    out = tmp_path / "o.pdf"
    safha.apply_recipe(books["offcentre"], plans["offcentre"], str(out))
    d = pymupdf.open(out)
    sizes = {(round(p.rect.width, 2), round(p.rect.height, 2)) for p in d}
    assert len(sizes) == 1


def test_text_centred_on_every_page(plans):
    r = plans["offcentre"]
    assert r["mode"] == "crop"
    for p in r["pages"]:
        c, t = p["crop"], p["text"]
        assert inside(t, c)
        left, right = t[0] - c[0], c[2] - t[2]
        assert abs(left - right) <= 0.02 * (c[2] - c[0])  # the text in the middle of the box, odd and even pages


def test_spread_split_into_two_pages(books, prof):
    r = safha.plan(books["spread"], prof.with_values(direction="ltr"))
    assert len(r["pages"]) == 6 and len(r["split"]) == 3
    rtl = safha.plan(books["spread"], prof.with_values(direction="rtl"))
    d0 = pymupdf.open(books["spread"])
    w = d0[0].rect.width
    from safha.pdf import open_book

    a, b = open_book(books["spread"], r), open_book(books["spread"], rtl)
    assert a[0].cropbox.x0 < w / 4 and b[0].cropbox.x0 > w / 4  # LTR: left page first; RTL: right page first


def test_blank_page_and_stain(plans):
    r = plans["blank"]
    assert r["pages"][2]["kind"] == "blank"
    p = r["pages"][3]
    assert p["blots"], "the stain beside the text is found"
    assert all(not inside(b, p["crop"], 0) for b in p["blots"]), "and left outside the box"


def test_recipe_is_json_and_reapplies(books, plans, tmp_path):
    r = json.loads(json.dumps(plans["tilt"]))
    assert r["schema"] == 1 and r["source"]["md5"]
    rep = safha.apply_recipe(books["tilt"], r, str(tmp_path / "a.pdf"))
    assert rep["pages"] == 5 and rep["turned"] >= 1


def test_good_scan_is_left_alone(books):
    r = safha.plan(books["level"], safha.load_profile(None, {"min_text_pages": 1, "gain_min": 3.0}))
    assert r["mode"] == "skip" and "good scan" in r["why"]
    r2 = safha.plan(books["level"], safha.load_profile("reader", {"min_text_pages": 1, "gain_min": 3.0}))
    assert r2["mode"] == "crop"


def test_few_pages_skipped(books):
    r = safha.plan(books["level"])  # the default needs 5 text pages: this book has 5
    assert r["mode"] in ("crop", "skip")
    r = safha.plan(books["level"], safha.load_profile(None, {"min_text_pages": 9}))
    assert r["mode"] == "skip" and "few text pages" in r["why"]


def test_jobs_do_not_change_the_result(books, prof):
    a = safha.plan(books["tilt"], prof, jobs=1)
    b = safha.plan(books["tilt"], prof, jobs=3)
    strip = lambda r: [{k: v for k, v in p.items()} for p in r["pages"]]
    assert strip(a) == strip(b)


def test_level_only_book(books, tmp_path):
    """a good scan whose only flaw is a tilted page: the page is turned, nothing else changes"""
    prof = safha.load_profile(None, {"min_text_pages": 1, "gain_min": 3.0, "offcentre": 1.0, "sway": 1.0})
    r = safha.plan(books["tilt"], prof)
    assert r["mode"] == "level" and r["summary"]["turned"] == [3]
    out = tmp_path / "l.pdf"
    rep = safha.apply_recipe(books["tilt"], r, str(out))
    assert rep["turned"] == 1
    a, b = pymupdf.open(books["tilt"]), pymupdf.open(out)
    assert [p.rect for p in a] == [p.rect for p in b]


def test_cover_on_the_scanner_bed(tmp_path, prof):
    """a coloured cover photographed on a dark bed is shown alone, filling the book's page"""
    from PIL import Image, ImageDraw

    import synth

    cover = Image.new("RGB", (900, 1300), (30, 30, 30))
    ImageDraw.Draw(cover).rectangle([120, 140, 780, 1180], fill=(150, 40, 40))
    pages = [cover] + [synth.page(seed=i).convert("RGB") for i in range(5)]
    path = synth.write(tmp_path / "c.pdf", pages)
    r = safha.plan(path, prof)
    assert r["pages"][0]["kind"] == "cover"
    c = r["pages"][0]["cover"]
    assert abs(c[0] - 120 * 72 / 150) < 6 and abs(c[2] - 780 * 72 / 150) < 6


def test_reading_order_comes_from_the_text_layer(tmp_path, prof):
    """spreads with an OCR layer: Arabic letters say right page first, Latin letters left page first, unasked"""
    import os

    import pytest

    import synth

    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(font):
        pytest.skip("no font with Arabic letters here")
    for name, words, want in (("ar", "كتاب العلوم والفنون والآداب", "rtl"), ("la", "the book of the sciences and the arts", "ltr")):
        d = pymupdf.open("pdf", synth.book([synth.spread(seed=i) for i in range(3)]))
        for p in d:
            for k in range(8):  # an invisible text layer over the scan
                p.insert_text((100, 100 + 20 * k), words, fontsize=9, fontname="dv", fontfile=font, render_mode=3)
        path = tmp_path / f"{name}.pdf"
        path.write_bytes(d.tobytes())
        r = safha.plan(str(path), prof)
        assert (r["direction"], r["direction_from"]) == (want, "text layer") and len(r["split"]) == 3, name


def test_split_never_always_and_a_wrap_around_cover(tmp_path, books, prof):
    import synth
    from safha.pages import find_spreads

    d = pymupdf.open(books["spread"])
    assert len(find_spreads(d, "auto")) == 3 and find_spreads(d, "never") == {}
    # one two-page sheet among portrait pages: no book of spreads, so it is split only when asked
    mixed = synth.write(tmp_path / "mixed.pdf", [synth.page(seed=i) if i != 3 else synth.spread(seed=3) for i in range(7)])
    d = pymupdf.open(mixed)
    assert find_spreads(d, "auto") == {} and list(find_spreads(d, "always")) == ["3"]
    r = safha.plan(mixed, prof.with_values(split="always", direction="ltr"))
    assert len(r["pages"]) == 8 and r["split"].keys() == {"3"}
    # a wrap-around cover (back, spine and front on one sheet, more than half again as wide as tall) opens the book:
    # split down its middle, the book's own pages left alone
    from PIL import Image, ImageDraw

    cover = Image.new("L", (2200, 1300), 235)
    dr = ImageDraw.Draw(cover)
    dr.rectangle([1070, 0, 1130, 1299], fill=90)  # the spine
    dr.text((1400, 500), "A TITLE", fill=20, font=synth.font(90))
    wrapped = synth.write(tmp_path / "cover.pdf", [cover] + [synth.page(seed=i) for i in range(6)])
    sp = find_spreads(pymupdf.open(wrapped), "auto")
    assert list(sp) == ["0"] and abs(sp["0"] - 2200 * 72 / 150 / 2) <= 30


def test_progress_is_told_as_the_pages_are_worked(books, prof):
    for jobs in (1, 2):
        seen: list[tuple[str, int, int]] = []
        r = safha.plan(books["offcentre"], prof, jobs=jobs, progress=lambda stage, done, n: seen.append((stage, done, n)))
        assert r["mode"] == "crop" and {s for s, _, _ in seen} == {"measure", "check"}
        for stage in ("measure", "check"):
            done = [d for s, d, _ in seen if s == stage]
            assert len(done) >= 3 and done == sorted(done) and done[-1] == 6, f"{stage}, {jobs} jobs: {done}"
