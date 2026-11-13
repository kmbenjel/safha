"""Lossless: the image streams byte for byte, the original bytes kept, restore, filters (JPEG, JBIG2, CCITT)."""

from __future__ import annotations

import hashlib
import os

import pymupdf
import pytest

import safha
from conftest import fixture
from safha.apply import ApplyError
from safha.pdf import image_filters, images_of


def read(path, n: int = -1) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def md5(path) -> str:
    return hashlib.md5(read(path)).hexdigest()


def test_images_untouched_and_restorable(books, plans, tmp_path):
    src, out, back = books["tilt"], tmp_path / "o.pdf", tmp_path / "back.pdf"
    rep = safha.apply_recipe(src, plans["tilt"], str(out))
    assert rep["reversible"]
    a, b = pymupdf.open(src), pymupdf.open(out)
    assert [[x[1:] for x in r] for r in images_of(a)] == [[x[1:] for x in r] for r in images_of(b)]
    assert read(out, os.path.getsize(src)) == read(src)
    safha.restore(str(out), str(back))
    assert md5(back) == md5(src)


def test_output_size_close_to_input(books, plans, tmp_path):
    out = tmp_path / "o.pdf"
    rep = safha.apply_recipe(books["tilt"], plans["tilt"], str(out))
    assert rep["bytes_out"] - rep["bytes_in"] < 20_000  # a few KB of drawing instructions


def test_compact_is_not_bigger(books, plans, tmp_path):
    a = safha.apply_recipe(books["tilt"], plans["tilt"], str(tmp_path / "a.pdf"))
    b = safha.apply_recipe(books["tilt"], plans["tilt"], str(tmp_path / "b.pdf"), compact=True)
    assert b["bytes_out"] <= a["bytes_out"] and not b["reversible"]
    with pytest.raises(ApplyError):
        safha.restore(str(tmp_path / "b.pdf"), str(tmp_path / "c.pdf"))


@pytest.mark.parametrize("name,flt", [("urdu-ccitt.pdf", "CCITTFaxDecode"), ("latin-jbig2.pdf", "JBIG2Decode"),
                                      ("arabic-leiden.pdf", "DCTDecode")])
def test_each_codec_kept(name, flt, tmp_path):
    src = fixture(name)
    rec = safha.plan(src, safha.load_profile("reader", {"min_text_pages": 1}))
    out = tmp_path / "o.pdf"
    safha.apply_recipe(src, rec, str(out))
    fa, fb = image_filters(pymupdf.open(src)), image_filters(pymupdf.open(out))
    assert flt in fa and fa == fb


def test_refuses_another_file(books, plans, tmp_path):
    with pytest.raises(ApplyError):
        safha.apply_recipe(books["level"], plans["tilt"], str(tmp_path / "x.pdf"))
    with pytest.raises(ApplyError):
        safha.apply_recipe(books["tilt"], plans["tilt"], books["tilt"])


def test_drop_pages_reversible(books, plans, tmp_path):
    r = dict(plans["blank"])
    r["drop"] = [3]
    out = tmp_path / "d.pdf"
    rep = safha.apply_recipe(books["blank"], r, str(out))
    assert rep["pages"] == 4 and rep["dropped"] == 1
    safha.restore(str(out), str(tmp_path / "r.pdf"))
    assert md5(tmp_path / "r.pdf") == md5(books["blank"])
