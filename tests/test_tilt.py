"""Tilt: turned only when two measures agree; never a warped page; a frame or a sheared print levelled."""

from __future__ import annotations

import pymupdf
import pytest

import safha
import synth
from safha.measure import marks
from safha.pdf import gray
from safha.tilt import frame_lean, line_tracks, lines_read, skew_of, tracks_tilt, two_angles


def page_skew(path: str, i: int) -> float:
    """the raw whole-page angle of page i of a PDF, by the ink-shear measure"""
    d = pymupdf.open(path)
    a, z = gray(d[i], 1000)
    return skew_of(marks(a, z, d[i].rect.width)["xy"], raw=True)[0]


def test_tilted_page_is_turned_level(plans):
    r = plans["tilt"]
    p = r["pages"][2]
    assert p.get("skew") is not None and abs(abs(p["skew"]) - 1.0) <= 0.06
    assert p["after"][0] <= 0.15 and p["after"][1] <= 0.2
    assert [q["n"] for q in r["pages"] if q.get("skew")] == [3]  # the level pages are not touched


def test_turned_output_reads_level(books, plans, tmp_path):
    out = tmp_path / "t.pdf"
    safha.apply_recipe(books["tilt"], plans["tilt"], str(out))
    assert abs(page_skew(books["tilt"], 2)) >= 0.8
    assert abs(page_skew(str(out), 2)) <= 0.15


def test_level_book_has_no_turn(plans):
    assert not plans["level"]["summary"]["turned"]


def test_warped_page_is_never_turned(plans):
    p = plans["warp"]["pages"][2]
    assert not p.get("skew")


def test_two_angles_rule():
    lines = [(10.0 * k, 0.0, -0.6) for k in range(5)] + [(60.0 + 10 * k, 0.6, 0.0) for k in range(5)]
    assert two_angles(lines)  # half the lines made to lean 0.6 deg
    assert not two_angles([(10.0 * k, 0.6, 0.0) for k in range(10)])  # a uniform tilt levelled


def test_lines_followed_across_the_page():
    im = synth.page(seed=3, tilt=0.8)
    d = pymupdf.open("pdf", synth.book([im]))
    a, z = gray(d[0], 1000)
    mk = marks(a, z, d[0].rect.width)
    t = tracks_tilt(line_tracks(a, mk["paper"], mk["text"], z))
    assert t is not None and abs(abs(t[0]) - 0.8) <= 0.1
    L = lines_read(line_tracks(a, mk["paper"], mk["text"], z), line_tracks(a, mk["paper"], mk["text"], z), 0.0)
    assert L and len(L) >= 5


def test_frame_lean_reads_the_frame():
    im = synth.page(seed=1, frame=True, tilt=0.7)
    d = pymupdf.open("pdf", synth.book([im]))
    a, z = gray(d[0], 1000)
    mk = marks(a, z, d[0].rect.width)
    mk.update(img=a, z=z)
    fl = frame_lean(mk)
    assert fl is not None and abs(abs(fl) - 0.7) <= 0.1


def test_framed_tilted_page_turned(plans):
    p = plans["frame"]["pages"][2]
    assert p.get("skew") and abs(abs(p["skew"]) - 0.6) <= 0.06


def test_sheared_print_is_sheared_level(plans):
    p = plans["shear"]["pages"][2]
    assert p.get("shear") is not None and abs(abs(p["shear"]) - 1.6) <= 0.06
    assert "frame_shear" in p["flags"]
    assert not any(q.get("shear") for k, q in enumerate(plans["shear"]["pages"]) if k != 2)


def test_crop_only_profile_never_turns(books):
    r = safha.plan(books["tilt"], safha.load_profile("crop-only", {"min_text_pages": 1}))
    assert not r["summary"]["turned"]


@pytest.mark.parametrize("angle", [-2.0, 3.5])
def test_skew_of_reads_known_angles(angle):
    im = synth.page(seed=5, tilt=angle)
    d = pymupdf.open("pdf", synth.book([im]))
    a, z = gray(d[0], 1000)
    ang, gain = skew_of(marks(a, z, d[0].rect.width)["xy"])
    assert gain > 1.02
    assert abs(abs(ang) - abs(angle)) <= 0.1


def test_baseline_tilt_certifies_by_the_lines_themselves():
    from safha.tilt import baseline_tilt

    for tilt in (0.0, 0.6, -1.0):
        d = pymupdf.open("pdf", synth.book([synth.page(seed=7, tilt=tilt)]))
        a, z = gray(d[0], 1000)
        b = baseline_tilt(a, marks(a, z, d[0].rect.width)["paper"])
        assert b is not None and abs(abs(b) - abs(tilt)) <= 0.15, f"{tilt}: {b}"
    blank = pymupdf.open("pdf", synth.book([synth.page(blank=True)]))
    a, z = gray(blank[0], 1000)
    assert baseline_tilt(a, 250.0) is None  # no lines to read


def test_print_certifies_a_turn_its_lines_cannot_judge():
    """an index under a head rule: the entries' own lines read at every angle, the rule is the print's straight line"""
    from safha.tilt import print_turn

    def tr(y, ang, rule=False):
        return (y, ang, 0.9, 0.3, 12, rule)

    scattered = [0.6, 1.3, 0.1, 1.1, -0.2, 0.9, 1.6, 0.2]  # lines that follow no common tilt
    t0 = [tr(40.0, 0.6, True)] + [tr(60.0 + 12 * k, v) for k, v in enumerate(scattered)]
    t1 = [tr(40.0, 0.0, True)] + [tr(60.0 + 12 * k, v - 0.6) for k, v in enumerate(scattered)]
    ok, rules = print_turn(t0, t1, 0.6)
    assert ok and rules == [(40.0, 0.6, 0.0)]  # the rule stands level once turned: the print certifies the turn
    assert not print_turn(t0, t1, 0.2)[0]  # a turn that leaves the rule leaning certifies nothing
    steady0 = [tr(40.0, 0.6, True)] + [tr(60.0 + 12 * k, 0.6) for k in range(8)]
    steady1 = [tr(40.0, 0.0, True)] + [tr(60.0 + 12 * k, 0.0) for k in range(8)]
    assert not print_turn(steady0, steady1, 0.6)[0]  # lines that read steadily speak for themselves
    assert not print_turn([t for t in t0 if not t[5]], [t for t in t1 if not t[5]], 0.6)[0]  # no rule, no certificate
