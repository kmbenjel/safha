"""DECIDE on measured pages given as plain records: which pages have a say in whether one box fits the book."""

from __future__ import annotations

import safha
from safha.decide import decide

PROF = safha.load_profile(None, {"min_text_pages": 1})


def page(n: int, k: float = 1.0, wide: bool = False) -> dict:
    """a measured text page 400 x 600 pt (times ``k``): a text block with two marks of print in its left margin (a
    book that prints there: its box is never grown round a page that holds more); ``wide``: a table across the page"""
    text = [8.0, 80.0, 392.0, 520.0] if wide else [80.0 * k, 80.0 * k, 320.0 * k, 520.0 * k]
    margin = [] if wide else [[50.0 * k, 300.0 * k, 58.0 * k, 310.0 * k], [50.0 * k, 316.0 * k, 58.0 * k, 326.0 * k]]
    return {"n": n, "kind": "text", "w": 400.0 * k, "h": 600.0 * k, "flags": [], "paper": 250.0, "text": text, "core": list(text),
            "box": list(text) if wide else [50.0 * k, 80.0 * k, 320.0 * k, 520.0 * k], "margin": margin,
            "allowed": [0.0, 0.0, 400.0 * k, 600.0 * k]}


def test_a_sheet_of_another_size_has_no_say_in_whether_one_box_fits():
    """two plates filmed at twice the size among twenty pages: they are shown whole, and the book is cropped"""
    pages = [page(i + 1, 2.0 if i in (6, 13) else 1.0) for i in range(22)]
    out = decide(pages, PROF)
    assert not out["clean_margins"] and out["decision"] == "crop"
    assert out["whole"] == [6, 13] and out["other_size"] == [6, 13]
    assert all(p["crop"] is None for p in (pages[6], pages[13])) and all(pages[i]["crop"] for i in (0, 5, 7, 21))


def test_pages_of_the_book_s_own_size_that_do_not_fit_still_stop_the_crop():
    """the same count of misfits on sheets of the book's own size: no one box fits, the book is not cropped"""
    pages = [page(i + 1, wide=i in (6, 13)) for i in range(22)]
    out = decide(pages, PROF)
    assert out["decision"] == "skip" and "2 pages do not fit one box" in out["why"] and out["other_size"] == []
    pages = [page(i + 1, wide=i == 6) for i in range(22)]
    out = decide(pages, PROF)
    assert out["decision"] == "crop" and out["whole"] == [6]  # one page in twenty-two: within the 5 % allowed
