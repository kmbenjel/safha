"""Ordinary mistakes get one plain line and exit status 2, never a traceback; a refused output never stays on disk."""

from __future__ import annotations

import json
import os

import pymupdf
import pytest

import safha
import synth
from safha.apply import ApplyError, _starts_with
from safha.cli import _pages, main


def fails(capsys, args: list[str], *said: str) -> str:
    """the command fails with status 2 and says each of ``said`` on stderr"""
    assert main(args) == 2, args
    err = capsys.readouterr().err
    assert err.strip().splitlines()[-1].startswith("safha: ") and "Traceback" not in err
    for w in said:
        assert w in err, f"{w!r} not in {err!r}"
    return err


@pytest.fixture(scope="module")
def recipe(books, plans, tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("recipes") / "tilt.json"
    path.write_text(json.dumps(plans["tilt"]), encoding="utf-8")
    return str(path)


def test_recipe_files_that_are_no_recipe(books, recipe, tmp_path, capsys):
    out = str(tmp_path / "o.pdf")
    fails(capsys, ["apply", books["tilt"], str(tmp_path / "none.json"), "-o", out], "no such file")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    fails(capsys, ["apply", books["tilt"], str(bad), "-o", out], "not JSON")
    other = tmp_path / "other.json"
    other.write_text('{"a": 1}')
    fails(capsys, ["apply", books["tilt"], str(other), "-o", out], "not a safha recipe")
    fails(capsys, ["inspect", str(other)], "not a safha recipe")
    fails(capsys, ["sheet", books["tilt"], "--recipe", str(other)], "not a safha recipe")
    fails(capsys, ["sheet", books["tilt"], "--recipe", str(tmp_path / "none.json")], "no such file")
    newer = tmp_path / "newer.json"
    with open(recipe, encoding="utf-8") as f:
        newer.write_text(json.dumps(dict(json.load(f), schema=99)))
    fails(capsys, ["apply", books["tilt"], str(newer), "-o", out], "newer safha")
    assert not os.path.exists(out)


def test_page_numbers(books, recipe, tmp_path, capsys):
    assert _pages("3") == [3] and _pages("1,4-6, 2") == [1, 2, 4, 5, 6] and _pages(None) == [] and _pages("") == []
    assert _pages("4-", last=6) == [4, 5, 6]
    for bad in ("abc", "0", "5-2", "1-2-3", "-3", "2-"):
        with pytest.raises(ValueError, match="pages"):
            _pages(bad)
    with pytest.raises(ValueError, match="not in the book"):
        _pages("3-9", last=5)
    sheet = ["sheet", books["tilt"], "--recipe", recipe, "-o", str(tmp_path / "s.jpg")]
    fails(capsys, [*sheet, "--pages", "0"], "counted from 1")  # (page 0 once showed the last page)
    fails(capsys, [*sheet, "--pages", "99"], "page 99 is not in the book (5 pages)")
    fails(capsys, [*sheet, "--pages", "x"], "page numbers")
    assert not (tmp_path / "s.jpg").exists()
    assert main([*sheet, "--pages", "2,4-"]) == 0 and (tmp_path / "s.jpg").exists()
    fails(capsys, ["crop", books["tilt"], "--drop", "x", "-q"], "--drop expects page numbers")
    fails(capsys, ["drop", books["blank"], "--pages", "9"], "page 9 is not in the book")


def test_settings_are_checked(books, tmp_path, capsys):
    fails(capsys, ["crop", books["tilt"], "--set", "split=sideways"], "one of auto, always, never")
    fails(capsys, ["crop", books["tilt"], "--set", "skew_min=abc"], "skew_min expects a number")
    fails(capsys, ["crop", books["tilt"], "--set", "always=flase"], "true or false")
    fails(capsys, ["crop", books["tilt"], "--profile", "nope"], "no profile named")
    bad = tmp_path / "p.toml"
    bad.write_text("margin = = 1\n")
    fails(capsys, ["crop", books["tilt"], "--profile", str(bad)], "cannot be read")
    bad.write_text('base = "kindle"\n')
    fails(capsys, ["crop", books["tilt"], "--profile", str(bad)], "no built-in profile")
    with pytest.raises(ValueError, match="direction is one of"):
        safha.load_profile(None, {"direction": "up"})
    assert safha.load_profile(None, {"deskew": "off", "min_text_pages": "2", "margin": 1}).margin == 1.0


def test_inputs_that_are_no_scanned_pdf(tmp_path, capsys):
    (tmp_path / "empty.pdf").write_bytes(b"")
    (tmp_path / "words.pdf").write_bytes(b"not a pdf at all\n" * 40)
    synth.page(seed=1).save(tmp_path / "page.png")
    (tmp_path / "folder.pdf").mkdir()
    fails(capsys, ["crop", str(tmp_path / "empty.pdf")])
    fails(capsys, ["crop", str(tmp_path / "words.pdf")])
    fails(capsys, ["crop", str(tmp_path / "page.png")], "is not a PDF")
    fails(capsys, ["crop", str(tmp_path / "folder.pdf")], "is a folder")
    fails(capsys, ["restore", str(tmp_path / "words.pdf")])
    fails(capsys, ["same-scan", str(tmp_path / "empty.pdf"), str(tmp_path / "none.pdf")], "no such file")
    assert [f for f in os.listdir(tmp_path) if "safha" in f] == []
    with pytest.raises(ValueError, match="is not a PDF"):
        safha.plan(str(tmp_path / "page.png"))


def test_a_damaged_file_is_named_as_such(tmp_path, capsys):
    data = synth.book([synth.page(seed=i) for i in range(4)])
    cut = tmp_path / "cut.pdf"
    cut.write_bytes(data[: len(data) // 2])
    err = fails(capsys, ["crop", str(cut), "-q", "--set", "min_text_pages=1"], "is damaged")
    assert "left as it is" in err and not (tmp_path / "cut.safha.pdf").exists()


def test_refused_output_never_stays_on_disk(books, plans, tmp_path):
    out = tmp_path / "o.pdf"
    out.write_bytes(b"an older output")
    for change in ({"drop": [99]}, {"pages": plans["tilt"]["pages"][:3]}, {"drop": [1, 2, 3, 4, 5]}, {"split": {"7": 100.0}}):
        with pytest.raises(ApplyError):
            safha.apply_recipe(books["tilt"], dict(plans["tilt"], **change), str(out))
        assert out.read_bytes() == b"an older output"  # ... and what was there before is left as it was
        assert sorted(os.listdir(tmp_path)) == ["o.pdf"]
    with pytest.raises(ApplyError, match="3 pages, the book 5"):
        safha.apply_recipe(books["tilt"], dict(plans["tilt"], pages=plans["tilt"]["pages"][:3]), str(tmp_path / "n.pdf"))
    with pytest.raises(ApplyError, match="not a safha recipe"):
        safha.apply_recipe(books["tilt"], {"mode": "crop"}, str(tmp_path / "n.pdf"))
    assert sorted(os.listdir(tmp_path)) == ["o.pdf"]


def test_output_that_cannot_be_written(books, recipe, tmp_path, capsys):
    fails(capsys, ["apply", books["tilt"], recipe, "-o", str(tmp_path / "no" / "o.pdf")], "folder does not exist")
    (tmp_path / "dir.pdf").mkdir()
    fails(capsys, ["apply", books["tilt"], recipe, "-o", str(tmp_path / "dir.pdf")], "is a folder")
    link = tmp_path / "same.pdf"
    os.symlink(books["tilt"], link)
    fails(capsys, ["apply", books["tilt"], recipe, "-o", str(link)], "must be a new file")  # the original under another name
    assert pymupdf.open(books["tilt"]).page_count == 5
    assert sorted(os.listdir(tmp_path)) == ["dir.pdf", "same.pdf"]


def test_short_book_is_told_how_to_be_cropped(tmp_path, capsys):
    """a book of fewer text pages than ``min_text_pages`` is left alone: the message names the setting, in quiet mode too"""
    path = synth.write(tmp_path / "short.pdf", [synth.page(seed=i) for i in range(3)])
    assert main(["crop", path, "-q"]) == 0
    out = capsys.readouterr().out
    assert "few text pages (3 of 3)" in out and "nothing to do" in out and "--set min_text_pages=3" in out
    assert not (tmp_path / "short.safha.pdf").exists()
    assert main(["crop", path, "-q", "--set", "min_text_pages=3"]) == 0 and (tmp_path / "short.safha.pdf").exists()


def test_a_file_mupdf_repairs_is_written_whole_and_says_so(tmp_path, capsys):
    """a broken cross-reference table: MuPDF repairs the file on reading, and a repaired file takes no incremental
    update; the output is still checked (same pages, same image streams), and the user is told it cannot be restored"""
    data = synth.book([synth.page(seed=i, tilt=(1.0 if i == 1 else 0)) for i in range(4)])
    src = tmp_path / "noxref.pdf"
    src.write_bytes(data.replace(b"startxref", b"startxxxx"))
    assert main(["crop", str(src), "--set", "min_text_pages=1", "-j", "1"]) == 0
    assert "written whole" in capsys.readouterr().out
    out = tmp_path / "noxref.safha.pdf"
    assert pymupdf.open(out).page_count == 4
    fails(capsys, ["restore", str(out)], "no safha restore mark")


def test_starts_with_reads_in_pieces(tmp_path, monkeypatch):
    monkeypatch.setattr("safha.apply.CHUNK", 7)
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"0123456789abcdefghij")
    b.write_bytes(b"0123456789abcdefghij + an update")
    assert _starts_with(str(b), str(a), 20) and not _starts_with(str(a), str(b), 20)
    b.write_bytes(b"0123456789abcdefghiX + an update")
    assert not _starts_with(str(b), str(a), 20)
    assert not _starts_with(str(b), str(a), 10)  # the head must be the whole of the original, not a part of it
