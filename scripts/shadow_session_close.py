"""Forensic closure of the 2026-06-21 shadow session (read-only; no network, no new odds calls).

Scores ONLY valid frozen predictions for matches confirmed FINISHED within the session boundary,
enforcing snapshot_timestamp <= prediction_timestamp < kickoff. Deduplicates double-captured
snapshot types (keeps earliest). Writes a scorecard CSV + an immutable session-close manifest JSON.
Descriptive only; single match; NO significance claims.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import shadow_integrity as si  # noqa: E402

SDIR = ROOT / "outputs/live_shadow/session_20260621T182402Z"
PRED = ROOT / "outputs/research/live_2026_shadow_predictions.csv"

# Recorded, verified FINAL results from the supervisor transaction log (football-data.org).
# Belgium|Iran is the only PREDICTED-upcoming match that finished within the session boundary.
FINISHED_IN_SESSION = {
    "2026_G_0621_BelIra": {"outcome": "D", "score": "0-0",
                           "result_source": "football-data.org",
                           "verified_at": "2026-06-21T21:14:17.880300+00:00"},
}

preds = pd.read_csv(PRED)
ko = pd.to_datetime(preds["kickoff_utc"], utc=True)
snap = pd.to_datetime(preds["source_snapshot_timestamp"], utc=True, errors="coerce")
pt = pd.to_datetime(preds["prediction_timestamp"], utc=True, errors="coerce")
# scorable rule: snapshot <= prediction < kickoff
preds["valid_pre_kickoff"] = (snap <= pt) & (pt < ko)

rows = []
for mid, info in FINISHED_IN_SESSION.items():
    sub = preds[(preds.match_id == mid) & preds.valid_pre_kickoff].copy()
    sub["snapshot_type"] = sub["snapshot_type"].fillna("manual_baseline")
    # dedup double-captured (model, snapshot_type) -> keep earliest snapshot timestamp
    sub = sub.sort_values("source_snapshot_timestamp").drop_duplicates(["model_version", "snapshot_type"], keep="first")
    y = {"A": 0, "D": 1, "B": 2}[info["outcome"]]
    oh = np.eye(3)[y]
    for r in sub.itertuples():
        p = np.array([r.p_team_a_win, r.p_draw, r.p_team_b_win]); p = p / p.sum()
        rps = float(((np.cumsum(p) - np.cumsum(oh)) ** 2).sum() / 2.0)
        ll = float(-np.log(np.clip(p[y], 1e-12, 1)))
        dbrier = float((p[1] - (1.0 if info["outcome"] == "D" else 0.0)) ** 2)
        rows.append({"match_id": mid, "result": info["score"], "outcome": info["outcome"],
                     "model_version": r.model_version, "snapshot_type": r.snapshot_type,
                     "approval_status": r.approval_status, "snapshot_ts": r.source_snapshot_timestamp,
                     "p_a": round(p[0], 4), "p_draw": round(p[1], 4), "p_b": round(p[2], 4),
                     "rps": round(rps, 4), "log_loss": round(ll, 4), "draw_brier": round(dbrier, 4)})
score = pd.DataFrame(rows)
score.to_csv(SDIR / "scorecard.csv", index=False)
print("=== BelIra (0-0 Draw) descriptive scorecard — single match, NO significance ===")
print(score[["model_version", "snapshot_type", "p_draw", "rps", "log_loss", "draw_brier"]].to_string(index=False))

# integrity (hard) + duplicate-type (warning)
ig = si.run_all(preds)
dup_ok, dup_viol = si.check_no_duplicate_type_per_match(preds)

manifest = {
    "session_id": "session_20260621T182402Z",
    "original_start_utc": "2026-06-21T18:24:02.709784+00:00",
    "original_deadline_utc": "2026-06-21T23:24:02.709784+00:00",
    "actual_stop_utc": "2026-06-21T23:24:29.410694+00:00",
    "supervisor_status": "completed (ran through deadline; self-finalized)",
    "odds_credits_consumed": 7, "credit_cap": 30, "cap_exceeded": False,
    "provider_calls": {"the_odds_api": 7, "football_data_org": "polled >=10min (no credit cost)",
                       "api_football": 0, "open_meteo": 0},
    "snapshot_types_captured": ["manual_baseline(pre-supervisor)", "baseline", "T-90", "T-15", "final_pre_kickoff"],
    "predictions_total_rows": int(len(preds)),
    "predictions_valid_pre_kickoff": int(preds["valid_pre_kickoff"].sum()),
    "scorable_now": {"matches": list(FINISHED_IN_SESSION), "rows_scored": int(len(score))},
    "missed_unrecoverable": {
        "2026_G_0621_BelIra": ["baseline", "T-90"],  # session started 36 min before KO, after T-90
        "note": "session start 18:24Z > BelIra T-90 (17:30Z) and >100-min baseline window; not backfilled"},
    "results_recorded": FINISHED_IN_SESSION,
    "results_unavailable_for_predicted_upcoming": [
        "2026_H_0621_UruCap (KO 22:00Z, finished ~23:50Z AFTER deadline -> not scorable this session)"],
    "anomalies": {
        "duplicate_type_capture": {"present": (not dup_ok), "detail": dup_viol,
            "cause": "brief dual supervisor-instance overlap at 18:40Z during the troubled relaunch; "
                     "BelIra T-15 captured twice (identical values, different snapshot_ts); deduped for scoring",
            "leakage_impact": "none (both captures strictly pre-kickoff, identical)"},
        "2022_replay_own_goal_bug": {
            "fixture": 855767, "match": "Canada 1-2 Morocco (Group Stage 3)",
            "classification": "OWN_GOAL event-attribution convention mismatch",
            "detail": "API-Football credits an Own Goal to the BENEFICIARY team in the `team` field; "
                      "reconciliation/state_from_events incorrectly flips own goals to the opponent, "
                      "yielding event-count 0-3 vs official 1-2.",
            "scope": "2022 event-replay dataset only; does NOT affect live shadow (pre-match odds) or "
                     "BelIra scoring (no own goals).",
            "status": "BLOCKED for Tier-4/in-play training until own-goal handling is fixed + policy updated"},
    },
    "hard_integrity": ig,
    "governance": {"live_trading": False, "kalshi_enable_live_trading": False,
                   "approved_runtime_model": "B1", "shadow_models_in_runtime_path": False,
                   "candidate_py_modified": False},
    "valid_for": "descriptive scoring only (n=1 finished predicted match; underpowered; no significance)",
}
(SDIR / "session_close_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("\nhard_integrity all_ok:", ig["all_ok"], "| duplicate_type_warning:", (not dup_ok))
print("wrote scorecard.csv + session_close_manifest.json")
