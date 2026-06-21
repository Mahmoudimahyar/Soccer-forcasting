"""APPROVED runtime forecast command. Routes through the model registry: the default and only
approved model is B1/Elo. Emits an approved forecast + approved ledger (each row carries model
identity + approval status). Also RELABELS the existing market-blend output as a shadow artifact.

Run: python scripts/forecast_runtime.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.runtime import get_approved_model_id  # noqa: E402
from wcdrawlab.runtime.forecaster import runtime_forecast, label_shadow  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "research" / "forecasts"
SNAP = "2026-06-21"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    targets = pd.read_csv(PROC / "forecast_targets_2026.csv", parse_dates=["kickoff_utc"])

    # APPROVED forecast — B1/Elo, default model, fail-closed routing
    approved = runtime_forecast(targets, model_id=None, decision_timestamp=SNAP + "T00:00:00Z")
    approved.to_csv(OUT / "approved_forecast_2026.csv", index=False)
    # approved ledger: every row states which exact model produced it + approval status
    ledger_cols = ["match_id", "matchday", "group", "team_a", "team_b", "p_a", "p_draw", "p_b",
                   "model_id", "model_version", "approval_status", "prediction_mode",
                   "decision_timestamp", "commit_hash", "feature_schema_version", "source_manifest_id"]
    approved[[c for c in ledger_cols if c in approved.columns]].to_csv(OUT / "approved_ledger.csv", index=False)

    print(f"APPROVED model: {get_approved_model_id()} | rows: {len(approved)} | "
          f"mode: {approved['prediction_mode'].unique().tolist()}")
    print(approved[["match_id", "team_a", "team_b", "p_a", "p_draw", "p_b", "model_id", "approval_status"]]
          .head(6).to_string(index=False))

    # RELABEL existing market-blend output as SHADOW (preserve original; write a shadow-tagged copy)
    ma = OUT / "forecast_2026_market_anchored.csv"
    if ma.exists():
        mdf = pd.read_csv(ma)
        if {"p_a_final", "p_draw_final", "p_b_final"}.issubset(mdf.columns):
            shp = mdf.rename(columns={"p_a_final": "p_a", "p_draw_final": "p_draw", "p_b_final": "p_b"})
            shadow = label_shadow("MARKET_ELO_BLEND", shp, decision_timestamp=SNAP + "T00:00:00Z")
            keep = ["match_id", "team_a", "team_b", "p_a", "p_draw", "p_b", "model_id",
                    "prediction_mode", "experimental_status", "no_runtime_authority", "reason_not_approved"]
            shadow[[c for c in keep if c in shadow.columns]].to_csv(OUT / "shadow_market_blend_2026.csv", index=False)
            print(f"\nSHADOW relabelled: market blend -> {(OUT/'shadow_market_blend_2026.csv').name} "
                  f"(mode={shadow['prediction_mode'].iloc[0]}, no_runtime_authority="
                  f"{bool(shadow['no_runtime_authority'].iloc[0])})")
    print("\nApproved forecast + ledger written to", OUT)


if __name__ == "__main__":
    main()
