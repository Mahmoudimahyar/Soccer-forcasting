"""Tests for the frozen prospective in-play model: deterministic, no fitting, matches the manifest."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.final_holdout import FrozenInPlayModel, load_frozen, FEATURE_SCHEMA_V1  # noqa: E402

CFG = ROOT / "configs/final_holdout_model.yaml"
MANIFEST = ROOT / "notes/research/final_holdout_freeze_manifest.json"


def _row(**kw):
    base = dict(elo_delta_home=120.0, decision_minute=60.0, score_home=1, score_away=0,
                red_home=0, red_away=0)
    base.update(kw)
    return pd.DataFrame([base])


def test_frozen_model_is_deterministic():
    m = FrozenInPlayModel(base=1.14, k=0.15, temperature=1.4)
    p1 = m.predict_wld(_row()); p2 = m.predict_wld(_row())
    assert (p1 == p2).all()
    assert abs(p1.sum() - 1.0) < 1e-9 and (p1 >= 0).all()


def test_frozen_config_loads_and_matches_manifest():
    if not CFG.exists() or not MANIFEST.exists():
        return  # freeze not run in this environment
    m = load_frozen(CFG)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert man["model_approval_status"] == "research_only"
    assert man["feature_schema"] == FEATURE_SCHEMA_V1
    # config params equal the manifest's frozen configuration
    assert abs(m.base - man["model_configuration"]["base"]) < 1e-12
    assert abs(m.k - man["model_configuration"]["k"]) < 1e-12
    assert abs(m.temperature - man["model_configuration"]["temperature"]) < 1e-12


def test_frozen_m2_v2_reproduces_M2():
    cfg = ROOT / "configs/final_holdout_model_m2.yaml"
    if not cfg.exists():
        return
    import numpy as np
    from wcdrawlab.research.inplay_models.models import M2_RemainingPoisson
    rows = pd.DataFrame([_row(elo_delta_home=d, decision_minute=m, score_home=s).iloc[0]
                         for d in (-100, 0, 150) for m in (15, 70) for s in (0, 1)])
    frozen = load_frozen(cfg).predict_wld(rows)
    assert np.allclose(frozen, M2_RemainingPoisson().predict_wld(rows), atol=1e-9)


def test_frozen_model_does_no_fitting():
    # a single row with no 'competition'/'final_wld' columns must still score (no fit path)
    m = load_frozen(CFG) if CFG.exists() else FrozenInPlayModel(1.14, 0.15, 1.4)
    out = m.predict_wld(_row(decision_minute=10.0, score_home=0, score_away=0))
    assert out.shape == (1, 3)
