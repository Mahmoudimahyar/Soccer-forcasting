"""Commentary text-quality + duplicate/correction detection (research_only)."""
from __future__ import annotations
from .normalization import normalize_text


def text_quality_status(text) -> str:
    t = normalize_text(text)
    if not t:
        return "empty"
    if len(t) < 3:
        return "too_short"
    return "ok"


def is_duplicate(a, b) -> bool:
    return normalize_text(a) == normalize_text(b) and bool(normalize_text(a))


def is_correction(text) -> bool:
    """Heuristic: commentary lines that explicitly retract/correct (synthetic-safe keywords)."""
    t = normalize_text(text).lower()
    return any(k in t for k in ("correction", "corrected", "apologies", "ignore that", "no goal -",
                                "ruled out", "scrap that"))
