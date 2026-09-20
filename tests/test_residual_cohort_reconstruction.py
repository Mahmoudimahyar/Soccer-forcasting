"""Tests for the independent residual 58-match cohort reconstruction + R0 RPS recompute.

Two layers:
  * UNIT tests (always run): exercise the from-scratch W2/R0 Poisson-convolution + RPS math against
    hand-computable references. These prove the recompute engine is correct independent of any data.
  * INTEGRATION tests (skipped in a clean worktree): reconstruct the real 58-match cohort from local
    artifacts and assert the funnel (258 -> 58), the cohort identity, and the bit-exact reproduction
    of the reported forward-chain (0.15263) and LOCO (0.14906) pooled R0 RPS.

The integration tests are gated on the presence of the residual run artifacts (gitignored, present
only on the research box). They skip with an explicit reason when those artifacts are absent.
research_only / experimental.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

THIS_ROOT = Path(__file__).resolve().parents[1]
AUDIT_PY = THIS_ROOT / "scripts/audit_residual_58_match_cohort.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("residual_audit_mod", AUDIT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AUD = _load_audit_module()

# Whether the real residual run artifacts are present (integration gate).
_HAVE_ARTIFACTS = (AUD.SNAP_CSV.exists() and AUD.WDL_CSV.exists()
                   and AUD.REPORTED_FC.exists() and AUD.REPORTED_LOCO.exists()
                   and AUD.BRIDGE_CSV.exists())
requires_artifacts = pytest.mark.skipif(
    not _HAVE_ARTIFACTS,
    reason="integration: requires gitignored residual run artifacts (snapshots/targets/reported "
           "forward-chain+loco/bridge) absent in a clean worktree")


# =================================================================================================
# UNIT -- the from-scratch R0 math (no data needed)
# =================================================================================================
def test_poisson_pmf_matches_closed_form():
    # PMF must equal exp(-lam) lam^k / k!
    for lam in (0.3, 1.35, 2.7):
        for k in (0, 1, 2, 5):
            ref = math.exp(-lam) * lam ** k / math.factorial(k)
            assert AUD._poisson_pmf(k, lam) == pytest.approx(ref, rel=1e-9, abs=1e-12)
    # lam == 0 degenerate: all mass at k=0
    assert AUD._poisson_pmf(0, 0.0) == 1.0
    assert AUD._poisson_pmf(3, 0.0) == 0.0


def test_r0_at_full_time_is_deterministic_from_current_diff():
    # At minute 90 (remaining 0), no remaining goals -> outcome is fully determined by current diff.
    home_lead = AUD.r0_wdl_from_row({"snapshot_minute": "90", "goals_home": "2", "goals_away": "0"})
    assert home_lead["H"] == pytest.approx(1.0, abs=1e-9)
    assert home_lead["D"] == pytest.approx(0.0, abs=1e-9)
    draw = AUD.r0_wdl_from_row({"snapshot_minute": "90", "goals_home": "1", "goals_away": "1"})
    assert draw["D"] == pytest.approx(1.0, abs=1e-9)
    away_lead = AUD.r0_wdl_from_row({"remaining_regulation_min": "0", "goals_diff": "-1"})
    assert away_lead["A"] == pytest.approx(1.0, abs=1e-9)


def test_r0_is_a_valid_simplex_and_symmetric_at_kickoff():
    # At kickoff (0-0, full time remaining) home and away intensities are equal -> P(H) == P(A).
    p = AUD.r0_wdl_from_row({"snapshot_minute": "0", "goals_home": "0", "goals_away": "0"})
    assert set(p) == {"H", "D", "A"}
    assert sum(p.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(v >= 0 for v in p.values())
    assert p["H"] == pytest.approx(p["A"], abs=1e-9)
    assert p["D"] > 0.0


def test_r0_uses_remaining_minutes_when_present_over_snapshot_minute():
    # remaining_regulation_min should take precedence over snapshot_minute (builder may shift clocks).
    p_rem0 = AUD.r0_wdl_from_row({"remaining_regulation_min": "0", "snapshot_minute": "10",
                                  "goals_home": "1", "goals_away": "0"})
    assert p_rem0["H"] == pytest.approx(1.0, abs=1e-9)  # 0 remaining -> home win locked


def test_rps_wdl_known_values():
    # Perfect confident correct prediction -> RPS 0.
    assert AUD.rps_wdl({"H": 1.0, "D": 0.0, "A": 0.0}, "H") == pytest.approx(0.0, abs=1e-12)
    # Uniform prediction RPS for an ordered 3-outcome target:
    #   H outcome: cum diffs (1/3-1, 2/3-1) -> ((-2/3)^2+(-1/3)^2)/2 = (4/9+1/9)/2 = 5/18
    u = {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
    assert AUD.rps_wdl(u, "H") == pytest.approx(5 / 18, abs=1e-12)
    # Confident-but-wrong (predict A, truth H): cum (0-1,0-1)->(1+1)/2 = 1.0
    assert AUD.rps_wdl({"H": 0.0, "D": 0.0, "A": 1.0}, "H") == pytest.approx(1.0, abs=1e-12)


def test_logloss_and_brier_helpers():
    assert AUD.logloss_wdl({"H": 1.0, "D": 0.0, "A": 0.0}, "H") == pytest.approx(0.0, abs=1e-9)
    assert AUD.brier_draw({"H": 0.0, "D": 1.0, "A": 0.0}, "D") == pytest.approx(0.0, abs=1e-12)
    assert AUD.brier_draw({"H": 0.0, "D": 0.0, "A": 1.0}, "D") == pytest.approx(1.0, abs=1e-12)


def test_forward_chain_order_is_by_first_kickoff():
    rows = [
        {"competition_label": "B", "kickoff_date": "2024-06-20"},
        {"competition_label": "A", "kickoff_date": "2018-06-14"},
        {"competition_label": "A", "kickoff_date": "2018-06-15"},
        {"competition_label": "C", "kickoff_date": "2021-06-11"},
    ]
    assert AUD.forward_chain_order(rows) == ["A", "C", "B"]


def test_recompute_forward_chain_on_synthetic_panel():
    # 3 synthetic competitions, train-free R0; N comps -> N-1 folds; pooled n = sum of test folds.
    rows = []
    for ci, (comp, kd) in enumerate([("A", "2018-01-01"), ("B", "2020-01-01"), ("C", "2022-01-01")]):
        for j in range(4):
            rows.append({"source_match_id": f"{comp}{j}", "competition_label": comp,
                         "kickoff_date": kd, "snapshot_minute": "45",
                         "goals_home": str(j % 2), "goals_away": "0", "target_wdl": "H"})
    fc = AUD.recompute_forward_chain(rows)
    assert fc["competition_order"] == ["A", "B", "C"]
    assert fc["n_folds"] == 2                       # B tested on A; C tested on A+B
    assert fc["pooled"]["n_test_rows"] == 8         # 4 (B) + 4 (C)
    assert 0.0 <= fc["pooled"]["rps"] <= 1.0


def test_match_bootstrap_is_clustered_and_deterministic():
    # Bootstrap unit is the MATCH; same seed -> same CI; CI brackets the mean.
    vals = [0.1, 0.2, 0.15, 0.05, 0.3, 0.12, 0.18, 0.22, 0.09, 0.27]
    lo1, hi1 = AUD.match_bootstrap_ci(vals, n=500, seed=42)
    lo2, hi2 = AUD.match_bootstrap_ci(vals, n=500, seed=42)
    assert (lo1, hi1) == (lo2, hi2)                 # deterministic for fixed seed
    mean = sum(vals) / len(vals)
    assert lo1 <= mean <= hi1


def test_fnum_preserves_missingness():
    assert AUD._fnum({"x": ""}, "x") is None
    assert AUD._fnum({"x": "none"}, "x") is None
    assert AUD._fnum({}, "x") is None
    assert AUD._fnum({"x": "2.5"}, "x") == 2.5


# =================================================================================================
# INTEGRATION -- real 58-match cohort reconstruction (skipped without artifacts)
# =================================================================================================
@requires_artifacts
def test_funnel_258_to_58_with_loss_reason():
    funnel, err = AUD.build_funnel()
    assert err is None
    stages = {s["stage"]: s for s in funnel["stages"]}
    assert stages["exact_international_bridge"]["n_matches"] == 258
    assert stages["statsbomb_events_cached_on_disk"]["n_matches"] == 58
    assert stages["residual_target_eligible_snapshots"]["n_matches"] == 58
    # the 200 loss is entirely "no cached StatsBomb events on disk"
    assert funnel["loss_by_reason"]["bridge_exact_to_cached"]["n_lost"] == 200
    assert funnel["loss_by_reason"]["cached_to_eligible"]["n_lost"] == 0


@requires_artifacts
def test_cohort_competition_split_is_12_12_12_12_10():
    funnel, _ = AUD.build_funnel()
    elig = funnel["by_competition"]["eligible"]
    assert elig == {"FIFA World Cup 2018": 12, "FIFA World Cup 2022": 12,
                    "UEFA Euro 2020": 12, "UEFA Euro 2024": 12, "Copa America 2024": 10}
    assert sum(elig.values()) == 58


@requires_artifacts
def test_forward_chain_pooled_rps_matches_reported_0_15263():
    snap = AUD._read_csv(AUD.SNAP_CSV)
    wdl = AUD._read_csv(AUD.WDL_CSV)
    rows = AUD.attach_targets(snap, wdl)
    fc = AUD.recompute_forward_chain(rows)
    rep = AUD._read_json(AUD.REPORTED_FC)
    rep_r0 = rep["pooled"]["research.residual.w2_reference_r0"]
    assert fc["n_folds"] == 4
    assert fc["pooled"]["n_test_rows"] == rep_r0["n_test_rows"] == 5789
    assert fc["pooled"]["rps"] == pytest.approx(0.15263, abs=1e-5)
    assert fc["pooled"]["rps"] == pytest.approx(rep_r0["rps"], abs=5e-5)


@requires_artifacts
def test_loco_pooled_rps_matches_reported_0_14906_and_per_match_array():
    snap = AUD._read_csv(AUD.SNAP_CSV)
    wdl = AUD._read_csv(AUD.WDL_CSV)
    rows = AUD.attach_targets(snap, wdl)
    pooled, pm_means, _ = AUD.recompute_loco_pooled_and_per_match(rows)
    rep = AUD._read_json(AUD.REPORTED_LOCO)
    rep_r0 = rep["pooled"]["research.residual.w2_reference_r0"]
    assert pooled["n_test_rows"] == rep_r0["n_test_rows"] == 7376
    assert pooled["rps"] == pytest.approx(0.14906, abs=1e-5)
    # per-match RPS multiset must reproduce the reported 58-value array exactly
    rep_pm = sorted(round(v, 6) for v in rep["per_match_rps"]["research.residual.w2_reference_r0"])
    mine = sorted(round(v, 6) for v in pm_means.values())
    assert len(mine) == len(rep_pm) == 58
    assert all(abs(a - b) < 1e-4 for a, b in zip(mine, rep_pm))


@requires_artifacts
def test_every_test_row_is_international_and_no_2026():
    snap = AUD._read_csv(AUD.SNAP_CSV)
    comps = {r.get("competition_label") for r in snap}
    assert "FIFA World Cup 2026" not in comps        # locked holdout never in the cohort
    assert all(r.get("comp_type", "international") == "international" for r in snap)
