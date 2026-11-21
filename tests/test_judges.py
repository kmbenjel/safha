"""The judges of the head-to-head (bench/rules.py) owe nothing to safha's measures: held here to pages of known tilt,
so that what they say of any tool's output can be trusted."""

from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import pymupdf
import pytest

import synth

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench"))
from rules import column_rule_lean, lines_lean


def image(im, px: int = 1400) -> np.ndarray:
    page = pymupdf.open("pdf", synth.book([im]))[0]
    z = px / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]


@pytest.mark.parametrize("tilt", [0.0, 0.5, -1.0, 2.0, -3.0])
def test_lines_lean_reads_a_known_tilt(tilt):
    a = image(synth.page(seed=11, tilt=tilt))
    assert abs(lines_lean(a) - tilt) <= 0.05
    assert abs(lines_lean(a, 0.05, 0.45) - tilt) <= 0.05 and abs(lines_lean(a, 0.55, 0.95) - tilt) <= 0.05


@pytest.mark.parametrize("warp", [1.0, -1.5, 2.5])
def test_lines_lean_reads_the_two_halves_of_a_warped_page_apart(warp):
    a = image(synth.page(seed=12, warp=warp))
    assert abs(lines_lean(a, 0.05, 0.45)) <= 0.05  # the upper lines are level
    assert abs(lines_lean(a, 0.55, 0.95) - warp) <= 0.1  # the lower ones lie at the warp's angle


def test_lines_lean_leaves_a_dark_bed_out_and_says_when_it_cannot_tell():
    assert abs(lines_lean(image(synth.on_bed(2, 1.2))) - 1.2) <= 0.05  # the bed's own edges are level: not read
    assert lines_lean(image(synth.page(blank=True))) is None


@pytest.mark.parametrize("tilt", [0.0, 0.6, -0.9])
def test_column_rule_lean_reads_a_known_tilt(tilt):
    assert abs(column_rule_lean(image(synth.columns(seed=3, tilt=tilt))) - tilt) <= 0.06
    assert column_rule_lean(image(synth.page(seed=3))) is None  # no rule, no reading


def test_the_bench_scripts_start_from_their_own_folder():
    """run as ``python bench/x.py``, a script finds its own folder first on the import path: no file there, or in
    scripts/, bears the name of a standard module, and the audit of the turns starts"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    names = {f[:-3] for d in ("bench", "scripts") for f in os.listdir(os.path.join(root, d)) if f.endswith(".py")}
    assert not names & set(sys.stdlib_module_names)
    r = subprocess.run([sys.executable, os.path.join(root, "bench", "rule_audit.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "RECIPES" in r.stdout
