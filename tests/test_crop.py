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
