"""Phase 2 freeze: fit M2fit_temp on PRE-2026 competitions only, freeze its exact parameters, and emit
the immutable holdout config + manifest for prospective 2026 scoring. No 2026 match is used to fit or
select. Run once at the freeze moment.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import M2fit_FittedPoisson, TemperatureScaled  # noqa: E402
from wcdrawlab.research.final_holdout import FEATURE_SCHEMA_V1  # noqa: E402

PRE2026 = ["inplay_state_2022_group_stage", "inplay_state_euro2024", "inplay_state_copa2024",
           "inplay_state_afcon2023", "inplay_state_asiancup2023"]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    frames = []
    for st in PRE2026:
        p = ROOT / f"data/processed/{st}.parquet"
        if p.exists():
            d = pd.read_parquet(p); d["competition"] = st; frames.append(d)
    train = pd.concat(frames, ignore_index=True)
    assert "2026" not in "".join(train.competition.unique()), "2026 must NOT be in the freeze training set"
    print(f"freeze training: {len(frames)} pre-2026 competitions, {train.match_id.nunique()} matches")

    ts = TemperatureScaled(M2fit_FittedPoisson).fit(train)
    base, k, T = ts.base.base_, ts.base.k_, ts.T
    print(f"frozen params: base={base:.4f} k={k:.4f} temperature={T:.4f}")

    git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    model_code_hash = sha256_file(ROOT / "src/wcdrawlab/research/inplay_models/models.py")
    frozen_code_hash = sha256_file(ROOT / "src/wcdrawlab/research/final_holdout.py")
    freeze_ts = datetime.now(timezone.utc).isoformat()

    cfg = {
        "model_id": "m2fit_temp_frozen",
        "architecture": "M2fit_temp = data-fit goal-rate Poisson (base,k) + remaining-time in-play update + temperature scaling",
        "approval_status": "research_only",
        "research_only": True, "experimental": True, "not_runtime_approved": True,
        "model_parameters": {"base": float(base), "k": float(k), "temperature": float(T)},
        "trained_on": "5 pre-2026 competitions (WC2022, Euro2024, Copa2024, AFCON2023, AsianCup2023); NO 2026 match",
        "feature_schema_version": "inplay_v1",
        "feature_schema": FEATURE_SCHEMA_V1,
        "pre_match_anchor": "elo_delta_home from elo_history.csv (Elo; market NOT used by this frozen model)",
        "allowed_data_sources": ["api_football_pro (fixtures/events for live state)", "elo_history.csv"],
        "output_schema": ["p_home_win", "p_draw", "p_away_win"],
        "scoring_only": True,
        "freeze_statement": "No 2026 match (finished or future) may influence model architecture, parameters, temperature, features, or selection. Future 2026 matches are scored by this frozen version only.",
    }
    (ROOT / "configs/final_holdout_model.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    manifest = {
        "final_holdout_freeze_utc": freeze_ts,
        "git_commit_hash": git_hash,
        "model_code_sha256": model_code_hash,
        "frozen_scorer_code_sha256": frozen_code_hash,
        "model_id": cfg["model_id"],
        "model_configuration": cfg["model_parameters"],
        "feature_schema_version": cfg["feature_schema_version"],
        "feature_schema": FEATURE_SCHEMA_V1,
        "allowed_data_sources": cfg["allowed_data_sources"],
        "output_schema": cfg["output_schema"],
        "model_approval_status": "research_only",
        "prediction_timestamps_rule": "each 2026 decision point is predicted from state known strictly before its decision_timestamp; predictions captured before the outcome is known",
        "no_influence_statement": "No remaining 2026 match may influence model selection, parameters, temperature, features, or architecture. Results are used ONLY for prospective scoring.",
        "trained_on": cfg["trained_on"],
    }
    (ROOT / "notes/research/final_holdout_freeze_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"FINAL_HOLDOUT_FREEZE_UTC = {freeze_ts}")
    print(f"git_commit={git_hash[:10]} model_code_sha256={model_code_hash[:12]}")
    print("wrote configs/final_holdout_model.yaml + notes/research/final_holdout_freeze_manifest.json")


if __name__ == "__main__":
    main()
