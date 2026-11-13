"""safha: lossless crop, deskew and split for scanned book PDFs. Images are never re-encoded.

    >>> import safha
    >>> recipe = safha.plan("book.pdf")              # measure, decide: a JSON-ready dict, nothing written
    >>> safha.apply_recipe("book.pdf", recipe, "book.safha.pdf")
"""

__version__ = "0.1.0"

from .apply import ApplyError, apply_recipe, restore
from .engine import plan
from .profile import PROFILES, Profile, load_profile


def crop(src: str, dst: str, profile: "Profile | str | None" = None, jobs: int = 1, **kw) -> dict:
    """plan and apply in one call -> the recipe, with the apply report under ``applied`` (None when nothing to do)"""
    rec = plan(src, profile, jobs=jobs)
    todo = rec["mode"] in ("crop", "level") or rec.get("drop") or rec.get("split")
    rec["applied"] = apply_recipe(src, rec, dst, **kw) if todo else None
    return rec


__all__ = ["PROFILES", "ApplyError", "Profile", "__version__", "apply_recipe", "crop", "load_profile", "plan", "restore"]
