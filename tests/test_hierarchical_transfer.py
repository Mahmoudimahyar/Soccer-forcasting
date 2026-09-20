"""DETERMINISTIC tests for the hierarchical cross-domain transfer ladder (Phase 4-6).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Covers wcdrawlab.research.hierarchical_transfer.{models,domain_baselines,partial_pooling,
selective_transfer,eval,registry}. All synthetic tests run ALWAYS (no disk / no network) on a
deterministic, 3-tournament + club-aux transfer dataset built via the Phase-3 builder. The real-CSV
tests are integration tests that SKIP cleanly when the materialized dataset is absent.

Hard properties asserted (>= 30 deterministic tests):
  * the ladder + registry are wired correctly (8 models, T0 reference, T2 diagnostic-only/never-promoted);
  * T0 is parameter-free and never fits; its probs read the dataset's pre-computed t0_prob_* columns;
  * every model returns a valid H/D/A simplex; RPS / logloss3 / draw-Brier are finite;
  * the W/D/L Poisson conversions (exact + MC) are valid simplices and agree at large MC budget;
  * the ridge residual regressor is deterministic and reduces TRAIN residual MSE vs the zero predictor;
  * partial pooling: shrinkage -> inf collapses T4 toward T3 (shared-only);
  * selective transfer: gate fails -> alpha 0 -> T6 == T1 exactly; always-on flips the gate;
  * T7 draw recalibration keeps the simplex valid and is monotone in the raw draw prob;
  * LOCO + forward-chaining produce >= 2 folds with finite metrics on the synthetic 3-tournament set;
  * intl-only test population enforced (a club row planted in a test set is rejected);
  * no completed-2026 row may enter the eval (assert_no_2026 + a positive 2026-poison rejection);
  * match-level paired bootstrap CI is finite and ordered;
  * the candidate rule never promotes a diagnostic-only (T2) or the reference (T0).
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wcdrawlab.research.transfer import domain_normalized_dataset as DND  # noqa: E402
from wcdrawlab.research import hierarchical_transfer as HT  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import models as M  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import domain_baselines as DB  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import partial_pooling as PP  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import selective_transfer as ST  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import registry as REG  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import eval as HE  # noqa: E402

DATASET_CSV = ROOT / "data/processed/domain_normalized_transfer/transfer_dataset_v1.csv"


# =================================================================================================
# deterministic synthetic transfer dataset (3 temporally-separated tournaments + club aux)
# =================================================================================================
def _three_tour_intl():
    rows = []
    tours = [("SynthCupA", "2016", "2016-06-14"), ("SynthCupB", "2018", "2018-06-14"),
             ("SynthCupC", "2022", "2022-11-20")]
    mid = 0
    for tour, season, base_ko in tours:
        for m in range(6):
            mid += 1
            reg_h = (mid * 2) % 4
            reg_a = (mid * 3) % 3
            tgt = "H" if reg_h > reg_a else ("A" if reg_a > reg_h else "D")
            has_xg = (m % 3 != 0)
            for t in (20.0, 45.0, 70.0):
                cur_h = int(round(reg_h * (t / 90.0)))
                cur_a = int(round(reg_a * (t / 90.0)))
                r = {"source_match_id": f"I{mid:03d}", "match_id": f"I{mid:03d}",
                     "competition_label": tour, "competition": tour, "season": season,
                     "comp_type": "international", "domain": "international",
                     "kickoff_date": base_ko[:8] + f"{14 + m:02d}", "snapshot_minute": t,
                     "snapshot_reason": "clock", "remaining_regulation_min": 90.0 - t,
                     "period": 1 if t < 45 else 2, "goals_home": cur_h, "goals_away": cur_a,
                     "goals_diff": cur_h - cur_a, "players_home": 11, "players_away": 11,
                     "players_diff": 0, "yellow_diff": (mid % 3) - 1, "sendoff_diff": 0,
                     "subs_used_diff": (mid % 4) - 2, "poss_share_diff": -0.1 + 0.02 * m,
                     "field_tilt_home": 0.45 + 0.01 * m, "final_third_actions_diff": (mid % 11) - 5,
                     "box_entries_diff": (mid % 7) - 3, "recoveries_diff": (mid % 9) - 4,
                     "turnovers_diff": (mid % 9) - 4, "corners_diff": (mid % 5) - 2,
                     "att_free_kicks_diff": (mid % 6) - 2, "shots_diff": (mid % 7) - 3,
                     "shots_on_target_diff": (mid % 5) - 2, "n_events_observed": 400 + mid,
                     "source_root": "lake_object", "source_sha256": f"sha_{mid}",
                     "engine_version": "synth", "rem_goals_home": float(max(0, reg_h - cur_h)),
                     "rem_goals_away": float(max(0, reg_a - cur_a)), "target_wdl": tgt}
                if has_xg:
                    r.update({"xg_present": "True", "cum_xg_diff": 0.2 * (cur_h - cur_a),
                              "cum_xg_total": 0.3 * (cur_h + cur_a) + 0.4,
                              "xg_last5m_diff": 0.05 * ((mid % 5) - 2),
                              "xg_last10m_diff": 0.08 * ((mid % 7) - 3)})
                else:
                    r["xg_present"] = "False"
                rows.append(r)
    return rows


@pytest.fixture(scope="module")
def synth_rows():
    intl = _three_tour_intl()
    club = DND.synthetic_club_rows(n_matches=8)
    out = DND.build_all_fold_rows(intl, club)
    return out["rows"]


@pytest.fixture(scope="module")
def synth_fold(synth_rows):
    groups = HE.fold_groups(synth_rows)
    tour = HE._tournament_order(synth_rows)[-1]   # latest tournament has the most training data
    g = groups[tour]
    return g["train"], g["test"]


# =================================================================================================
# registry / wiring
# =================================================================================================
def test_ladder_has_eight_models():
    assert len(HT.LADDER) == 8
    assert HT.LADDER == ("T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7")


def test_registry_maps_every_ladder_id():
    summ = REG.registry_summary()
    assert set(summ) == set(HT.LADDER)
    for sid in HT.LADDER:
        assert summ[sid]["canonical_id"].startswith("research.transfer.")


def test_T0_is_reference_and_canonical():
    assert REG.is_reference("T0")
    assert REG.canonical_id("T0") == HT.REFERENCE_MODEL


def test_T2_is_diagnostic_only_and_not_promotable():
    assert REG.is_diagnostic_only("T2")
    assert not REG.is_promotable("T2")


def test_reference_not_promotable_as_its_own_candidate():
    assert not REG.is_promotable("T0")


def test_promotable_set_excludes_T0_T2():
    promotable = [s for s in HT.LADDER if REG.is_promotable(s)]
    assert "T0" not in promotable and "T2" not in promotable
    assert set(promotable) == {"T1", "T3", "T4", "T5", "T6", "T7"}


def test_build_returns_unfitted_model():
    m = REG.build("T1")
    assert isinstance(m, DB.T1InternationalOnly)
    assert m.fitted is False


def test_build_unknown_id_raises():
    with pytest.raises(KeyError):
        REG.build("T99")


# =================================================================================================
# W/D/L conversions (models.py)
# =================================================================================================
def test_exact_wdl_is_simplex():
    p = M.remaining_goal_exact_wdl(1.0, 1.0, 0)
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert all(0.0 <= v <= 1.0 for v in p.values())


def test_exact_wdl_symmetric_when_level():
    p = M.remaining_goal_exact_wdl(1.2, 1.2, 0)
    assert abs(p["H"] - p["A"]) < 1e-9


def test_exact_wdl_lead_favours_home():
    p = M.remaining_goal_exact_wdl(1.0, 1.0, 2)   # home +2
    assert p["H"] > p["A"]


def test_mc_wdl_is_simplex_and_deterministic():
    p1 = M.remaining_goal_mc_wdl(1.0, 0.8, 1, n_sims=2000, seed=7)
    p2 = M.remaining_goal_mc_wdl(1.0, 0.8, 1, n_sims=2000, seed=7)
    assert p1 == p2
    assert abs(sum(p1.values()) - 1.0) < 1e-9


def test_mc_agrees_with_exact_at_large_budget():
    exact = M.remaining_goal_exact_wdl(1.1, 0.9, 0)
    mc = M.remaining_goal_mc_wdl(1.1, 0.9, 0, n_sims=80000, seed=123)
    for k in ("H", "D", "A"):
        assert abs(exact[k] - mc[k]) < 0.02


def test_cell_float_preserves_missingness():
    assert M.cell_float({"a": ""}, "a") is None
    assert M.cell_float({"a": "nan"}, "a") is None
    assert M.cell_float({}, "a") is None
    assert M.cell_float({"a": "1.5"}, "a") == 1.5


# =================================================================================================
# ridge residual regressor (models.py)
# =================================================================================================
def test_ridge_is_deterministic(synth_fold):
    train, _ = synth_fold
    cols = M.stable_feature_columns(train)
    m1 = M.RidgePoissonResidual(side="home", ridge=1.0).fit(train, cols)
    m2 = M.RidgePoissonResidual(side="home", ridge=1.0).fit(train, cols)
    r = train[0]
    assert abs(m1.predict_residual(r) - m2.predict_residual(r)) < 1e-12


def test_ridge_beats_zero_on_train_mse(synth_fold):
    train, _ = synth_fold
    cols = M.stable_feature_columns(train)
    m = M.RidgePoissonResidual(side="total", ridge=0.3).fit(train, cols)
    sse_model = sse_zero = 0.0
    n = 0
    for r in train:
        y = M.cell_float(r, "transfer_residual_total")
        if y is None:
            continue
        sse_model += (m.predict_residual(r) - y) ** 2
        sse_zero += y * y
        n += 1
    assert n > 0
    assert sse_model <= sse_zero + 1e-6   # ridge fit never worse than predicting zero on TRAIN


def test_intensity_is_floored_nonnegative(synth_fold):
    train, test = synth_fold
    cols = M.stable_feature_columns(train)
    m = M.RidgePoissonResidual(side="home", ridge=1.0).fit(train, cols)
    for r in test:
        assert m.intensity(r) >= 0.0


def test_cross_fit_lambda_returns_candidate(synth_fold):
    train, _ = synth_fold
    cols = M.stable_feature_columns(train)
    best, scores = M.cross_fit_ridge_lambda(train, cols, "home")
    assert best > 0
    # all reported cv scores are finite
    assert all(math.isfinite(v) for v in scores.values()) or scores == {}


# =================================================================================================
# T0 / T1 / T2 baselines (domain_baselines.py)
# =================================================================================================
def test_T0_does_not_fit_and_reads_columns(synth_fold):
    train, test = synth_fold
    t0 = DB.T0Reference().fit(train)   # no-op
    p = t0.predict_wdl(test[0])
    assert abs(sum(p.values()) - 1.0) < 1e-9


def test_T1_intensity_and_wdl_valid(synth_fold):
    train, test = synth_fold
    t1 = DB.T1InternationalOnly().fit(train)
    assert t1.n_train_intl > 0
    for r in test:
        p = t1.predict_wdl(r)
        assert abs(sum(p.values()) - 1.0) < 1e-9


def test_T2_degenerate_flag_tracks_club_presence(synth_fold, synth_rows):
    train, _ = synth_fold
    t2 = DB.T2NaiveClubPool().fit(train)
    has_club = any(r.get("domain") == "club" for r in train)
    assert t2.degenerate_to_T1 == (not has_club)
    assert t2.is_diagnostic_only is True


def test_T2_pools_club_rows_when_present(synth_fold):
    train, _ = synth_fold
    t2 = DB.T2NaiveClubPool().fit(train)
    # synthetic club rows kick off in 2016 before every tournament -> present in every fold's training
    assert t2.n_train_club > 0
    assert t2.n_train_total > t2.n_train_club


# =================================================================================================
# partial pooling (partial_pooling.py)
# =================================================================================================
def test_T3_T4_T5_produce_valid_simplex(synth_fold):
    train, test = synth_fold
    for cls in (PP.T3SharedStableFeatures, PP.T4PartialPooling, PP.T5DomainWeighted):
        m = cls().fit(train)
        p = m.predict_wdl(test[0])
        assert abs(sum(p.values()) - 1.0) < 1e-9


def test_T4_shrinkage_monotonically_shrinks_deviation(synth_fold):
    # The defining partial-pooling property: a LARGER deviation ridge shrinks the intl-specific deviation
    # coefficient vector toward zero (more pooling). Assert the deviation weight norm is non-increasing in
    # dev_ridge. (At dev_ridge -> inf the deviation slopes vanish and T4 -> shared/T3 in the feature part.)
    import numpy as np
    train, _ = synth_fold
    t4_small = PP.T4PartialPooling(shared_ridge=1.0, dev_ridge=0.1).fit(train)
    t4_big = PP.T4PartialPooling(shared_ridge=1.0, dev_ridge=1e6).fit(train)
    # exclude the (unpenalized) bias term -> compare the penalized slope norm only
    norm_small = float(np.linalg.norm(t4_small.home.dev_w[:-1]))
    norm_big = float(np.linalg.norm(t4_big.home.dev_w[:-1]))
    assert norm_big <= norm_small + 1e-9
    assert norm_big < 1e-3   # heavy shrinkage drives the deviation slopes essentially to zero


def test_T5_domain_weight_intl_is_one():
    cols = ["goals_diff", "cum_xg_diff"]
    intl_row = {"domain": "international"}
    assert PP.domain_weight(intl_row, cols) == 1.0


def test_T5_club_weight_in_unit_interval():
    cols = ["goals_diff", "cum_xg_diff"]
    club_row = {"domain": "club", "domain_overlap_score": 0.5,
                "feat_goals_diff": 1.0, "feat_cum_xg_diff": 0.2}
    w = PP.domain_weight(club_row, cols)
    assert 0.0 <= w <= 1.0


def test_T5_records_mean_club_weight(synth_fold):
    train, _ = synth_fold
    t5 = PP.T5DomainWeighted().fit(train)
    if t5.n_train_club > 0:
        assert t5.mean_club_weight is not None and 0.0 <= t5.mean_club_weight <= 1.0


# =================================================================================================
# selective transfer + calibration (selective_transfer.py)
# =================================================================================================
def test_T6_gate_zero_when_support_below_threshold(synth_fold):
    train, test = synth_fold
    # synthetic fold has only 8 club matches < default support_min 30 -> transfer ineligible -> alpha 0
    t6 = ST.T6SelectiveTransfer().fit(train)
    assert t6.transfer_eligible_fold is False
    assert all(t6.gate_alpha(r) == 0.0 for r in test)


def test_T6_falls_back_exactly_to_T1_when_alpha_zero(synth_fold):
    train, test = synth_fold
    t6 = ST.T6SelectiveTransfer().fit(train)
    t1 = DB.T1InternationalOnly().fit(train)
    for r in test:
        a = t6.predict_intensity(r)
        b = t1.predict_intensity(r)
        assert abs(a["home"] - b["home"]) < 1e-9
        assert abs(a["away"] - b["away"]) < 1e-9


def test_T6_always_on_overrides_gate(synth_fold):
    train, test = synth_fold
    t6 = ST.T6SelectiveTransfer(always_on=True).fit(train)
    assert all(t6.gate_alpha(r) == t6.alpha_max for r in test)


def test_T6_eligible_when_support_threshold_lowered(synth_fold):
    train, _ = synth_fold
    t6 = ST.T6SelectiveTransfer(support_min=1).fit(train)
    # club support exists in synthetic folds -> fold becomes transfer-eligible
    if any(r.get("domain") == "club" for r in train):
        assert t6.transfer_eligible_fold is True


def test_T7_wdl_valid_simplex(synth_fold):
    train, test = synth_fold
    t7 = ST.T7CalibratedSimulation(n_sims=1500).fit(train)
    for r in test[:5]:
        p = t7.predict_wdl(r)
        assert abs(sum(p.values()) - 1.0) < 1e-9
        assert all(0.0 <= v <= 1.0 for v in p.values())


def test_monotone_calibrator_is_nondecreasing():
    cal = ST._MonotoneCalibrator()
    pairs = [(i / 100.0, 1.0 if i > 50 else 0.0) for i in range(100)]
    cal.fit(pairs)
    xs = [j / 20.0 for j in range(21)]
    ys = [cal.apply(x) for x in xs]
    for a, b in zip(ys, ys[1:]):
        assert b >= a - 1e-9


def test_calibrator_identity_when_too_few_points():
    cal = ST._MonotoneCalibrator()
    cal.fit([(0.3, 1.0), (0.4, 0.0)])
    assert cal.fitted is False
    assert cal.apply(0.37) == 0.37


# =================================================================================================
# eval drivers (eval.py)
# =================================================================================================
def test_loco_two_folds_finite_rps(synth_rows):
    res = HE.loco_eval(synth_rows, ids=("T0", "T1"))
    assert res["n_folds"] >= 2
    for f in res["folds"]:
        for sid in ("T0", "T1"):
            assert math.isfinite(f["models"][sid]["rps"])


def test_loco_full_ladder_all_finite(synth_rows):
    res = HE.loco_eval(synth_rows)
    assert set(res["folds"][0]["models"]) == set(HT.LADDER)
    for f in res["folds"]:
        for sid in HT.LADDER:
            assert f["models"][sid]["rps"] is not None
            assert math.isfinite(f["models"][sid]["rps"])


def test_forward_chain_produces_folds(synth_rows):
    fc = HE.forward_chain_eval(synth_rows, ids=("T0", "T1"))
    assert fc["n_folds"] >= 1
    assert fc["pooled"]["T0"]["rps"] is not None


def test_intl_only_test_population_enforced():
    bad_test = [{"domain": "club", "row_role": "intl_test", "target_wdl": "D"}]
    with pytest.raises(AssertionError):
        HE.assert_test_is_international_only(bad_test)


def test_assert_no_2026_rejects_poison():
    poison = [{"competition_label": "FIFA World Cup 2026", "kickoff_date": "2026-06-20",
               "target_wdl": "D"}]
    with pytest.raises(AssertionError):
        HE.assert_no_2026(poison)


def test_assert_no_2026_passes_clean(synth_rows):
    HE.assert_no_2026(synth_rows)   # must not raise


def test_score_wdl_metrics_finite(synth_fold):
    train, test = synth_fold
    t1 = DB.T1InternationalOnly().fit(train)
    sc = HE.score_wdl(t1.predict_wdl, test)
    assert math.isfinite(sc["rps"]) and math.isfinite(sc["logloss"])
    assert math.isfinite(sc["brier_draw"])
    assert sc["n_matches"] > 0


def test_paired_bootstrap_ci_ordered(synth_rows):
    res = HE.loco_eval(synth_rows, ids=("T0", "T1"))
    boot = HE.paired_bootstrap_delta(res["per_model_match_rps"], "T1", "T0")
    lo, hi = boot["ci95"]
    assert lo is not None and hi is not None
    assert lo <= hi


def test_reliability_tables_have_overlap_and_availability_slices(synth_rows):
    res = HE.loco_eval(synth_rows, ids=("T0", "T1"))
    rel = res["reliability"]["T1"]
    assert "domain_overlap" in rel and "availability" in rel
    assert rel["_overall_ece"] is None or math.isfinite(rel["_overall_ece"])


# =================================================================================================
# candidate rule (eval.py) — must never promote a diagnostic / the reference
# =================================================================================================
def test_candidate_rule_rejects_diagnostic_T2(synth_rows):
    res = HE.loco_eval(synth_rows)
    out = HE.evaluate_candidate_rule(res, "T2", "T0")
    assert out["verdict"] == "rejected"


def test_candidate_rule_rejects_reference_as_candidate(synth_rows):
    res = HE.loco_eval(synth_rows)
    out = HE.evaluate_candidate_rule(res, "T0", "T0")
    assert out["verdict"] == "rejected"


def test_candidate_rule_verdict_in_allowed_set(synth_rows):
    res = HE.loco_eval(synth_rows)
    out = HE.evaluate_candidate_rule(res, "T7", "T0")
    assert out["verdict"] in HE.CANDIDATE_VERDICTS
    assert out["candidate_canonical"].startswith("research.transfer.")


def test_candidate_rule_data_insufficient_on_one_fold():
    # a single-fold LOCO result must trigger data_insufficient (need >= 2 folds)
    one_fold = {"folds": [{"held_tournament": "X", "n_test_rows": 10,
                           "models": {"T0": {"rps": 0.2, "logloss": 1.0,
                                             "draw_calibration": {"ece": 0.1}},
                                      "T1": {"rps": 0.1, "logloss": 0.9,
                                             "draw_calibration": {"ece": 0.1}}}}],
                "per_model_match_rps": {"T0": {"m1": 0.2}, "T1": {"m1": 0.1}}}
    out = HE.evaluate_candidate_rule(one_fold, "T1", "T0")
    assert out["verdict"] == "data_insufficient"


# =================================================================================================
# integration: materialized real dataset (SKIP cleanly if absent)
# =================================================================================================
def _load_real():
    if not DATASET_CSV.exists():
        return None
    with DATASET_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.skipif(not DATASET_CSV.exists(), reason="materialized transfer dataset absent (clean worktree)")
def test_real_dataset_loco_finite():
    rows = _load_real()
    res = HE.loco_eval(rows, ids=("T0", "T1"))
    assert res["n_folds"] >= 2
    for f in res["folds"]:
        assert math.isfinite(f["models"]["T0"]["rps"])
        assert math.isfinite(f["models"]["T1"]["rps"])


@pytest.mark.skipif(not DATASET_CSV.exists(), reason="materialized transfer dataset absent (clean worktree)")
def test_real_dataset_test_population_is_international_only():
    rows = _load_real()
    test_rows = [r for r in rows if r.get("row_role") == "intl_test"]
    # must not raise
    HE.assert_test_is_international_only(test_rows)
    assert all(r.get("domain", "international") == "international" for r in test_rows)
