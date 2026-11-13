from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import safha
import synth

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def prof():
    """the default profile, allowing the short test books"""
    return safha.load_profile(None, {"min_text_pages": 1})


@pytest.fixture(scope="session")
def books(tmp_path_factory):
    """synthetic books with a known truth, written once per session"""
    d = tmp_path_factory.mktemp("synth")
    cases = {
        "tilt": [synth.page(seed=i, tilt=(1.0 if i == 2 else 0)) for i in range(5)],
        "level": [synth.page(seed=i) for i in range(5)],
        "warp": [synth.page(seed=i, warp=(1.5 if i == 2 else 0)) for i in range(5)],
        "frame": [synth.page(seed=i, frame=True, tilt=(0.6 if i == 2 else 0)) for i in range(5)],
        "shear": [synth.page(seed=i, frame=True, shear=(1.6 if i == 2 else 0)) for i in range(5)],
        "spread": [synth.spread(seed=i) for i in range(3)],
        "blank": [synth.page(seed=i, blank=(i == 2), stain=(i == 3)) for i in range(5)],
        "offcentre": [synth.page(seed=i, margin=((60, 160, 240, 170) if i % 2 else (240, 160, 60, 170))) for i in range(6)],
    }
    return {k: synth.write(d / f"{k}.pdf", v) for k, v in cases.items()}


@pytest.fixture(scope="session")
def plans(books, prof):
    return {k: safha.plan(v, prof) for k, v in books.items()}


def fixture(name: str) -> str:
    return os.path.join(FIX, name)
