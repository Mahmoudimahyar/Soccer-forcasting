"""SoccerNet match-identity mapping + event-taxonomy reconciliation (Phase 3). Provider-neutral,
deterministic, audit-logged. SoccerNet-Echoes and SoccerNet labels share the SAME game-path keys, so the
primary join is EXACT; normalized + override paths handle edge cases with explicit confidence.
research_only / historical_weak_supervision_only.
"""
from __future__ import annotations

from pathlib import Path
import yaml

# Official SoccerNet action-spotting (Labels-v2.json) 17 classes -> canonical taxonomy.
SOCCERNET_TO_CANONICAL = {
    "Goal": ("goal", "supported", 1.0),
    "Penalty": ("penalty_awarded", "supported", 0.9),
    "Yellow card": ("yellow_card", "supported", 1.0),
    "Red card": ("red_card", "supported", 1.0),
    "Yellow->red card": ("second_yellow", "supported", 1.0),
    "Substitution": ("substitution", "supported", 1.0),
    "Corner": ("corner", "supported", 1.0),
    "Offside": ("offside", "supported", 1.0),
    "Foul": ("foul", "supported", 1.0),
    "Shots on target": ("shot_on_target", "supported", 0.9),
    "Shots off target": ("shot", "supported", 0.8),
    "Kick-off": ("kickoff", "supported", 0.9),
    # present in SoccerNet but no precise canonical event -> 'other'
    "Throw-in": ("other", "mapped_to_other", 0.5),
    "Clearance": ("other", "mapped_to_other", 0.5),
    "Ball out of play": ("other", "mapped_to_other", 0.5),
    "Indirect free-kick": ("other", "mapped_to_other", 0.5),
    "Direct free-kick": ("other", "mapped_to_other", 0.5),
}
# canonical classes with NO SoccerNet-v2 source -> unsupported (cannot be derived from these labels)
CANONICAL_UNSUPPORTED = {"own_goal", "penalty_scored", "penalty_missed", "VAR_review",
                         "VAR_goal_cancelled", "halftime", "fulltime"}


def normalize_game_id(g: str) -> str:
    return "/".join(p.strip().lower().replace(" ", "_") for p in str(g).replace("\\", "/").split("/") if p.strip())


def map_to_canonical_event(soccernet_label: str):
    """Return (canonical_event, support_status, confidence)."""
    return SOCCERNET_TO_CANONICAL.get(soccernet_label, ("unknown", "unsupported_source_event", 0.0))


def load_overrides(path) -> dict:
    if not Path(path).exists():
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {o["echoes_game"]: o for o in data.get("overrides", [])}


def map_games(echoes_ids, label_ids, overrides=None) -> dict:
    """Deterministic game mapping with confidence + status. Returns {echoes_id: {label_id, status,
    confidence}}. Statuses: exact / normalized / override / ambiguous / missing."""
    overrides = overrides or {}
    label_exact = set(label_ids)
    norm_index = {}
    for lid in label_ids:
        norm_index.setdefault(normalize_game_id(lid), []).append(lid)
    out = {}
    for eid in echoes_ids:
        if eid in overrides:
            out[eid] = {"label_id": overrides[eid]["label_game"], "status": "override",
                        "confidence": float(overrides[eid].get("confidence", 1.0))}
            continue
        if eid in label_exact:
            out[eid] = {"label_id": eid, "status": "exact", "confidence": 1.0}
            continue
        cands = norm_index.get(normalize_game_id(eid), [])
        if len(cands) == 1:
            out[eid] = {"label_id": cands[0], "status": "normalized", "confidence": 0.9}
        elif len(cands) > 1:
            out[eid] = {"label_id": None, "status": "ambiguous", "confidence": 0.0, "candidates": cands}
        else:
            out[eid] = {"label_id": None, "status": "missing", "confidence": 0.0}
    return out


def detect_collisions(label_ids) -> list:
    """Distinct label IDs that normalize to the same key (would cause ambiguous joins)."""
    norm = {}
    for lid in label_ids:
        norm.setdefault(normalize_game_id(lid), []).append(lid)
    return [v for v in norm.values() if len(v) > 1]
