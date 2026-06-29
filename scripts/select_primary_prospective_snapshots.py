"""PHASE 3 — Primary one-snapshot-per-fixture selection (deterministic, outcome-independent).

Implements the LOCKED preregistration rule: for each fixture, choose the latest common valid pre-kickoff
snapshot covering all five compared models + the no-vig market. Pure function `select_primary` is unit-tested.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "prospective_harvest"))
from _harvest_common import PRED_LEDGER, FORECAST_TARGETS, SCORING_ROOT, stamp_labels, write_json  # noqa: E402

COMPARED = ["M1_B1", "M2_market", "M3_75_25", "M4_50_50", "M5_25_75"]
PRIMARY_CSV = SCORING_ROOT / "primary_snapshot_registry.csv"
EXCLUSION_CSV = SCORING_ROOT / "primary_snapshot_exclusions.csv"
SELECTION_JSON = SCORING_ROOT / "primary_snapshot_selection_manifest.json"


def _ts(x):
    try:
        return pd.Timestamp(str(x))
    except Exception:
        return pd.NaT


def _window_label(row) -> str:
    st = row.get("snapshot_type")
    if isinstance(st, str) and st:
        return st
    return "unknown"


def select_primary(preds: pd.DataFrame, ft: pd.DataFrame | None = None):
    """Return (primary_df, exclusions_df). Deterministic; depends only on timestamps + coverage."""
    p = preds.copy()
    p["_pt"] = p["prediction_timestamp"].map(_ts)
    p["_ko"] = p["kickoff_utc"].map(_ts)
    p["_ss"] = p["source_snapshot_timestamp"].map(_ts)
    valid_ids = set(ft["match_id"]) if ft is not None else None

    primary_rows, exclusions = [], []
    for mid, g in p.groupby("match_id"):
        if valid_ids is not None and mid not in valid_ids:
            exclusions.append({"canonical_fixture_id": mid, "reason": "unresolved_fixture_identity"})
            continue
        # candidate snapshots: group by source_snapshot_timestamp
        qualifying = []
        for ss, gs in g.groupby("source_snapshot_timestamp"):
            models = set(gs["model_version"])
            if not set(COMPARED).issubset(models):
                continue
            sub = gs[gs["model_version"].isin(COMPARED)]
            # pre-kickoff for all
            if not (sub["_pt"] < sub["_ko"]).all():
                continue
            # market present (M2..M5 rows have market columns non-null)
            mkt = sub[sub.model_version != "M1_B1"]
            if mkt[["p_a_market", "p_draw_market", "p_b_market"]].isna().any().any():
                continue
            # simplex valid for all five
            P = sub[["p_team_a_win", "p_draw", "p_team_b_win"]].to_numpy(dtype=float)
            if np.isnan(P).any() or (np.abs(P.sum(axis=1) - 1.0) > 1e-6).any():
                continue
            qualifying.append(_ts(ss))
        if not qualifying:
            exclusions.append({"canonical_fixture_id": mid, "reason": "no_common_market_snapshot"})
            continue
        primary_ss = max(qualifying)
        sel = g[g["_ss"] == primary_ss]
        sel = sel[sel["model_version"].isin(COMPARED)].drop_duplicates("model_version", keep="first")
        win = _window_label(sel[sel.model_version == "M2_market"].iloc[0]) if (sel.model_version == "M2_market").any() else "unknown"
        for r in sel.itertuples():
            primary_rows.append({
                "canonical_fixture_id": mid,
                "selected_source_snapshot_timestamp": str(primary_ss),
                "selected_window": win,
                "model_version": r.model_version,
                "prediction_timestamp": r.prediction_timestamp,
                "kickoff_utc": r.kickoff_utc,
                "p_team_a_win": r.p_team_a_win, "p_draw": r.p_draw, "p_team_b_win": r.p_team_b_win,
                "p_a_market": getattr(r, "p_a_market", None), "p_draw_market": getattr(r, "p_draw_market", None),
                "p_b_market": getattr(r, "p_b_market", None), "n_books": getattr(r, "n_books", None),
            })
    return pd.DataFrame(primary_rows), pd.DataFrame(exclusions)


def main():
    preds = pd.read_csv(PRED_LEDGER)
    ft = pd.read_csv(FORECAST_TARGETS)
    primary, excl = select_primary(preds, ft)
    SCORING_ROOT.mkdir(parents=True, exist_ok=True)
    primary.to_csv(PRIMARY_CSV, index=False)
    excl.to_csv(EXCLUSION_CSV, index=False)
    n_fix = primary["canonical_fixture_id"].nunique() if not primary.empty else 0
    write_json(SELECTION_JSON, stamp_labels({
        "rule": "latest_common_valid_pre_kickoff_snapshot_all_models_and_market",
        "compared_models": COMPARED,
        "n_primary_fixtures": int(n_fix),
        "n_excluded_fixtures": int(len(excl)),
        "window_distribution": primary.drop_duplicates("canonical_fixture_id")["selected_window"].value_counts().to_dict() if not primary.empty else {},
        "exclusion_reasons": excl["reason"].value_counts().to_dict() if not excl.empty else {},
    }))
    print(f"SELECT OK | primary_fixtures={n_fix} excluded={len(excl)} "
          f"rows={len(primary)} (expect 5/fixture)")
    if not primary.empty:
        print("  window dist:", primary.drop_duplicates('canonical_fixture_id')['selected_window'].value_counts().to_dict())
    if not excl.empty:
        print("  exclusions:", excl['reason'].value_counts().to_dict())


if __name__ == "__main__":
    main()
