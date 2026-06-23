"""Frozen prospective prediction + post-match scoring (V1.5 operations).

Builds a research-only frozen-M2 in-play/pre-match prediction record (with a B1/Elo anchor and full
provenance) and scores it once the match is FINISHED. Enforces the leakage rule: the event source
timestamp behind a decision must be no later than the decision timestamp. Never updates the model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_STATE_FIELDS = ["elo_delta_home", "decision_minute", "score_home", "score_away",
                         "red_home", "red_away"]
SCHEMA_VERSION = "prospective_v1"


class LeakageError(RuntimeError):
    pass


def assert_no_leakage(event_source_ts, decision_ts):
    """Decision may only use events whose source timestamp is <= the decision timestamp."""
    if event_source_ts is not None and decision_ts is not None and str(event_source_ts) > str(decision_ts):
        raise LeakageError(f"event_source_ts {event_source_ts} > decision_ts {decision_ts} (future info)")


def data_completeness(state: dict) -> float:
    present = sum(1 for k in REQUIRED_STATE_FIELDS if state.get(k) is not None
                 and not (isinstance(state.get(k), float) and np.isnan(state.get(k))))
    return round(present / len(REQUIRED_STATE_FIELDS), 4)


def build_prediction_record(*, match_id, kickoff_utc, phase, capture_window, decision_minute,
                            decision_timestamp, retrieval_timestamp, event_source_timestamp,
                            state: dict, frozen_model, anchor_probs, source_hashes: dict,
                            model_version="v2") -> dict:
    assert_no_leakage(event_source_timestamp, decision_timestamp)
    row = pd.DataFrame([{k: state.get(k) for k in REQUIRED_STATE_FIELDS}])
    p = frozen_model.predict_wld(row)[0]
    a = list(anchor_probs)
    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": getattr(frozen_model, "model_id", "m2_frozen"),
        "model_version": model_version,
        "approval_status": "research_only",
        "not_runtime_approved": True,
        "match_id": match_id, "kickoff_utc": kickoff_utc,
        "phase": phase, "capture_window": capture_window, "decision_minute": decision_minute,
        "decision_timestamp": decision_timestamp, "retrieval_timestamp": retrieval_timestamp,
        "event_source_timestamp": event_source_timestamp,
        "p_home_win": float(p[0]), "p_draw": float(p[1]), "p_away_win": float(p[2]),
        "anchor_p_home": float(a[0]), "anchor_p_draw": float(a[1]), "anchor_p_away": float(a[2]),
        "state": {k: state.get(k) for k in REQUIRED_STATE_FIELDS},
        "source_hashes": source_hashes, "data_completeness": data_completeness(state),
    }


def state_from_apifootball(fixture_item: dict, events: list, elo_delta_home: float,
                           decision_minute: int) -> dict:
    """Construct an in-play state dict from an API-Football /fixtures item + /fixtures/events list.
    Red cards counted per side from events; score from current goals. decision_minute is the checkpoint."""
    teams = fixture_item.get("teams", {})
    home_id = (teams.get("home") or {}).get("id")
    goals = fixture_item.get("goals", {})
    reds = {"home": 0, "away": 0}
    for e in events or []:
        if e.get("type") == "Card" and e.get("detail") in ("Red Card", "Second Yellow card", "Second Yellow"):
            side = "home" if (e.get("team", {}).get("id") == home_id) else "away"
            reds[side] += 1
    return {
        "elo_delta_home": float(elo_delta_home), "decision_minute": int(decision_minute),
        "score_home": int(goals.get("home") or 0), "score_away": int(goals.get("away") or 0),
        "red_home": reds["home"], "red_away": reds["away"],
    }


def _rps(p, y):  # p=(h,d,a), y in {0,1,2}; ordered ranked probability score
    cp = np.cumsum(p); cy = np.cumsum([1 if i == y else 0 for i in range(3)])
    return float(np.sum((cp - cy) ** 2) / 2.0)


def score_record(record: dict, *, final_wld: str, final_score_home: int, final_score_away: int,
                 result_event_time, result_retrieval_time) -> dict:
    """Score a frozen prediction against a FINISHED result. Pure scoring; never mutates the model."""
    y = {"H": 0, "D": 1, "A": 2}[final_wld]
    p = np.array([record["p_home_win"], record["p_draw"], record["p_away_win"]], dtype=float)
    a = np.array([record["anchor_p_home"], record["anchor_p_draw"], record["anchor_p_away"]], dtype=float)
    logloss = float(-np.log(max(p[y], 1e-12)))
    draw_brier = float((p[1] - (1 if y == 1 else 0)) ** 2)
    return {
        "ledger_key": record.get("ledger_key"), "match_id": record["match_id"],
        "phase": record["phase"], "capture_window": record.get("capture_window"),
        "decision_minute": record.get("decision_minute"),
        "final_wld": final_wld, "final_score_home": final_score_home, "final_score_away": final_score_away,
        "rps_model": _rps(p, y), "rps_anchor": _rps(a, y),
        "log_loss_model": logloss, "draw_brier_model": draw_brier,
        "result_event_time": result_event_time, "result_retrieval_time": result_retrieval_time,
        "scored_with": record["model_id"] + "@" + record["model_version"],
        "approval_status": "research_only",
    }
