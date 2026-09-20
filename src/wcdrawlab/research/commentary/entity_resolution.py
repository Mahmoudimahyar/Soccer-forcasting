"""Entity (team/player) resolution with explicit confidence (research_only). Conservative; no guessing."""
from __future__ import annotations
from difflib import SequenceMatcher


def _norm(s):
    return "".join(c for c in str(s).lower() if c.isalnum() or c == " ").strip() if s else ""


def resolve_entity(raw_name, candidates) -> tuple:
    """Return (best_canonical_or_None, confidence in [0,1]). Empty/no-candidate -> (None, 0.0)."""
    if not raw_name or not candidates:
        return (None, 0.0)
    rn = _norm(raw_name)
    best, score = None, 0.0
    for c in candidates:
        s = SequenceMatcher(None, rn, _norm(c)).ratio()
        if s > score:
            best, score = c, s
    return (best if score >= 0.6 else None, round(float(score), 3))
