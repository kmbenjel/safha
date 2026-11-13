"""The command line and the profiles."""

from __future__ import annotations

import json

import pytest

import safha
from safha.cli import main


def test_crop_inspect_restore(books, tmp_path, capsys):
    out, rec = tmp_path / "o.pdf", tmp_path / "r.json"
    assert main(["crop", books["tilt"], "-o", str(out), "--recipe", str(rec), "--set", "min_text_pages=1", "-q"]) == 0
    assert out.exists() and json.loads(rec.read_text())["mode"] == "crop"
    assert main(["inspect", str(rec)]) == 0
    assert "turn" in capsys.readouterr().out
    assert main(["restore", str(out), "-o", str(tmp_path / "back.pdf")]) == 0


def test_plan_apply_sheet(books, tmp_path):
    rec = tmp_path / "r.json"
    assert main(["plan", books["blank"], "-o", str(rec), "--set", "min_text_pages=1", "-q", "--pretty"]) == 0
    assert main(["apply", books["blank"], str(rec), "-o", str(tmp_path / "o.pdf")]) == 0
    assert main(["sheet", books["blank"], "--recipe", str(rec), "-o", str(tmp_path / "s.jpg")]) == 0
    assert (tmp_path / "s.jpg").stat().st_size > 10_000
    assert main(["sheet", books["blank"], "--recipe", str(rec), "--html", str(tmp_path / "rev")]) == 0
    assert (tmp_path / "rev" / "index.html").exists()
    assert main(["sheet", books["blank"], "--recipe", str(rec), "--cards", str(tmp_path / "cards")]) == 0
    first = json.loads((tmp_path / "cards" / "cards.jsonl").read_text().splitlines()[0])
    assert first["id"] and len(first["images"]) == 2


def test_drop_blank(books, tmp_path, capsys):
    out = tmp_path / "d.pdf"
    assert main(["drop", books["blank"], "--pages", "3", "-o", str(out)]) == 0


def test_drop_refuses_text_page(books, tmp_path):
    with pytest.raises(SystemExit):
        main(["drop", books["blank"], "--pages", "1", "-o", str(tmp_path / "d.pdf")])


def test_errors_are_plain(books, tmp_path, capsys):
    assert main(["crop", str(tmp_path / "missing.pdf")]) == 2
    assert "no such file" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["crop", books["tilt"], "--set", "nonsense"])
    with pytest.raises(SystemExit):
        main(["crop", books["tilt"], "--set", "nonsense=1"])


def test_profiles(tmp_path, capsys):
    assert main(["profiles", "-v"]) == 0
    assert "eink" in capsys.readouterr().out
    p = tmp_path / "mine.toml"
    p.write_text('base = "eink"\nmargin = 0.04\nskew_min = 0.3\n')
    prof = safha.load_profile(str(p))
    assert prof.name == "mine" and prof.margin == 0.04 and prof.always and prof.skew_min == 0.3
    assert safha.load_profile(None, {"margin": "0.1"}).margin == 0.1
    with pytest.raises(ValueError):
        safha.load_profile(None, {"nope": 1})
    with pytest.raises(ValueError):
        safha.load_profile("no-such-profile")


def test_same_scan(books, tmp_path, capsys):
    out = tmp_path / "o.pdf"
    assert main(["crop", books["tilt"], "-o", str(out), "--set", "min_text_pages=1", "-q"]) == 0
    assert main(["same-scan", books["tilt"], str(out)]) == 0
    assert main(["same-scan", books["tilt"], books["level"]]) == 1


def test_version_and_help(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert main([]) == 0


def test_bench(books, prof, tmp_path, capsys):
    from safha.bench import bench

    rows = bench([books["tilt"], books["level"]], prof, out=str(tmp_path / "b.json"))
    assert len(rows) == 2 and all("error" not in r for r in rows)
    assert (tmp_path / "b.md").read_text().startswith("# safha bench")
    assert rows[0]["filters"] == rows[0]["filters_out"]


def test_demo(tmp_path, capsys):
    assert main(["demo", "-o", str(tmp_path / "demo"), "-j", "2"]) == 0
    out = capsys.readouterr().out
    assert "sample-spreads" in out and (tmp_path / "demo" / "sample-latin.safha.pdf").exists()
