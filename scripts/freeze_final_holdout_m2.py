"""Re-freeze (v2): adopt plain M2 (remaining-time Poisson) as the operative prospective in-play model,
per the Phase 5 nested-CV finding (M2fit_temp did NOT survive selection; M2 is the reference). M2 is
parameter-free (base=1.35, k=0.20, no temperature), so the frozen object is fully transparent.
v1 (m2fit_temp freeze) is retained as an immutable historical record. research_only.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.final_holdout import FEATURE_SCHEMA_V1, FrozenInPlayModel  # noqa: E402
from wcdrawlab.research.inplay_models.models import M2_RemainingPoisson  # noqa: E402
import pandas as pd  # noqa: E402

BASE, K, TEMP = 1.35, 0.20, 1.0  # plain M2 = pregame_lambdas defaults, no temperature


def main():
    # sanity: FrozenInPlayModel(BASE,K,TEMP) must reproduce M2 exactly
    rows = pd.DataFrame([{"elo_delta_home": d, "decision_minute": m, "score_home": sh, "score_away": sa,
                          "red_home": 0, "red_away": 0}
                         for d in (-150, 0, 200) for m in (10, 55, 85) for (sh, sa) in ((0, 0), (1, 0), (1, 2))])
    fm = FrozenInPlayModel(BASE, K, TEMP).predict_wld(rows)
    m2 = M2_RemainingPoisson().predict_wld(rows)
    assert np.allclose(fm, m2, atol=1e-9), "frozen M2 must equal M2_RemainingPoisson"
    print(f"verified frozen M2 == M2_RemainingPoisson on {len(rows)} sample rows")

    git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    code_hash = hashlib.sha256((ROOT / "src/wcdrawlab/research/inplay_models/models.py").read_bytes()).hexdigest()
    scorer_hash = hashlib.sha256((ROOT / "src/wcdrawlab/research/final_holdout.py").read_bytes()).hexdigest()
    ts = datetime.now(timezone.utc).isoformat()

    cfg = {
        "model_id": "m2_frozen",
        "architecture": "M2 = remaining-time Poisson anchored on Elo supremacy (pregame_lambdas base=1.35, k=0.20); no fitting, no temperature",
        "supersedes": "m2fit_temp_frozen (v1) — discredited by Phase 5 nested CV (selection-on-test)",
        "approval_status": "research_only", "research_only": True, "experimental": True,
        "not_runtime_approved": True,
        "model_parameters": {"base": BASE, "k": K, "temperature": TEMP},
        "selection_justification": "Phase 5 nested LOGO selected plain M2 (4/6 folds); M2fit_temp/xG never selected. See inplay_model_selection_report.md.",
        "trained_on": "none (M2 is parameter-free / transparent)",
        "feature_schema_version": "inplay_v1", "feature_schema": FEATURE_SCHEMA_V1,
        "pre_match_anchor": "elo_delta_home from elo_history.csv",
        "allowed_data_sources": ["api_football_pro (fixtures/events for live state)", "elo_history.csv"],
        "output_schema": ["p_home_win", "p_draw", "p_away_win"], "scoring_only": True,
        "freeze_statement": "No 2026 match may influence this model (it has no free parameters). Future 2026 matches are scored by this frozen M2 only.",
    }
    (ROOT / "configs/final_holdout_model_m2.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    manifest = {
        "final_holdout_freeze_utc_v2": ts, "version": 2, "git_commit_hash": git_hash,
        "model_code_sha256": code_hash, "frozen_scorer_code_sha256": scorer_hash,
        "model_id": "m2_frozen", "model_configuration": cfg["model_parameters"],
        "supersedes_v1": "m2fit_temp_frozen", "reason": cfg["selection_justification"],
        "feature_schema_version": "inplay_v1", "feature_schema": FEATURE_SCHEMA_V1,
        "allowed_data_sources": cfg["allowed_data_sources"], "output_schema": cfg["output_schema"],
        "model_approval_status": "research_only",
        "no_influence_statement": "M2 has no free parameters; no 2026 result can change it. Results used only for prospective scoring.",
    }
    (ROOT / "notes/research/final_holdout_freeze_manifest_v2.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"v2 freeze: m2_frozen | base={BASE} k={K} T={TEMP} | git {git_hash[:10]} | {ts}")
    print("wrote configs/final_holdout_model_m2.yaml + notes/research/final_holdout_freeze_manifest_v2.json")


if __name__ == "__main__":
    main()
