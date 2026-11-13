"""Two columns: the whole-page measures are not trusted; a printed rule or the columns' own edges decide the turn."""

from __future__ import annotations

import numpy as np
import pymupdf
import pytest

import safha
import synth
from conftest import fixture
from safha.measure import marks
from safha.pdf import gray
from safha.tilt import column_rule, columns_tilt, edge_tilt, edges_refuse, ink_mask, rules_made_to_lean


def ink_of(im) -> np.ndarray:
    d = pymupdf.open("pdf", synth.book([im]))
    a, z = gray(d[0], 1000)
    return ink_mask(marks(a, z, d[0].rect.width)["xy"])


@pytest.fixture(scope="module")
def col_plans(tmp_path_factory, prof):
    d = tmp_path_factory.mktemp("cols")
    cases = {
        "level": [synth.columns(seed=i) for i in range(6)],
        "tilt": [synth.columns(seed=i, tilt=(0.6 if i % 2 else -0.4)) for i in range(6)],
        "gutter": [synth.columns(seed=i, rule=False, tilt=(0.5 if i == 2 else 0)) for i in range(6)],
        "bent": [synth.columns(seed=i, warp=(0.9 if i == 3 else 0)) for i in range(6)],
    }
    return {k: safha.plan(synth.write(d / f"{k}.pdf", v), prof) for k, v in cases.items()}


def test_level_columns_are_not_turned(col_plans):
    assert not col_plans["level"]["summary"]["turned"]


def test_column_rule_decides_the_turn(col_plans):
    for k, p in enumerate(col_plans["tilt"]["pages"]):
        want = -0.6 if k % 2 else 0.4  # the turn that squares the rule: minus the page's tilt
        assert p.get("skew") is not None and abs(p["skew"] - want) <= 0.08, f"page {k + 1}: {p.get('skew')}"
        assert "by_columns" in p["flags"] and p["columns"]["after"] <= 0.15


def test_columns_without_a_rule_are_read_by_their_edges(col_plans):
    r = col_plans["gutter"]
    assert [p["n"] for p in r["pages"] if p.get("skew")] == [3]
    assert abs(r["pages"][2]["skew"] + 0.5) <= 0.1


def test_bent_rule_is_no_standard(col_plans):
    assert not col_plans["bent"]["summary"]["turned"]  # a warped leaf: left as scanned


@pytest.mark.parametrize("tilt", [0.0, 0.5, -0.8, 1.4])
def test_column_rule_reads_its_lean(tilt):
    r = column_rule(ink_of(synth.columns(seed=1, tilt=tilt)))
    assert r is not None and r[1] is not None and abs(r[1] - tilt) <= 0.06


def test_column_rule_in_pieces():
    m = ink_of(synth.columns(seed=2, tilt=0.4))
    h = m.shape[0]
    m[int(0.4 * h):int(0.46 * h)] = False  # the rule prints broken
    r = column_rule(m)
    assert r is not None and r[1] is not None and abs(r[1] - 0.4) <= 0.08
    assert column_rule(ink_of(synth.page(seed=3))) is None  # an ordinary page has none


def test_columns_tilt_needs_two_columns():
    assert columns_tilt(ink_of(synth.page(seed=4, tilt=0.7))) is None
    ct = columns_tilt(ink_of(synth.columns(seed=4, rule=False, tilt=0.7)))
    assert ct is not None and all(v is not None and abs(v - 0.7) <= 0.12 for v in ct)


def test_edges_read_and_refuse():
    m = ink_of(synth.page(seed=5, tilt=0.5))
    e = [v for v in edge_tilt(m) if v is not None and v[1] >= 10]  # the edges ten lines or more stand on
    assert e and all(abs(v[0] - 0.5) <= 0.12 for v in e)  # lines set flush stand on a straight edge
    assert not edges_refuse(m, 0.5)  # a turn made for the tilt the margins show
    assert edges_refuse(m, -0.4)  # a turn made for a tilt the margins do not show
    level = ink_of(synth.page(seed=6))
    assert edges_refuse(level, 0.7)  # a level page: its margins refuse any turn
    assert not edges_refuse(None, 0.7)
    assert not edges_refuse(m, 0.9)  # margins that lean the way of the lines, by half the tilt or more, refuse nothing
    assert edges_refuse(m, 1.2)  # ... by less than half: they stand against it
    # the page as turned is read too: margins that lean there by the whole turn confirm the refusal ...
    assert edges_refuse(level, 0.7, turned=ink_of(synth.page(seed=6, tilt=-0.7)))
    # ... margins that stand upright there withdraw it (the edges of a page far off level read badly as scanned)
    assert not edges_refuse(level, 0.7, turned=level)


def test_a_rule_made_to_lean_refuses_the_turn():
    def tr(y, ang, rule):
        return (y, ang, 0.9, 0.3, 12, rule)

    t0 = [tr(40.0, 0.0, True)] + [tr(60.0 + 12 * k, 0.6, False) for k in range(8)]
    t1 = [tr(40.0, -0.6, True)] + [tr(60.0 + 12 * k, 0.0, False) for k in range(8)]
    assert rules_made_to_lean(t0, t1, 0.6) == [(40.0, 0.0, -0.6)]  # the head rule stood level: the turn makes it lean
    t0 = [tr(40.0, 0.6, True)] + t0[1:]
    t1 = [tr(40.0, 0.0, True)] + t1[1:]
    assert not rules_made_to_lean(t0, t1, 0.6)  # the rule leaned with the lines: the turn levels it


def test_dictionary_pages_follow_their_rule(prof):
    """real pages (a French-Arabic dictionary, 1896): the row profile of lines whose headword and gloss stand at
    different heights reads these pages 0.5 to 1 degree off; the rule between the columns is the truth"""
    r = safha.plan(fixture("dictionary-rule.pdf"), prof)
    turns = [p.get("skew") for p in r["pages"]]
    assert turns[0] is None  # scan p. 437: its rule stands upright (0.05 deg)
    assert turns[1] is not None and abs(turns[1] - 0.52) <= 0.1  # p. 87: the rule leans -0.52 deg
    assert turns[2] is None  # p. 341: a bent rule (its upper piece upright, its lower piece leaning) is no standard
    assert turns[3] is not None and abs(turns[3] + 0.73) <= 0.1  # p. 52: +0.73 deg
    assert turns[4] is None  # p. 230: upright (0.04 deg)
    for p in r["pages"]:  # and no page is turned on the word of the whole-page measures alone
        assert not p.get("skew") or "by_columns" in p["flags"]
