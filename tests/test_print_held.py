"""No line of print is cut: the page image is read around the box's edge, whatever the first look took its marks for."""

from __future__ import annotations

import numpy as np
import pymupdf

import safha
import synth
from safha.engine import cut_print
from safha.measure import marks
from safha.pdf import gray, open_book, turned


def left_out(path: str, rec: dict, i: int, box_px: tuple, dpi: float = 150) -> float:
    """share of the ink inside ``box_px`` (px of the page image as scanned) that page i's shown part leaves out"""
    p = rec["pages"][i]
    doc = open_book(path, rec)
    mv = (p.get("move") or [0, 0]) if p.get("crop") else [0, 0]
    t = turned(doc, i, p.get("skew") or 0, mv[0], mv[1], p.get("shear") or 0)
    a, z = gray(t[0], 900)
    ink = np.array(a) < float(np.percentile(a, 90)) - 60
    b = [(box_px[0] * 72 / dpi + mv[0]) * z, (box_px[1] * 72 / dpi + mv[1]) * z, (box_px[2] * 72 / dpi + mv[0]) * z,
         (box_px[3] * 72 / dpi + mv[1]) * z]
    reg = np.zeros_like(ink)
    reg[int(b[1]):int(b[3]) + 1, int(b[0]):int(b[2]) + 1] = True
    R = p.get("show") if rec["mode"] == "crop" else p.get("crop")
    shown = np.ones_like(ink)
    if R is not None:
        shown[:] = False
        shown[max(0, int(R[1] * z)):max(0, int(R[3] * z)), max(0, int(R[0] * z)):max(0, int(R[2] * z))] = True
    return float((ink & reg & ~shown).sum() / max(1, (ink & reg).sum()))


def test_note_running_to_the_scan_edge_is_kept_whole(tmp_path):
    """a marginal note against the text whose words run out to the sheet's edge (the first look takes the outer words
    for the sheet's border): the box takes the whole note in"""
    pages = [synth.page(seed=i, margin=(170, 110, 60, 120)) for i in range(8)]
    pages[4], box = synth.note_page(seed=20, side="left")
    path = synth.write(tmp_path / "note.pdf", pages)
    rec = safha.plan(path)
    assert rec["mode"] == "crop"
    assert left_out(path, rec, 4, box) == 0.0
    assert "print_held" in rec["pages"][4]["flags"]
    out = tmp_path / "o.pdf"
    safha.apply_recipe(path, rec, str(out))
    assert len({(round(p.rect.width, 2), round(p.rect.height, 2)) for p in pymupdf.open(out)}) == 1  # still one size


def test_cut_print_reads_the_page_itself(tmp_path):
    im, box = synth.note_page(seed=21, side="left")
    d = pymupdf.open("pdf", synth.book([im]))
    a, z = gray(d[0], 1000)
    mk = marks(np.array(a), z, d[0].rect.width)
    mk.update(img=np.array(a), z=z)
    w, h = d[0].rect.width, d[0].rect.height
    p = {"w": w, "h": h}
    t = mk["text"]
    assert not cut_print(mk, [0.0, 0.0, w, h], p)  # the whole page: nothing is cut
    box_pt = [v * 72 / 150 for v in box]
    cut = cut_print(mk, [box_pt[0] + 30, t[1] - 10, t[2] + 10, t[3] + 10], p)  # an edge through the note
    assert cut and min(b[0] for b in cut) <= box_pt[0] + 3  # ... its outer words must be taken in
    foot = cut_print(mk, [t[0] - 10, t[1] - 10, t[2] + 10, t[3] - 40], p)  # an edge above the last lines
    assert foot and max(b[3] for b in foot) >= t[3] - 3


def test_level_trim_never_reaches_the_text(tmp_path):
    """level only, on grey paper: every page loses a thin strip (the turned page's bare corners), never its print"""
    ims = [synth.page(seed=i, tilt=(2.5 if i == 2 else 0), margin=(40, 40, 40, 40)).point(lambda v: min(v, 215)) for i in range(6)]
    path = synth.write(tmp_path / "grey.pdf", ims)
    prof = safha.load_profile(None, {"min_text_pages": 1, "gain_min": 9.0, "offcentre": 1.0, "sway": 1.0})
    rec = safha.plan(path, prof)
    assert rec["mode"] == "level" and rec["level_trim"]
    for i, p in enumerate(rec["pages"]):
        assert p["crop"] is not None
        assert left_out(path, rec, i, (40, 40, 860, 1260)) <= 0.002, f"page {i + 1}"
