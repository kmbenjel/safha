"""The text's own margins are a witness: a turn made for a tilt they do not show is refused, unless the page's printed
rules certify it."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

import safha
import synth

LEAN = 0.7


def askew(seed: int, rule: bool) -> Image.Image:
    """a page whose lines lean by LEAN degrees while its margins stand upright (a forme set askew); ``rule``: a running
    head and a printed rule under it, leaning with the lines"""
    im = synth.page(seed=seed)
    if rule:
        d = ImageDraw.Draw(im)
        d.text((330, 112), "CHAPTER THE THIRD", fill=0, font=synth.font(22))
        d.line([150, 146, 750, 146], fill=0, width=3)
    k = math.tan(math.radians(LEAN))
    return im.transform(im.size, Image.AFFINE, (1, 0, 0, k, 1, -k * im.width / 2), resample=Image.BICUBIC, fillcolor=250)


def book(tmp_path, name: str, rule: bool) -> str:
    return synth.write(tmp_path / name, [askew(i, rule) if i == 2 else synth.page(seed=i) for i in range(5)])


def test_margins_refuse_a_turn_the_lines_alone_ask_for(tmp_path, prof):
    r = safha.plan(book(tmp_path, "askew.pdf", rule=False), prof)
    p = r["pages"][2]
    assert not p.get("skew")  # left as scanned ...
    assert "tilt_disputed" in p["flags"] and p["edges"]  # ... and listed, with what the margins read
    assert r["summary"]["tilt_disputed"] == [3]
    assert not any(q.get("skew") for q in r["pages"])


def test_without_the_guard_the_lines_decide(tmp_path, prof):
    r = safha.plan(book(tmp_path, "askew.pdf", rule=False), prof.with_values(edge_guard=False))
    p = r["pages"][2]
    assert p.get("skew") and abs(abs(p["skew"]) - LEAN) <= 0.1


def test_a_printed_rule_certifies_the_turn(tmp_path, prof):
    r = safha.plan(book(tmp_path, "ruled.pdf", rule=True), prof)
    p = r["pages"][2]
    assert p.get("skew") and abs(abs(p["skew"]) - LEAN) <= 0.1  # lines and rule lean one way: levelled by them
    assert "tilt_disputed" not in p["flags"]
