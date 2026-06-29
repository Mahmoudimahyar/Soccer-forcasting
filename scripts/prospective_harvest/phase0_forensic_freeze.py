"""PHASE 0 — Forensic freeze and input inventory.

Hashes the immutable frozen inputs, records counts, and validates every frozen prediction WITHOUT
mutating, deleting, or repairing anything. Invalid predictions are classified, not removed.

Outputs (worktree-owned):
  data/reference/prospective_frozen_input_manifest.json
  data/reference/prospective_frozen_input_manifest.csv
  notes/research/prospective_frozen_input_audit.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harvest_common import (  # noqa: E402
    COLLECTOR_RESULTS, FORECAST_TARGETS, LABELS, PRED_LEDGER, QUEUE, RAW_ODDS_DIR,
    WORKTREE_ROOT, canon, pair_key, sha256_file, stamp_labels, write_json,
)

NOW = pd.Timestamp("2026-06-29T23:59:59+00:00")  # system date upper bound for "should be final" reasoning
MANIFEST_JSON = WORKTREE_ROOT / "data/reference/prospective_frozen_input_manifest.json"
MANIFEST_CSV = WORKTREE_ROOT / "data/reference/prospective_frozen_input_manifest.csv"
AUDIT_MD = WORKTREE_ROOT / "notes/research/prospective_frozen_input_audit.md"

REQUIRED_FIELDS = [
    "prediction_timestamp", "match_id", "kickoff_utc", "model_version", "approval_status",
    "source_snapshot_timestamp", "p_team_a_win", "p_draw", "p_team_b_win",
]


def _ts(x):
    try:
        return pd.Timestamp(str(x))
    except Exception:
        return pd.NaT


def validate_predictions(preds: pd.DataFrame, ft: pd.DataFrame):
    mid2pair = {r.match_id: pair_key(r.team_a, r.team_b) for r in ft.itertuples()}
    rows = []
    for i, r in preds.iterrows():
        reasons = []
        for f in REQUIRED_FIELDS:
            if f not in preds.columns or pd.isna(r.get(f)):
                reasons.append(f"missing:{f}")
        # identity resolvable?
        if r.get("match_id") not in mid2pair:
            reasons.append("unresolved_fixture_identity")
        # probability simplex
        try:
            p = np.array([float(r["p_team_a_win"]), float(r["p_draw"]), float(r["p_team_b_win"])])
            if np.isnan(p).any():
                reasons.append("nan_probability")
            elif abs(p.sum() - 1.0) > 1e-6:
                reasons.append("non_simplex")
            elif (p < -1e-9).any() or (p > 1 + 1e-9).any():
                reasons.append("prob_out_of_range")
        except Exception:
            reasons.append("unparseable_probability")
        # pre-kickoff
        pt, ko = _ts(r.get("prediction_timestamp")), _ts(r.get("kickoff_utc"))
        if pd.notna(pt) and pd.notna(ko) and not (pt < ko):
            reasons.append("not_pre_kickoff")
        # market snapshot must not be after prediction (provenance ordering)
        st = _ts(r.get("source_snapshot_timestamp"))
        if pd.notna(st) and pd.notna(pt) and st > pt + pd.Timedelta(seconds=5):
            reasons.append("snapshot_after_prediction")
        # approval status sane
        if str(r.get("approval_status")) not in ("approved", "shadow"):
            reasons.append("bad_approval_status")
        rows.append({"row_index": i, "match_id": r.get("match_id"),
                     "model_version": r.get("model_version"),
                     "valid": len(reasons) == 0, "reasons": ";".join(reasons)})
    return pd.DataFrame(rows)


def main():
    preds = pd.read_csv(PRED_LEDGER)
    ft = pd.read_csv(FORECAST_TARGETS)
    queue = pd.read_csv(QUEUE) if QUEUE.exists() else pd.DataFrame()

    mid2pair = {r.match_id: pair_key(r.team_a, r.team_b) for r in ft.itertuples()}
    preds_pair = preds["match_id"].map(mid2pair)

    # raw odds snapshots: count + per-file hashes + combined hash
    raw_files = sorted(RAW_ODDS_DIR.glob("*.json")) if RAW_ODDS_DIR.exists() else []
    raw_hashes = {f.name: sha256_file(f) for f in raw_files}
    combined = "".join(sorted(h for h in raw_hashes.values() if h))
    import hashlib
    raw_combined_hash = hashlib.sha256(combined.encode()).hexdigest() if combined else None

    val = validate_predictions(preds, ft)

    pt = preds["prediction_timestamp"].map(_ts)
    ko = preds["kickoff_utc"].map(_ts)
    before_kickoff = int((pt < ko).sum())
    after_kickoff = int((pt >= ko).sum())

    # queue staleness: rows whose status looks not-final but kickoff is already in the past
    stale_queue = 0
    pending_queue = 0
    if not queue.empty and "kickoff_utc" in queue.columns:
        qko = queue["kickoff_utc"].map(_ts)
        status = queue.get("status", pd.Series(["?"] * len(queue))).astype(str).str.upper()
        scoring = queue.get("scoring_status", pd.Series([""] * len(queue))).astype(str)
        pending_queue = int((scoring == "pending").sum())
        stale_queue = int(((qko < NOW) & (~status.isin(["FT", "FINISHED", "AET", "PEN"]))).sum())

    def _count_rows(p):
        try:
            df = pd.read_csv(p)
            return int(len(df))
        except Exception:
            return 0

    counts = {
        "prediction_rows": int(len(preds)),
        "unique_fixture_ids": int(preds["match_id"].nunique()),
        "unique_match_keys_pairs": int(pd.Series([frozenset(x) if isinstance(x, frozenset) else x
                                                  for x in preds_pair.dropna()]).map(lambda s: tuple(sorted(s))).nunique()),
        "models_represented": sorted(preds["model_version"].dropna().unique().tolist()),
        "snapshot_types_represented": preds.get("snapshot_type", pd.Series(dtype=object)).dropna().unique().tolist(),
        "approved_rows": int((preds["approval_status"] == "approved").sum()),
        "shadow_rows": int((preds["approval_status"] == "shadow").sum()),
        "rows_before_kickoff": before_kickoff,
        "rows_after_kickoff": after_kickoff,
        "rows_missing_timestamps": int(preds[["prediction_timestamp", "source_snapshot_timestamp", "kickoff_utc"]].isna().any(axis=1).sum()),
        "rows_malformed_probabilities": int((~val["valid"] & val["reasons"].str.contains("simplex|nan_prob|out_of_range|unparseable", regex=True)).sum()),
        "rows_unresolved_identity": int(val["reasons"].str.contains("unresolved_fixture_identity").sum()),
        "rows_missing_provenance": int(preds.get("source_snapshot_timestamp", pd.Series([np.nan])).isna().sum()),
        "pending_queue_rows": pending_queue,
        "stale_queue_rows": stale_queue,
        "existing_scored_rows": _count_rows(WORKTREE_ROOT.parent / "worldcup_draw_model_lab_FINAL/outputs/research/prospective_scorecard.csv"),
        "existing_metrics_rows": _count_rows(WORKTREE_ROOT.parent / "worldcup_draw_model_lab_FINAL/outputs/research/live_2026_shadow_metrics.csv"),
        "existing_calibration_rows": _count_rows(WORKTREE_ROOT.parent / "worldcup_draw_model_lab_FINAL/outputs/research/live_2026_shadow_calibration.csv"),
        "valid_predictions": int(val["valid"].sum()),
        "invalid_predictions": int((~val["valid"]).sum()),
    }

    manifest = stamp_labels({
        "phase": "0_forensic_freeze",
        "system_now": str(NOW),
        "input_hashes": {
            "prediction_ledger": {"path": str(PRED_LEDGER), "sha256": sha256_file(PRED_LEDGER)},
            "forecast_targets": {"path": str(FORECAST_TARGETS), "sha256": sha256_file(FORECAST_TARGETS)},
            "queue": {"path": str(QUEUE), "sha256": sha256_file(QUEUE)},
            "collector_results_reference": {"path": str(COLLECTOR_RESULTS), "sha256": sha256_file(COLLECTOR_RESULTS)},
            "raw_odds_snapshots": {"dir": str(RAW_ODDS_DIR), "n_files": len(raw_files),
                                   "combined_sha256": raw_combined_hash},
        },
        "counts": counts,
        "invalid_classification": val[~val["valid"]][["row_index", "match_id", "model_version", "reasons"]].to_dict("records"),
    })
    write_json(MANIFEST_JSON, manifest)

    # per-row CSV manifest (immutable record of each prediction's hashable identity + validity)
    rec = preds[["match_id", "model_version", "prediction_timestamp", "source_snapshot_timestamp",
                 "kickoff_utc", "approval_status"]].copy()
    rec = rec.merge(val[["row_index", "valid", "reasons"]], left_index=True, right_on="row_index", how="left")
    rec.to_csv(MANIFEST_CSV, index=False)

    lines = ["# Prospective Frozen Input Audit (Phase 0)", "",
             "**" + " · ".join(f"{k}={v}" for k, v in LABELS.items()) + "**", "",
             "Read-only hash + inventory of the immutable frozen inputs. Nothing mutated, repaired, or deleted.",
             "", "## Input hashes",
             f"- prediction_ledger sha256 `{sha256_file(PRED_LEDGER)}`",
             f"- forecast_targets sha256 `{sha256_file(FORECAST_TARGETS)}`",
             f"- queue sha256 `{sha256_file(QUEUE)}`",
             f"- raw odds snapshots: {len(raw_files)} files, combined sha256 `{raw_combined_hash}`",
             "", "## Counts"]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Validity",
              f"- valid predictions: {counts['valid_predictions']} / {counts['prediction_rows']}",
              f"- invalid predictions: {counts['invalid_predictions']} (classified, not deleted)"]
    if counts["invalid_predictions"]:
        lines.append("")
        for r in val[~val["valid"]].head(25).itertuples():
            lines.append(f"  - row {r.row_index} {r.match_id} {r.model_version}: {r.reasons}")
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PHASE0 OK | preds={counts['prediction_rows']} valid={counts['valid_predictions']} "
          f"invalid={counts['invalid_predictions']} fixtures={counts['unique_fixture_ids']} "
          f"before_kickoff={counts['rows_before_kickoff']} after_kickoff={counts['rows_after_kickoff']}")
    print(f"  manifest -> {MANIFEST_JSON}")


if __name__ == "__main__":
    main()
