"""Golden recipes: the essential decisions of each fixture's recipe, compared with tolerances (numbers can move by a
fraction of a point between numpy/MuPDF builds; decisions may not)."""

from __future__ import annotations

import os

import safha

HERE = os.path.dirname(__file__)
FIXTURES = ["arabic-leiden.pdf", "arabic-bulaq.pdf", "latin-jbig2.pdf", "spreads.pdf", "urdu-ccitt.pdf"]
OPTIONS = {"spreads.pdf": {"direction": "rtl"}}


def essential(rec: dict) -> dict:
    return {
        "mode": rec["mode"], "size": rec.get("size"), "split": rec.get("split"), "framed": rec.get("framed"),
        "clean_margins": rec.get("clean_margins"),
        "pages": [{"kind": p["kind"], "skew": p.get("skew"), "shear": p.get("shear"), "show": p.get("show"),
                   "move": p.get("move"), "whole": "whole" in (p.get("flags") or [])} for p in rec["pages"]],
    }


def make(name: str) -> dict:
    prof = safha.load_profile(None, {"min_text_pages": 1, **OPTIONS.get(name, {})})
    return essential(safha.plan(os.path.join(HERE, "fixtures", name), prof))
