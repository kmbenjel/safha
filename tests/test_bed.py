"""A book scanned on a dark scanner bed: a leaf lying askew is turned level and cropped like its neighbours. The blank
wedge a turn leaves at the page's edge must not hide the bed behind it."""

from __future__ import annotations

import numpy as np
import pymupdf

import safha
import synth
from safha.pdf import beyond_sheet, gray

TILTS = {3: 1.2, 5: -0.9}


def bed_share(page: pymupdf.Page) -> float:
    """the share of the shown page's outermost strip (3 % on every side, where no letter stands) that is as dark as
    the scanner bed"""
    a, _ = gray(page, 300)
    a = np.array(a)
    h, w = a.shape
    ring = np.ones_like(a, bool)
    ring[int(0.03 * h):int(0.97 * h), int(0.03 * w):int(0.97 * w)] = False
    return float((a[ring] < 80).mean())


def test_a_leaf_askew_on_the_bed_is_cropped_like_its_neighbours(tmp_path, prof):
    path = synth.write(tmp_path / "bed.pdf", [synth.on_bed(i, TILTS.get(i, 0.0)) for i in range(8)])
    assert bed_share(pymupdf.open(path)[3]) > 0.9  # the scan: a dark bed all round the leaf
    rec = safha.plan(path, prof)
    assert rec["mode"] == "crop" and "scanner bands" in rec["reasons"]
    assert rec["summary"]["turned"] == [4, 6] and not rec["summary"]["whole"]
    for k, turn in ((3, -1.2), (5, 0.9)):
        assert abs(rec["pages"][k]["skew"] - turn) <= 0.1
    widths = [p["crop"][2] - p["crop"][0] for p in rec["pages"]]
    assert max(widths) - min(widths) <= 0.5  # one box, the turned pages too
    for p in rec["pages"]:  # every page's text in the middle of its box, the bed outside it
        t, c = p["text"], p["crop"]
        assert abs((t[0] - c[0]) - (c[2] - t[2])) <= 0.03 * (c[2] - c[0]), f"page {p['n']}"
    out = tmp_path / "o.pdf"
    safha.apply_recipe(path, rec, str(out))
    for pg in pymupdf.open(out):
        assert bed_share(pg) == 0.0, f"page {pg.number + 1} still shows the scanner bed"


def test_a_level_leaf_on_the_bed_reads_the_same_turned_or_not(tmp_path, prof):
    """the recipe carries no trace of the helper that tells the second check where the bed lies"""
    path = synth.write(tmp_path / "bed.pdf", [synth.on_bed(i, TILTS.get(i, 0.0)) for i in range(6)])
    rec = safha.plan(path, prof)
    assert all("bed" not in p for p in rec["pages"])
    a = [p["allowed"] for p in rec["pages"]]
    for k in (3, 5):  # the turned leaf's bounds are its own edges, as on the level pages (within the leaf's own tilt)
        assert all(abs(u - v) <= 3.0 for u, v in zip(a[k], a[0])), f"page {k + 1}: {a[k]} vs {a[0]}"


def test_beyond_sheet():
    # a sheet 100 x 200 pt turned a little: its corners in the view, one pixel per point
    c = [(3.0, -2.0), (103.0, 1.0), (97.0, 201.0), (-3.0, 198.0)]
    assert beyond_sheet((200, 100), c, 1.0, [False] * 4) is None
    top = beyond_sheet((200, 100), c, 1.0, [False, True, False, False])
    assert top is not None and top[0, 99] and not top[0, 2] and not top[5, 50] and not top[199].any()
    left = beyond_sheet((200, 100), c, 1.0, [True, False, False, False])
    assert left is not None and left[2, 0] and not left[199, 0] and not left[:, 10].any()
    every = beyond_sheet((200, 100), c, 1.0, [True] * 4)
    assert every is not None and 0 < every.mean() < 0.05 and not every[20:180, 10:90].any()
    level = [(0.0, 0.0), (100.0, 0.0), (100.0, 200.0), (0.0, 200.0)]
    assert beyond_sheet((200, 100), level, 1.0, [True] * 4) is None  # a page as scanned: nothing lies beyond it


def test_a_blank_leaf_on_the_bed_is_blank(tmp_path, capsys):
    """the bed round a blank leaf is no ink: ``drop --blank`` finds the leaf, and the guard lets it go"""
    from safha.cli import main
    from safha.pages import ink_share

    ims = [synth.on_bed(i, blank=(i == 1), tilt=(0.8 if i == 1 else 0.0), border=(90, 80, 85, 95)) for i in range(6)]
    path = synth.write(tmp_path / "bed.pdf", ims)
    d = pymupdf.open(path)
    assert ink_share(d[1]) < 0.001 < ink_share(d[0])
    out = tmp_path / "d.pdf"
    assert main(["drop", path, "--blank", "-o", str(out)]) == 0
    assert "dropped p. 2:" in capsys.readouterr().out and pymupdf.open(out).page_count == 5
