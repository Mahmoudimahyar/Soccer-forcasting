"""Deterministic provider-neutral normalization helpers (Phase 3). No invented IDs/fields."""
from __future__ import annotations

import hashlib

# Common provider period strings -> canonical period.
_PERIOD_ALIASES = {
    "1h": "first_half", "first half": "first_half", "1st_half": "first_half", "1": "first_half",
    "2h": "second_half", "second half": "second_half", "2nd_half": "second_half", "2": "second_half",
    "et1": "et_first", "extra time first": "et_first", "et2": "et_second", "extra time second": "et_second",
    "pen": "shootout", "penalties": "shootout", "shootout": "shootout", "pso": "shootout",
    "pre": "pre", "post": "post", "ft": "post", "ht": "first_half",
}


def normalize_period(raw) -> str:
    return _PERIOD_ALIASES.get(str(raw).strip().lower(), "unknown")


def source_hash(raw_bytes_or_str) -> str:
    b = raw_bytes_or_str if isinstance(raw_bytes_or_str, bytes) else str(raw_bytes_or_str).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def canonical_match_id(competition: str, season: str, home_team_id: str, away_team_id: str, date_str: str) -> str:
    """Deterministic provider-neutral match id. Uses provider team IDs verbatim (never invents)."""
    parts = [str(competition).strip().lower(), str(season).strip(), str(date_str).strip(),
             str(home_team_id).strip(), str(away_team_id).strip()]
    return "/".join(p.replace(" ", "_") for p in parts)


def preserve_player_id(raw_player_id):
    """Return the provider's player id verbatim or None — NEVER synthesize an id."""
    if raw_player_id in (None, "", "null"):
        return None
    return str(raw_player_id)
