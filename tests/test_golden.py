"""Each fixture's recipe matches its golden recipe: the same decisions, numbers within a point."""

from __future__ import annotations

import json
import os

import pytest

from golden_util import FIXTURES, HERE, make


def close(a, b, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, list):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= tol
    return a == b


@pytest.mark.parametrize("name", FIXTURES)
def test_golden(name):
    with open(os.path.join(HERE, "golden", name.replace(".pdf", ".json")), encoding="utf-8") as f:
        want = json.load(f)
    got = make(name)
    assert got["mode"] == want["mode"]
    assert close(got["size"], want["size"], 1.5)
    assert (got["split"] or {}).keys() == (want["split"] or {}).keys()
    for k, (g, w) in enumerate(zip(got["pages"], want["pages"], strict=True)):
        assert g["kind"] == w["kind"], f"page {k + 1}"
        assert close(g["skew"], w["skew"], 0.05), f"page {k + 1} turn {g['skew']} vs {w['skew']}"
        assert close(g["shear"], w["shear"], 0.05), f"page {k + 1}"
        assert g["whole"] == w["whole"], f"page {k + 1}"
        assert close(g["show"], w["show"], 2.0), f"page {k + 1} shown part {g['show']} vs {w['show']}"
