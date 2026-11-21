"""A printed frame is the standard of tilt: its sides decide the turn of the page they surround, whatever the lines of
the text read."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

import safha
import synth


def framed(seed: int, lines: float = 0.0, frame: float = 0.0) -> Image.Image:
    """a page whose text lies at ``lines`` degrees inside a printed frame drawn at ``frame`` degrees"""
    im = synth.page(seed=seed, tilt=lines)
    box = Image.new("L", im.size, 255)
    ImageDraw.Draw(box).rectangle([125, 135, 775, 1155], outline=0, width=4)
    if frame:
        box = box.rotate(frame, resample=Image.BICUBIC, fillcolor=255)
    return Image.composite(im, box, box.point(lambda v: 255 if v > 128 else 0))


def planned(tmp_path, prof, name: str, **odd) -> dict:
    """five framed pages, the third with the tilts given"""
    pages = [framed(i, **(odd if i == 2 else {})) for i in range(5)]
    return safha.plan(synth.write(tmp_path / name, pages), prof)["pages"][2]


def test_lines_askew_in_a_level_frame_are_left_alone(tmp_path, prof):
    """the text was set a little askew inside a frame that stands level: turning the page by its lines would make the
    frame lean, so the frame keeps the page as scanned"""
    p = planned(tmp_path, prof, "lines.pdf", lines=0.8)
    assert not p.get("skew")
    assert {"frame_turn", "tilt_disputed"} & set(p["flags"])  # ... and listed: by its frame, or by its witnesses


def test_a_frame_askew_turns_its_page(tmp_path, prof):
    """the frame leans and the lines within it do not: the page is turned by its frame"""
    p = planned(tmp_path, prof, "frame.pdf", frame=0.8)
    assert p.get("skew") is not None and abs(abs(p["skew"]) - 0.8) <= 0.1 and "frame_turn" in p["flags"]
    assert abs(p["frame"]["after"]) <= 0.2


@pytest.mark.parametrize("lines", [1.5, -2.0])
def test_a_leaf_far_askew_inside_a_level_frame_is_not_turned(tmp_path, prof, lines):
    p = planned(tmp_path, prof, "far.pdf", lines=lines)
    assert not p.get("skew")
