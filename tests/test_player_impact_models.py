"""Deterministic synthetic tests for the player-impact MODEL families. No network, no corpus.

Covers, for each family (W/D/L P*, next-goal N*, discipline C*, xG-fusion X*):
  - valid probabilities (in [0,1], sum to 1 for W/D/L, scalar in [0,1] for binary),
  - train-only fitting (the model object only ever sees train rows; predict() never refits),
  - no-leakage (test-row target is never read; the fitted model is identical whether or not test targets
    are present / corrupted),
  - determinism (two independent fits on the same train data give identical predictions),
  - graceful unknown-feature handling (rows missing player-impact columns predict valid probabilities and
    reduce toward the anchor instead of crashing).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research import player_impact_models as PIM  # noqa: E402

WDL = ["H", "D", "A"]


# ----------------------------------------------------------------------------------------------------
# synthetic data
# ----------------------------------------------------------------------------------------------------
def _wdl_rows(n=240, seed=0, with_impact=True):
    rng = np.random.default_rng(seed)
    rows = []
    comps = ["WC", "Euro", "Copa"]
    for i in range(n):
        minute = int(rng.choice([15, 30, 45, 60, 75]))
        score_diff = int(rng.integers(-2, 3))
        impact = float(rng.normal(score_diff * 0.3, 1.0))  # impact correlated with score for signal
        # target: a noisy function of score_diff + impact
        z = 0.9 * score_diff + 0.6 * impact + rng.normal(0, 0.8)
        target = "H" if z > 0.4 else ("A" if z < -0.4 else "D")
        r = {
            "match_id": f"m{i}", "competition": comps[i % 3], "comp_type": "international",
            "minute": minute, "remaining": 90 - minute,
            "score_h": max(0, score_diff), "score_a": max(0, -score_diff), "score_diff": score_diff,
            "card_diff": int(rng.integers(-1, 2)), "so_diff": 0,
            "subs_diff": int(rng.integers(-2, 3)), "player_count_diff": 0,
            "target_wdl": target,
            "next_goal_15": int(rng.random() < 0.30 + 0.05 * score_diff),
        }
        if with_impact:
            r["prematch_impact_diff"] = impact
            r["prematch_impact_uncertainty"] = float(abs(rng.normal(0, 0.5)))
            r["prematch_impact_coverage"] = float(rng.uniform(0.5, 1.0))
            r["onpitch_impact_diff"] = impact + float(rng.normal(0, 0.3))
            r["sub_impact_delta"] = float(rng.normal(0, 0.4))
        rows.append(r)
    return rows


def _discipline_rows(n=400, seed=1, positives_target=200):
    rng = np.random.default_rng(seed)
    rows = []
    comps = ["WC", "Euro", "Copa", "AFCON"]
    # force enough positives to open the C1 gate
    pos_flags = np.zeros(n, dtype=int)
    pos_flags[:positives_target] = 1
    rng.shuffle(pos_flags)
    for i in range(n):
        rows.append({
            "match_id": f"d{i}", "competition": comps[i % 4], "comp_type": "international",
            "minute": int(rng.choice([15, 30, 45, 60, 75])), "remaining": 30,
            "card_diff": int(rng.integers(-2, 3)), "so_diff": 0,
            "team_card_rate_prior": float(rng.uniform(0, 0.05)),
            "opp_card_rate_prior": float(rng.uniform(0, 0.05)),
            "discipline_event": int(pos_flags[i]),
        })
    return rows


def _probs_ok_wdl(p):
    assert set(p.keys()) >= set(WDL)
    vals = [p[k] for k in WDL]
    assert all(0.0 - 1e-9 <= v <= 1.0 + 1e-9 for v in vals), vals
    assert abs(sum(vals) - 1.0) < 1e-6, sum(vals)


# ----------------------------------------------------------------------------------------------------
# W/D/L  (W2 + P1..P4)
# ----------------------------------------------------------------------------------------------------
def test_wdl_valid_probabilities():
    rows = _wdl_rows()
    preds = PIM.wdl_predictors(rows)
    assert set(preds) == {"W2", "P1", "P2", "P3", "P4"}
    for name, fn in preds.items():
        for r in rows[:20]:
            _probs_ok_wdl(fn(r))


def test_w2_is_parameter_free_reference_and_score_responsive():
    # 2-0 up at 80' -> home heavily favored, independent of any fit
    lead = {"score_diff": 2, "remaining": 10}
    p = PIM.w2_poisson(lead)
    _probs_ok_wdl(p)
    assert p["H"] > 0.8
    trail = {"score_diff": -2, "remaining": 10}
    assert PIM.w2_poisson(trail)["A"] > 0.8


def test_wdl_train_only_fitting_no_leakage():
    """The fitted model must be identical whether or not the (held-out) rows it later scores carry the
    true target -- proves predict() reads no label."""
    train = _wdl_rows(n=240, seed=0)
    preds = PIM.wdl_predictors(train)
    test_clean = _wdl_rows(n=40, seed=99)
    test_corrupt = []
    for r in test_clean:
        c = dict(r)
        c["target_wdl"] = "D" if c["target_wdl"] != "D" else "H"  # corrupt the label
        c["next_goal_15"] = 1 - c["next_goal_15"]
        test_corrupt.append(c)
    for name, fn in preds.items():
        for a, b in zip(test_clean, test_corrupt):
            pa, pb = fn(a), fn(b)
            assert pa == pytest.approx(pb), name  # prediction unchanged by corrupting the label


def test_wdl_deterministic_across_independent_fits():
    train = _wdl_rows(n=240, seed=0)
    test = _wdl_rows(n=30, seed=7)
    p1 = PIM.wdl_predictors(train)
    p2 = PIM.wdl_predictors(train)
    for name in p1:
        for r in test:
            assert p1[name](r) == pytest.approx(p2[name](r)), name


def test_wdl_graceful_unknown_features():
    """Train WITH impact features; predict on rows that LACK them -> still valid probabilities."""
    train = _wdl_rows(n=240, seed=0, with_impact=True)
    preds = PIM.wdl_predictors(train)
    bare = {"score_diff": 0, "remaining": 45, "minute": 45,
            "card_diff": 0, "so_diff": 0, "subs_diff": 0, "player_count_diff": 0}
    for name, fn in preds.items():
        _probs_ok_wdl(fn(bare))


def test_wdl_models_train_on_impactless_data():
    """If the whole train set lacks impact columns, fitting still succeeds (all-unknown -> anchor)."""
    train = _wdl_rows(n=180, seed=3, with_impact=False)
    preds = PIM.wdl_predictors(train)
    for name, fn in preds.items():
        for r in train[:10]:
            _probs_ok_wdl(fn(r))


# ----------------------------------------------------------------------------------------------------
# next goal (N0..N3)
# ----------------------------------------------------------------------------------------------------
def test_nextgoal_valid_probabilities_and_base_rate():
    rows = _wdl_rows()
    preds = PIM.nextgoal_predictors(rows)
    assert set(preds) == {"N0", "N1", "N2", "N3"}
    base = sum(r["next_goal_15"] for r in rows) / len(rows)
    assert preds["N0"](rows[0]) == pytest.approx(base)
    for name, fn in preds.items():
        for r in rows[:20]:
            p = fn(r)
            assert 0.0 <= p <= 1.0


def test_nextgoal_no_leakage_and_deterministic():
    train = _wdl_rows(n=240, seed=0)
    a = PIM.nextgoal_predictors(train)
    b = PIM.nextgoal_predictors(train)
    test_clean = _wdl_rows(n=30, seed=5)
    test_corrupt = [dict(r, next_goal_15=1 - r["next_goal_15"]) for r in test_clean]
    for name in a:
        for r in test_clean:
            assert a[name](r) == pytest.approx(b[name](r)), name
        for cl, co in zip(test_clean, test_corrupt):
            assert a[name](cl) == pytest.approx(a[name](co)), name  # label not read at predict


def test_nextgoal_graceful_unknown_features():
    train = _wdl_rows(n=200, seed=0, with_impact=True)
    preds = PIM.nextgoal_predictors(train)
    bare = {"score_diff": 1, "remaining": 30, "minute": 60,
            "card_diff": 0, "so_diff": 0, "subs_diff": 0, "player_count_diff": 0}
    for name, fn in preds.items():
        assert 0.0 <= fn(bare) <= 1.0


# ----------------------------------------------------------------------------------------------------
# discipline (C0; C1 gated >=150 positives)
# ----------------------------------------------------------------------------------------------------
def test_discipline_gate_open_fits_c1():
    rows = _discipline_rows(n=400, positives_target=200)
    built = PIM.discipline_predictors(rows)
    assert built["C1_gate_open"] is True
    assert built["n_positives"] >= PIM.DISCIPLINE_POSITIVE_GATE
    assert set(built["predictors"]) == {"C0", "C1"}
    for name, fn in built["predictors"].items():
        for r in rows[:20]:
            assert 0.0 <= fn(r) <= 1.0


def test_discipline_gate_closed_skips_c1():
    rows = _discipline_rows(n=400, positives_target=40)  # < 150 positives
    built = PIM.discipline_predictors(rows)
    assert built["C1_gate_open"] is False
    assert "C1" not in built["predictors"]
    assert built["C1_status"] == "SKIPPED_below_gate"
    assert 0.0 <= built["predictors"]["C0"](rows[0]) <= 1.0


def test_discipline_no_leakage_and_deterministic():
    rows = _discipline_rows(n=400, positives_target=200)
    a = PIM.discipline_predictors(rows)["predictors"]
    b = PIM.discipline_predictors(rows)["predictors"]
    test_clean = _discipline_rows(n=40, seed=11, positives_target=20)
    test_corrupt = [dict(r, discipline_event=1 - r["discipline_event"]) for r in test_clean]
    for name in a:
        for r in test_clean:
            assert a[name](r) == pytest.approx(b[name](r)), name
        for cl, co in zip(test_clean, test_corrupt):
            assert a[name](cl) == pytest.approx(a[name](co)), name


def test_discipline_graceful_unknown_features():
    rows = _discipline_rows(n=400, positives_target=200)
    built = PIM.discipline_predictors(rows)
    bare = {"card_diff": 0, "so_diff": 0}  # missing history columns
    for name, fn in built["predictors"].items():
        assert 0.0 <= fn(bare) <= 1.0


# ----------------------------------------------------------------------------------------------------
# xG fusion (X0..X3)
# ----------------------------------------------------------------------------------------------------
def _xg_rows(n=200, seed=2):
    rng = np.random.default_rng(seed)
    rows = []
    comps = ["WC", "Euro", "Copa"]
    for i in range(n):
        score_diff = int(rng.integers(-2, 3))
        minute = int(rng.choice([30, 45, 60, 75]))
        xg = float(rng.normal(score_diff * 0.4, 0.8))
        impact = float(rng.normal(score_diff * 0.3, 1.0))
        z = 0.8 * score_diff + 0.5 * xg + 0.4 * impact + rng.normal(0, 0.7)
        target = "H" if z > 0.4 else ("A" if z < -0.4 else "D")
        rows.append({
            "match_id": f"x{i}", "competition": comps[i % 3], "comp_type": "international",
            "minute": minute, "remaining": 90 - minute, "score_diff": score_diff,
            "xg_diff_before": xg, "roll5_xg_diff": xg * 0.5, "roll10_xg_diff": xg * 0.7,
            "shotcount5_diff": float(rng.integers(-3, 4)), "shotcount10_diff": float(rng.integers(-5, 6)),
            "tsl_shot": float(rng.uniform(0, 10)), "tsl_major": float(rng.uniform(0, 20)),
            "prematch_impact_diff": impact, "prematch_impact_uncertainty": 0.3,
            "prematch_impact_coverage": 0.9, "onpitch_impact_diff": impact + 0.1,
            "target_wdl": target,
        })
    return rows


def test_xg_fusion_valid_probabilities():
    rows = _xg_rows()
    preds = PIM.xg_fusion_predictors(rows)
    assert set(preds) == {"X0", "X1", "X2", "X3"}
    for name, fn in preds.items():
        for r in rows[:20]:
            _probs_ok_wdl(fn(r))


def test_xg_fusion_no_leakage_and_deterministic():
    train = _xg_rows(n=200, seed=2)
    a = PIM.xg_fusion_predictors(train)
    b = PIM.xg_fusion_predictors(train)
    test_clean = _xg_rows(n=30, seed=21)
    test_corrupt = [dict(r, target_wdl=("D" if r["target_wdl"] != "D" else "H")) for r in test_clean]
    for name in a:
        for r in test_clean:
            assert a[name](r) == pytest.approx(b[name](r)), name
        for cl, co in zip(test_clean, test_corrupt):
            assert a[name](cl) == pytest.approx(a[name](co)), name


def test_xg_fusion_graceful_unknown_features():
    """X0 is the parameter-free W2 reference; X1/X2/X3 must degrade when xG / impact absent."""
    train = _xg_rows(n=200, seed=2)
    preds = PIM.xg_fusion_predictors(train)
    bare = {"score_diff": 0, "remaining": 45, "minute": 45}  # no xG, no impact
    for name, fn in preds.items():
        _probs_ok_wdl(fn(bare))
