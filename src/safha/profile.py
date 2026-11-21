"""Profiles: every threshold of the method in one place.

The default profile, ``warraq``, is the behaviour tuned page by page on a 16,700-volume library of scanned books: crop a
book only when it pays (the text grows by 15 % or more on a phone, or the scan has a flaw worth fixing), keep 8 % of the
text width as a margin, never turn a page unless two independent measures agree. Other profiles change a few values;
any value can also be set from the command line (``--set margin=0.05``) or a JSON/TOML file (``--profile my.toml``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Profile:
    name: str = "warraq"
    # -- measuring -------------------------------------------------------------------------------------------------
    first_px: int = 500  # width (px) of the page render used by the first look
    check_px: int = 1000  # width (px) of the second look (tilt check, nothing cut)
    # -- deciding a crop ---------------------------------------------------------------------------------------------
    gain_min: float = 1.15  # crop a book for size alone when its text grows at least this much on a phone
    offcentre: float = 0.02  # ... or its text is this far off-centre (share of the page width, median page)
    sway: float = 0.015  # ... or its text sways this much from page to page (interquartile range of its centre)
    stained: float = 0.05  # ... or stains are left out on this share of the text pages
    always: bool = False  # crop every book that fits one box, even a well-made scan the crop changes little
    max_whole: float = 0.05  # share of text pages allowed to stay uncropped (their content wider than the box)
    min_text_pages: int = 5  # a file with fewer text pages (or text on fewer than half its pages) is left as it is
    width_quantiles: tuple[float, ...] = (0.95, 0.98, 1.0)  # the box width: content width of 95 % of pages, else ...
    # -- margins (shares of the text width / height) -------------------------------------------------------------
    margin: float = 0.08  # side margin of an ordinary book
    margin_v: float = 0.05  # top and bottom margin
    framed_margin: float = 0.02  # a book whose text stands in a printed frame keeps a hairline outside it
    clean_margin: float = 0.06  # a book with nothing printed in its side margins: text block + this on every side
    min_margin_pt: float = 14.0  # never less than this (pt on a page 420 pt wide)
    magnify_max: float = 1.05  # a page smaller than the book's box may be drawn up to 5 % larger
    # -- tilt ---------------------------------------------------------------------------------------------------------
    deskew: bool = True
    skew_min: float = 0.2  # degrees: no turn under it (the eye sees 0.25 deg on a full line)
    level: float = 0.15  # a turned page must read level within this by the ink-shear measure ...
    img_level: float = 0.2  # ... and within this by the image-projection measure
    curved: float = 0.25  # a slightly curved page is kept turned when both read <= this and <= a third of its tilt
    skew_max: float = 8.0  # degrees: the widest tilt looked for
    frame_side_max: float = 0.35  # a printed frame whose sides lean more than this is turned by the frame
    shear_min: float = 1.25  # a frame whose rules lean this much against its upright sides is sheared level ...
    shear_max: float = 3.0  # ... up to this (beyond it: a misreading, left alone)
    two_angle_guard: bool = True  # never turn a page whose lines lie at two angles (warped leaf)
    edge_guard: bool = True  # never turn a page against its text's own margins (unless its printed rules certify the turn)
    # -- pages ---------------------------------------------------------------------------------------------------------
    split: str = "auto"  # split two-page spreads: auto | always | never
    direction: str = "auto"  # reading order of a split spread: ltr | rtl | auto (from the text layer, else ltr)
    covers: bool = True  # find a cover photographed on the scanner bed and show it alone

    def with_values(self, **kw: Any) -> Profile:
        known = {f.name: f for f in fields(self)}
        out: dict[str, Any] = {}
        for k, v in kw.items():
            if k not in known:
                raise ValueError(f"unknown profile setting {k!r}; known: {', '.join(sorted(known))}")
            try:
                out[k] = _coerce(known[k].type, v)
            except (TypeError, ValueError):
                raise ValueError(f"profile setting {k} expects {_KIND.get(str(known[k].type), 'a value')}, got {v!r}") from None
            if k in CHOICES and out[k] not in CHOICES[k]:
                raise ValueError(f"profile setting {k} is one of {', '.join(CHOICES[k])}; got {v!r}")
        return replace(self, **out)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["width_quantiles"] = list(self.width_quantiles)
        return d

    def diff(self) -> dict[str, Any]:
        """the settings that differ from the default profile"""
        base = Profile().to_dict()
        return {k: v for k, v in self.to_dict().items() if k != "name" and base.get(k) != v}


CHOICES = {"split": ("auto", "always", "never"), "direction": ("auto", "ltr", "rtl")}
_KIND = {"bool": "true or false", "int": "a whole number", "float": "a number", "str": "a word",
         "tuple[float, ...]": "numbers separated by commas"}
_TRUE, _FALSE = ("1", "true", "yes", "on"), ("0", "false", "no", "off")


def _coerce(typ: Any, v: Any) -> Any:
    """a setting's value as its field's type; a value of another kind raises (TypeError, ValueError)"""
    t = str(typ)
    if isinstance(v, str):
        w = v.strip()
        if t == "bool":
            if w.lower() not in _TRUE + _FALSE:
                raise ValueError(v)
            return w.lower() in _TRUE
        if t == "int":
            return int(w)
        if t == "float":
            return float(w)
        if t.startswith("tuple"):
            return tuple(float(x) for x in w.split(","))
        return w
    if t.startswith("tuple"):
        return tuple(float(x) for x in v)
    if t == "bool":
        if not isinstance(v, bool):
            raise TypeError(v)
        return v
    if t == "int":
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(v)
        return v
    if t == "float":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TypeError(v)
        return float(v)
    if not isinstance(v, str):
        raise TypeError(v)
    return v


PROFILES: dict[str, Profile] = {
    "warraq": Profile(),
    # crop every book that fits one box, even a clean scan: the most reading area on a small screen
    "reader": Profile(name="reader", always=True, margin=0.05, margin_v=0.035, clean_margin=0.04),
    # a large screen or print: crop only, never turn a page
    "crop-only": Profile(name="crop-only", deskew=False),
    # e-ink readers (Kindle, Kobo, reMarkable): tight margins, every book cropped
    "eink": Profile(name="eink", always=True, margin=0.03, margin_v=0.025, clean_margin=0.03, framed_margin=0.01),
}


def load_profile(spec: str | None, overrides: dict[str, Any] | None = None) -> Profile:
    """a profile by name (``warraq``, ``reader``, ``eink``, ``crop-only``) or from a JSON/TOML file, then overrides"""
    if not spec:
        prof = PROFILES["warraq"]
    elif spec in PROFILES:
        prof = PROFILES[spec]
    else:
        p = Path(spec)
        if not p.exists():
            raise ValueError(f"no profile named {spec!r} and no such file; built-in: {', '.join(PROFILES)}")
        try:
            if p.suffix == ".toml":
                try:
                    import tomllib
                except ImportError:  # Python 3.10
                    import tomli as tomllib  # type: ignore[no-redef]
                data = tomllib.loads(p.read_text(encoding="utf-8"))
            else:
                data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:  # (TOML and JSON syntax errors are both ValueErrors)
            raise ValueError(f"profile file {spec} cannot be read: {e}") from None
        if not isinstance(data, dict):
            raise ValueError(f"profile file {spec} must hold settings (name = value), not {type(data).__name__}")
        base_name = data.pop("base", "warraq")
        if base_name not in PROFILES:
            raise ValueError(f"profile file {spec}: base = {base_name!r} is no built-in profile ({', '.join(PROFILES)})")
        prof = PROFILES[base_name].with_values(name=str(data.pop("name", p.stem)), **data)
    return prof.with_values(**overrides) if overrides else prof
