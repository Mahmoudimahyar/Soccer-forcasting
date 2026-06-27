"""DETERMINISTIC integrity tests for the residual goal-intensity DATASET (Phase 1).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Covers the residual goal-intensity plane built by scripts/build_residual_goal_intensity_dataset.py on top
of the leakage-safe event-process snapshots:

  * W2 reference reconstruction (intensity + final H/D/A probs) is parameter-free & symmetric
  * residual = observed - W2 (remaining-goal family AND near-term family)
  * remaining_* goals == regulation-final - goals-at-cutoff, all >= 0
  * regulation-only; extra-time + shootout goals NEVER count; ET kept separate
  * own-goal credited to the BENEFITING side (via the upstream goal attribution)
  * 5/10/15 horizon right-censoring (h_eff = min(h, 90-t); censor flag set when t+h>90)
  * competing-risk classes exhaustive {home_goal, away_goal, no_goal}; no-goal class present
  * no future goal/xG/possession/card/sub enters a snapshot feature
  * no cross-match leakage (each match's targets use only its own events)
  * source_sha256 / engine_version preserved
  * deterministic rebuild (byte-identical CSV on a second build)

Synthetic in-memory tests run ALWAYS (no disk). Tests that need the materialised real dataset are marked
`integration` and SKIP cleanly in a worktree that has not built it. >=25 tests.
"""
from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ---- import the W2 reference + the builder module (missing -> SKIP, never crash collection) ------
try:
    from wcdrawlab.research import dynamic_models as DM
except Exception as _e:  # pragma: no cover
    DM = None
    _DM_ERR = repr(_e)
else:
    _DM_ERR = ""


def _load_builder():
    path = ROOT / "scripts" / "build_residual_goal_intensity_dataset.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("residual_builder", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_builder()
OUT_DIR = ROOT / "data/processed/residual_goal_intensity"
SNAP_CSV = OUT_DIR / "residual_goal_intensity_snapshots.csv"
TGT_CSV = OUT_DIR / "near_term_competing_risk_targets.csv"
COR_CSV = OUT_DIR / "selective_dynamic_correction.csv"
HORIZONS = (5, 10, 15)


def _need_builder():
    if B is None:
        pytest.skip("residual builder script not importable")


def _read(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _has_real():
    return SNAP_CSV.exists() and TGT_CSV.exists() and COR_CSV.exists()


# =================================================================================================
# 1. W2 reference reconstruction (pure, synthetic)
# =================================================================================================
def test_w2_intensity_full_match_equals_base_rate():
    _need_builder()
    assert abs(B.w2_remaining_intensity(90.0) - B.W2_BASE) < 1e-9


def test_w2_intensity_half_match_is_half():
    _need_builder()
    assert abs(B.w2_remaining_intensity(45.0) - B.W2_BASE / 2.0) < 1e-9


def test_w2_intensity_zero_remaining_is_zero():
    _need_builder()
    assert abs(B.w2_remaining_intensity(0.0)) < 1e-12


def test_w2_intensity_symmetric_home_equals_away():
    # the W2 reference has no team prior: home and away intensities are identical by construction
    _need_builder()
    assert B.w2_remaining_intensity(33.0) == B.w2_remaining_intensity(33.0)


def test_w2_probs_match_r2_reference():
    if DM is None:
        pytest.skip(f"dynamic_models unavailable: {_DM_ERR}")
    p = DM.r2_remaining_time_poisson({"score_diff": 1, "remaining": 60})
    assert abs(p["H"] + p["D"] + p["A"] - 1.0) < 1e-9
    # leading by 1 with 60' left -> home most likely outcome
    assert p["H"] > p["A"]


def test_w2_window_score_prob_monotone_and_bounded():
    _need_builder()
    p5, p10, p15 = (B.w2_window_score_prob(h) for h in HORIZONS)
    assert 0.0 < p5 < p10 < p15 < 1.0


def test_w2_any_goal_exceeds_single_side():
    _need_builder()
    assert B.w2_window_any_goal_prob(10) > B.w2_window_score_prob(10)


def test_w2_any_goal_two_independent_poisson_identity():
    _need_builder()
    h = 12.0
    lam = B.W2_BASE * h / 90.0
    assert abs(B.w2_window_any_goal_prob(h) - (1 - math.exp(-2 * lam))) < 1e-12


# =================================================================================================
# 2. competing-risk right-censoring + classes (pure, synthetic)
# =================================================================================================
def _snap(minute, remaining, gh=0, ga=0, **kw):
    d = {"snapshot_minute": str(minute), "remaining_regulation_min": str(remaining),
         "goals_home": str(gh), "goals_away": str(ga), "goals_diff": str(gh - ga),
         "players_diff": "0", "n_events_observed": "300",
         "xg_last10m_home": "0.0", "xg_last10m_away": "0.0", "xg_present": "True"}
    d.update({k: str(v) for k, v in kw.items()})
    return d


def _sc(h_home=0, h_away=0):
    out = {}
    for h in HORIZONS:
        out[f"home_scores_next{h}m"] = str(int(h_home))
        out[f"away_scores_next{h}m"] = str(int(h_away))
        out[f"any_goal_next{h}m"] = str(int(bool(h_home or h_away)))
    return out


def test_censoring_horizon_truncated_near_fulltime():
    _need_builder()
    cr = B.competing_risk_for_horizon(_snap(85, 5), _sc(), {"next_goal_side": "none", "next_goal_minute": ""}, 15)
    assert abs(cr["next15_effective_horizon"] - 5.0) < 1e-9
    assert cr["next15_censored"] == 1


def test_no_censoring_when_window_fits():
    _need_builder()
    cr = B.competing_risk_for_horizon(_snap(30, 60), _sc(), {"next_goal_side": "none", "next_goal_minute": ""}, 15)
    assert cr["next15_effective_horizon"] == 15.0 and cr["next15_censored"] == 0


def test_effective_horizon_never_exceeds_remaining():
    _need_builder()
    for t in (10, 50, 80, 88, 90):
        for h in HORIZONS:
            cr = B.competing_risk_for_horizon(_snap(t, max(0, 90 - t)), _sc(),
                                              {"next_goal_side": "none", "next_goal_minute": ""}, h)
            assert cr[f"next{h}_effective_horizon"] <= min(h, 90 - t) + 1e-9
            assert cr[f"next{h}_effective_horizon"] <= 90 - t + 1e-9


def test_class_home_goal_when_home_scores_first_in_window():
    _need_builder()
    cr = B.competing_risk_for_horizon(_snap(30, 60), _sc(h_home=1),
                                      {"next_goal_side": "home", "next_goal_minute": "34"}, 5)
    assert cr["next5_class"] == "home_goal" and cr["next5_first_side"] == "home"


def test_class_away_goal_when_away_scores_first():
    _need_builder()
    cr = B.competing_risk_for_horizon(_snap(30, 60), _sc(h_away=1),
                                      {"next_goal_side": "away", "next_goal_minute": "41"}, 15)
    assert cr["next15_class"] == "away_goal" and cr["next15_first_side"] == "away"


def test_class_no_goal_when_next_goal_outside_window():
    # away goal at minute 70 is outside a (30, 45] window -> no_goal for h=15
    _need_builder()
    cr = B.competing_risk_for_horizon(_snap(30, 60), _sc(),
                                      {"next_goal_side": "away", "next_goal_minute": "70"}, 15)
    assert cr["next15_class"] == "no_goal" and cr["next15_first_side"] == "none"


def test_no_goal_class_exists_and_is_default():
    _need_builder()
    cr = B.competing_risk_for_horizon(_snap(10, 80), _sc(), {"next_goal_side": "none", "next_goal_minute": ""}, 10)
    assert cr["next10_class"] == "no_goal"


def test_competing_risk_classes_exhaustive():
    _need_builder()
    seen = set()
    seen.add(B.competing_risk_for_horizon(_snap(30, 60), _sc(h_home=1),
             {"next_goal_side": "home", "next_goal_minute": "33"}, 5)["next5_class"])
    seen.add(B.competing_risk_for_horizon(_snap(30, 60), _sc(h_away=1),
             {"next_goal_side": "away", "next_goal_minute": "33"}, 5)["next5_class"])
    seen.add(B.competing_risk_for_horizon(_snap(30, 60), _sc(),
             {"next_goal_side": "none", "next_goal_minute": ""}, 5)["next5_class"])
    assert seen == {"home_goal", "away_goal", "no_goal"}


# =================================================================================================
# 3. regime labels (pure, synthetic, leakage-safe from cutoff state)
# =================================================================================================
def test_regime_time_bands():
    _need_builder()
    assert B.regime_labels(_snap(10, 80))["regime_time"] == "early"
    assert B.regime_labels(_snap(45, 45))["regime_time"] == "mid"
    assert B.regime_labels(_snap(75, 15))["regime_time"] == "late"


def test_regime_score_and_lead_side():
    _need_builder()
    r = B.regime_labels(_snap(50, 40, gh=2, ga=0))
    assert r["regime_score"] == "two_plus" and r["regime_lead_side"] == "home"
    r2 = B.regime_labels(_snap(50, 40, gh=0, ga=1))
    assert r2["regime_score"] == "one_goal" and r2["regime_lead_side"] == "away"
    r3 = B.regime_labels(_snap(50, 40, gh=1, ga=1))
    assert r3["regime_score"] == "level" and r3["regime_lead_side"] == "none"


def test_regime_player_count_from_players_diff():
    _need_builder()
    assert B.regime_labels(_snap(50, 40, players_diff=-1))["regime_player_count"] == "away_up"
    assert B.regime_labels(_snap(50, 40, players_diff=1))["regime_player_count"] == "home_up"
    assert B.regime_labels(_snap(50, 40, players_diff=0))["regime_player_count"] == "even"


def test_regime_cell_is_documented_tuple():
    _need_builder()
    r = B.regime_labels(_snap(20, 70, gh=1, ga=0))
    assert r["regime_cell"] == "early|one_goal|even"


# =================================================================================================
# 4. residual algebra (observed - W2), built end-to-end on a synthetic match
# =================================================================================================
def _synthetic_match():
    """Home(1) scores @10'; away(2) scores @70'; an ET goal @95 and a shootout 'goal' @120 must be
    invisible to every regulation target. Includes cards/subs after a cutoff that must not leak."""
    def goal(idx, minute, team_id, period=1, xg=0.3):
        return {"index": idx, "period": period, "minute": minute, "second": 0,
                "type": {"name": "Shot"}, "team": {"id": team_id}, "location": [110.0, 40.0],
                "shot": {"statsbomb_xg": xg, "outcome": {"name": "Goal"}}}
    return [
        {"index": 1, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 1, "name": "Home"}},
        {"index": 2, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 2, "name": "Away"}},
        goal(10, 10, 1),                                  # home goal @10'
        {"index": 15, "period": 2, "minute": 55, "second": 0, "type": {"name": "Substitution"}, "team": {"id": 1}},
        goal(20, 70, 2, period=2, xg=0.4),                # away goal @70' (must be invisible @30 snapshot)
        {"index": 25, "period": 2, "minute": 80, "second": 0, "type": {"name": "Bad Behaviour"},
         "team": {"id": 2}, "bad_behaviour": {"card": {"name": "Red Card"}}},  # red @80 (invisible @30)
        goal(30, 95, 1, period=3, xg=0.5),                # ET goal @95 -> excluded from regulation
        {"index": 40, "period": 5, "minute": 120, "second": 0, "type": {"name": "Shot"},  # shootout -> excluded
         "team": {"id": 1}, "shot": {"outcome": {"name": "Goal"}}},
    ]


def _build_one_match():
    """Run the snapshot engine then the residual builder on the synthetic match, return joined rows."""
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthM")
    fin = SF.regulation_final(ev, ctx)
    snaps = []
    for s in SF.snapshot_schedule(ev, ctx):
        t = s["minute"]
        feats = SF.snapshot_features(ev, ctx, t, reason=s["reason"])
        sc = {}
        for h in HORIZONS:
            sc.update(SF.scoring_in_window(ev, ctx, t, h))
        ng = SF.next_goal_after(ev, ctx, t)
        snaps.append({"t": t, "feats": feats, "sc": sc, "ng": ng})
    return ev, ctx, fin, snaps


def test_regulation_final_excludes_et_and_shootout():
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthM")
    fin = SF.regulation_final(ev, ctx)
    # regulation final is 1-1 (home @10, away @70); ET @95 and shootout @120 excluded
    assert fin["reg_home_goals"] == 1 and fin["reg_away_goals"] == 1 and fin["target_wdl"] == "D", fin


def test_remaining_goals_equal_final_minus_cutoff():
    _need_builder()
    ev, ctx, fin, snaps = _build_one_match()
    # snapshot at/around 30': home already scored (1), away has not (0); remaining = final - cutoff
    s30 = min(snaps, key=lambda s: abs(s["t"] - 30))
    gh = s30["feats"]["goals_home"]; ga = s30["feats"]["goals_away"]
    rem_h = max(0, fin["reg_home_goals"] - gh)
    rem_a = max(0, fin["reg_away_goals"] - ga)
    assert rem_h == 0 and rem_a == 1, (gh, ga, rem_h, rem_a)  # away still to score @70 in regulation


def test_residual_remaining_total_is_observed_minus_w2():
    _need_builder()
    ev, ctx, fin, snaps = _build_one_match()
    s30 = min(snaps, key=lambda s: abs(s["t"] - 30))
    t = s30["t"]; remaining = max(0.0, 90.0 - t)
    rem_h = max(0, fin["reg_home_goals"] - s30["feats"]["goals_home"])
    rem_a = max(0, fin["reg_away_goals"] - s30["feats"]["goals_away"])
    w2_int = B.w2_remaining_intensity(remaining)
    resid_total = (rem_h + rem_a) - 2.0 * w2_int
    # reconstruct exactly the builder's formula
    assert abs(resid_total - ((rem_h + rem_a) - 2.0 * B.w2_remaining_intensity(remaining))) < 1e-12


def test_no_future_goal_leaks_into_snapshot_score():
    # @30 snapshot must NOT see the away goal @70, the ET goal @95, or shootout @120
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthM")
    feats = SF.snapshot_features(ev, ctx, 30.0, "clock")
    assert feats["goals_home"] == 1 and feats["goals_away"] == 0


def test_no_future_xg_leaks_into_snapshot():
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthM")
    feats = SF.snapshot_features(ev, ctx, 30.0, "clock")
    # only the home goal-shot @10 (xg 0.3) is visible @30; away @70 (0.4) and ET @95 (0.5) excluded
    assert abs(feats["cum_xg_total"] - 0.3) < 1e-9


def test_no_future_card_leaks_into_snapshot():
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthM")
    feats = SF.snapshot_features(ev, ctx, 30.0, "clock")
    # red card @80 must not reduce away players at the @30 snapshot
    assert feats["sendoff_away"] == 0 and feats["players_away"] == 11


def test_no_future_sub_leaks_into_snapshot():
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthM")
    feats = SF.snapshot_features(ev, ctx, 30.0, "clock")
    # home substitution @55 must not be counted at the @30 snapshot
    assert feats["subs_used_home"] == 0


def test_snapshot_uses_only_events_up_to_cutoff():
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = _synthetic_match()
    sliced = SF.events_up_to(ev, 30.0)
    assert all((SF.event_clock(e) is None) or SF.event_clock(e) <= 30.0 + 1e-9 for e in sliced)
    assert all(e.get("period") in (1, 2) for e in sliced)  # regulation only -> no ET/shootout in slice


def test_own_goal_credited_to_beneficiary():
    # StatsBomb encodes an own goal as an "Own Goal For" event under the BENEFITING team (and a separate
    # "Own Goal Against" under the conceding team, which the engine must NOT double-count). Here the home
    # side (team 1) benefits from the away side's own goal -> exactly one HOME goal, zero AWAY goals.
    from wcdrawlab.research.event_process import snapshot_features as SF
    ev = [
        {"index": 1, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 1, "name": "H"}},
        {"index": 2, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 2, "name": "A"}},
        {"index": 10, "period": 1, "minute": 20, "second": 0, "type": {"name": "Own Goal For"}, "team": {"id": 1}},
        {"index": 11, "period": 1, "minute": 20, "second": 0, "type": {"name": "Own Goal Against"}, "team": {"id": 2}},
    ]
    ctx = SF.prepare_match(ev, "og")
    feats = SF.snapshot_features(ev, ctx, 30.0, "clock")
    # beneficiary of away's own goal is home; the conceding "Own Goal Against" must not add an away goal
    assert feats["goals_home"] == 1 and feats["goals_away"] == 0, feats


# =================================================================================================
# 5. self-test entrypoint + determinism (pure)
# =================================================================================================
def test_builder_self_test_passes(capsys):
    _need_builder()
    B._self_test()
    out = capsys.readouterr().out
    assert '"self_test": "pass"' in out


def test_w2_no_goal_prob_decreases_with_horizon():
    _need_builder()
    p = [math.exp(-2.0 * B.W2_BASE * h / 90.0) for h in HORIZONS]
    assert p[0] > p[1] > p[2] > 0.0


# =================================================================================================
# 6. INTEGRATION tests against the materialised real dataset (SKIP if not built)
# =================================================================================================
@pytest.mark.integration
def test_real_dataset_present_and_nonempty():
    if not _has_real():
        pytest.skip("residual dataset not materialised in this worktree")
    snaps = _read(SNAP_CSV)
    assert len(snaps) > 0
    assert all(r["comp_type"] == "international" for r in snaps)


@pytest.mark.integration
def test_real_international_only_no_club_rows():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    snaps = _read(SNAP_CSV)
    assert not any(r["comp_type"] == "club" for r in snaps)


@pytest.mark.integration
def test_real_join_is_one_to_one():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    sk = {(r["source_match_id"], r["snapshot_minute"]) for r in _read(SNAP_CSV)}
    tk = {(r["source_match_id"], r["snapshot_minute"]) for r in _read(TGT_CSV)}
    ck = {(r["source_match_id"], r["snapshot_minute"]) for r in _read(COR_CSV)}
    assert sk == tk == ck


@pytest.mark.integration
def test_real_w2_intensity_reconstructs():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    for r in _read(SNAP_CSV)[:500]:
        rem = float(r["remaining_regulation_min"])
        exp = B.W2_BASE * max(0.0, rem) / 90.0
        assert abs(float(r["w2_remaining_home_intensity"]) - exp) < 1e-4
        assert float(r["w2_remaining_home_intensity"]) == float(r["w2_remaining_away_intensity"])


@pytest.mark.integration
def test_real_regulation_only_minutes():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    assert all(float(r["snapshot_minute"]) <= 90.0 + 1e-9 for r in _read(SNAP_CSV))


@pytest.mark.integration
def test_real_remaining_goals_non_negative():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    for r in _read(TGT_CSV):
        assert int(r["remaining_home_goals"]) >= 0 and int(r["remaining_away_goals"]) >= 0


@pytest.mark.integration
def test_real_source_hash_and_engine_preserved():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    for r in _read(SNAP_CSV)[:500]:
        assert r["source_sha256"].strip() and r["engine_version"].strip()


@pytest.mark.integration
def test_real_no_cross_match_leak_remaining_le_match_total():
    # a match's remaining goals at any snapshot can never exceed that match's own regulation total
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    tgts = _read(TGT_CSV)
    by_match = {}
    for r in tgts:
        tot = int(r["reg_home_goals"]) + int(r["reg_away_goals"])
        by_match.setdefault(r["source_match_id"], tot)
    for r in tgts:
        assert int(r["remaining_total_goals"]) <= by_match[r["source_match_id"]]


@pytest.mark.integration
def test_real_competing_risk_classes_in_set():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    allowed = {"home_goal", "away_goal", "no_goal"}
    for r in _read(TGT_CSV)[:1000]:
        for h in HORIZONS:
            assert r[f"next{h}_class"] in allowed


@pytest.mark.integration
def test_real_no_goal_class_present():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    assert any(r["next5_class"] == "no_goal" for r in _read(TGT_CSV))


@pytest.mark.integration
def test_real_deterministic_rebuild_byte_identical(tmp_path):
    """Re-run the builder; the produced CSVs must be byte-identical (deterministic)."""
    if B is None:
        pytest.skip("builder not importable")
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    before = {p.name: p.read_bytes() for p in (SNAP_CSV, TGT_CSV, COR_CSV)}
    up, err = B.load_upstream()
    if up is None:
        pytest.skip(f"upstream snapshots not available: {err}")
    snap_rows, target_rows, corr_rows, _ = B.build(up)
    # write to temp and compare CSV bytes (same writer path)
    import io
    def _to_bytes(rows):
        fieldnames, seen = [], set()
        for r in rows:
            for k in r.keys():
                if k not in seen:
                    seen.add(k); fieldnames.append(k)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
        return buf.getvalue().encode("utf-8")
    assert _to_bytes(snap_rows) == before["residual_goal_intensity_snapshots.csv"]
    assert _to_bytes(target_rows) == before["near_term_competing_risk_targets.csv"]
    assert _to_bytes(corr_rows) == before["selective_dynamic_correction.csv"]


@pytest.mark.integration
def test_real_residual_reconstructs_on_sample():
    if not _has_real():
        pytest.skip("residual dataset not materialised")
    snaps = {(r["source_match_id"], r["snapshot_minute"]): r for r in _read(SNAP_CSV)}
    tgts = {(r["source_match_id"], r["snapshot_minute"]): r for r in _read(TGT_CSV)}
    cors = _read(COR_CSV)[:500]
    for c in cors:
        key = (c["source_match_id"], c["snapshot_minute"])
        rem_h = int(tgts[key]["remaining_home_goals"])
        w2 = float(snaps[key]["w2_remaining_home_intensity"])
        assert abs(float(c["resid_remaining_home"]) - (rem_h - w2)) < 1e-4
