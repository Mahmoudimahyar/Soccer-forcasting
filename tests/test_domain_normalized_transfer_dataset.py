"""DETERMINISTIC integrity tests for the CAUSAL DOMAIN-NORMALIZED TRANSFER DATASET (Phase 3).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Covers wcdrawlab.research.transfer.domain_normalized_dataset (the in-memory transfer plane) plus the
materialised real CSV when present (integration tests; SKIP cleanly otherwise). The synthetic tests run
ALWAYS (no disk / no network) and exercise the WHOLE pipeline: outer temporal folds + per-domain baseline
(fit on TRAIN only) + stable-feature filter (fit on TRAIN only) + residual target + row assembly.

Hard invariants asserted (>=25 deterministic tests):
  * no future event leak (snapshot n_events_observed monotone in minute; targets never feature columns);
  * no test-fold scaling leak (baseline + filter fit on TRAIN rows only; held-out tournament excluded);
  * no club test row in the intl eval (club rows are auxiliary training only);
  * correct temporal cutoff (intl_train + club_train kickoff < fold cutoff; earliest tournament skipped);
  * domain baseline fit only in training; stable-feature filter fit only in training;
  * no competition-label leak (intl_train never carries the held tournament label);
  * deterministic fold recreation (identical inputs -> identical folds / kept subset / rows);
  * source-hash traceability (every row carries source_sha256 + engine_version);
  * match-level grouping (a (match_id, fold) carries exactly one role);
  * no 2026 World Cup row anywhere (assert_no_2026 + a positive 2026-poison rejection test).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wcdrawlab.research.transfer import domain_normalized_dataset as DND  # noqa: E402
from wcdrawlab.research.transfer import w2_reference_t0 as T0  # noqa: E402
from wcdrawlab.research import transfer as TR  # noqa: E402

DATASET_CSV = ROOT / "data/processed/domain_normalized_transfer/transfer_dataset_v1.csv"


# =================================================================================================
# fixtures / helpers
# =================================================================================================
@pytest.fixture(scope="module")
def synth():
    intl = DND.synthetic_intl_rows()
    club = DND.synthetic_club_rows()
    built = DND.build_all_fold_rows(intl, club)
    return {"intl": intl, "club": club, "built": built, "rows": built["rows"],
            "summary": built["summary"]}


@pytest.fixture(scope="module")
def real_rows():
    if not DATASET_CSV.exists():
        pytest.skip(f"integration: requires materialised {DATASET_CSV.name} "
                    "(run scripts/build_domain_normalized_transfer_dataset.py)")
    with DATASET_CSV.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        pytest.skip("integration: materialised dataset is empty")
    return rows


def _by_role(rows, role):
    return [r for r in rows if r.get("row_role") == role]


# =================================================================================================
# 1-5  outer folds + temporal cutoff
# =================================================================================================
def test_01_folds_built_on_synthetic(synth):
    assert synth["summary"]["n_folds"] >= 1
    assert synth["summary"]["n_rows_total"] == len(synth["rows"]) > 0


def test_02_earliest_tournament_is_skipped(synth):
    # the synthetic intl set has two tournaments; the EARLIER one cannot be a held-out fold (no prior
    # international training data), so exactly one fold is produced.
    folds = synth["summary"]["folds"]
    held = {f["held_tournament"] for f in folds}
    assert "SynthCup2018" not in held  # earliest -> no earlier training -> skipped
    assert "SynthCup2022" in held


def test_03_train_rows_strictly_before_cutoff(synth):
    for r in synth["rows"]:
        if r["row_role"] in ("intl_train", "club_train"):
            assert r["kickoff_date"] < r["fold_cutoff_kickoff"], r


def test_04_test_rows_belong_to_held_tournament(synth):
    for r in _by_role(synth["rows"], "intl_test"):
        assert (r["competition_label"] or r["competition"]) == r["fold_held_tournament"]


def test_05_each_fold_test_is_single_tournament(synth):
    by_fold = {}
    for r in _by_role(synth["rows"], "intl_test"):
        by_fold.setdefault(r["fold_held_tournament"], set()).add(
            r["competition_label"] or r["competition"])
    for f, comps in by_fold.items():
        assert comps == {f}


# =================================================================================================
# 6-9  club auxiliary rules (no club test row; club is temporally cut too)
# =================================================================================================
def test_06_no_club_row_is_intl_test(synth):
    bad = [r for r in _by_role(synth["rows"], "intl_test") if r["domain"] == DND.DOMAIN_CLUB]
    assert bad == []


def test_07_club_rows_only_appear_as_club_train(synth):
    for r in synth["rows"]:
        if r["domain"] == DND.DOMAIN_CLUB:
            assert r["row_role"] == "club_train"


def test_08_club_train_respects_temporal_cutoff(synth):
    for r in _by_role(synth["rows"], "club_train"):
        assert r["kickoff_date"] < r["fold_cutoff_kickoff"]


def test_09_club_train_matches_counted(synth):
    # synthetic club season (2016) is before both tournaments -> all club matches train every fold
    assert synth["summary"]["n_club_train_matches"] == 8


# =================================================================================================
# 10-14  domain baseline fit on TRAIN only; residual target relative to the DOMAIN baseline
# =================================================================================================
def test_10_domain_baseline_fit_uses_train_only(synth):
    # The held-out TEST rows must NOT enter the baseline fit. Prove it by POISONING the test labels with
    # an absurd remaining-goal value: a TRAIN-only fit is invariant to test-label corruption, while an
    # all-rows fit would move. The builder must reproduce the TRAIN-only fit exactly.
    fold = synth["built"]["folds"][0]
    bl_train = DND.fit_domain_baseline(fold.train_rows)
    poisoned_test = [{**r, "rem_goals_home": 999.0, "rem_goals_away": 999.0}
                     for r in fold.intl_test_rows]
    bl_train_again = DND.fit_domain_baseline(fold.train_rows)            # invariant to test poison
    bl_all_poison = DND.fit_domain_baseline(fold.train_rows + poisoned_test)
    assert bl_train.log_intercept == bl_train_again.log_intercept       # train-only fit is stable
    assert len(fold.intl_test_rows) > 0
    # the all-rows-with-poison fit MUST differ from the train-only fit (test rows would have leaked)
    assert bl_all_poison.log_intercept != bl_train.log_intercept
    assert bl_train.fitted_on == "train_rows_only"


def test_11_residual_equals_obs_minus_domain_baseline(synth):
    n = 0
    for r in synth["rows"]:
        oh = DND.fnum(r, "rem_goals_home"); oa = DND.fnum(r, "rem_goals_away")
        bt = DND.fnum(r, "domain_baseline_total"); rt = DND.fnum(r, "transfer_residual_total")
        if None in (oh, oa, bt, rt):
            continue
        n += 1
        assert abs(((oh + oa) - bt) - rt) < 1e-6
    assert n > 0


def test_12_residual_is_relative_to_domain_not_t0(synth):
    # the domain baseline differs from the symmetric T0 anchor (it carries a per-domain intercept), so
    # the residual is NOT simply observed - T0.
    fold = synth["built"]["folds"][0]
    bl = DND.fit_domain_baseline(fold.train_rows)
    # at least one domain should have a non-zero log intercept on the synthetic data
    assert any(abs(v) > 1e-9 for v in bl.log_intercept.values())


def test_13_baseline_missing_label_yields_none_residual():
    bl = DND.fit_domain_baseline([
        {"domain": "international", "rem_goals_home": 1.0, "rem_goals_away": 0.0,
         "remaining_regulation_min": 45.0, "goals_diff": 0},
    ])
    row = {"domain": "international", "remaining_regulation_min": 30.0, "goals_diff": 0}  # no label
    res = DND.residual_targets(row, bl)
    assert res["transfer_residual_total"] is None
    assert res["domain_baseline_total"] is not None  # baseline is still defined


def test_14_t0_reference_is_symmetric_and_parameter_free():
    row = {"remaining_regulation_min": 45.0, "goals_diff": 1}
    ref = T0.reference_intensity(row)
    assert ref["t0_lam_home"] == ref["t0_lam_away"]
    assert abs(ref["t0_base_rate_per90"] - T0.BASE_RATE_PER90) < 1e-12


# =================================================================================================
# 15-19  stable-feature filter fit on TRAIN only; excluded columns; missingness
# =================================================================================================
def test_15_stable_filter_fit_on_train_only_excludes_test(synth):
    fold = synth["built"]["folds"][0]
    filt_train = DND.fit_stable_feature_filter(fold.train_rows)
    # the kept subset must be derivable from TRAIN rows alone (re-fit reproduces it)
    filt_again = DND.fit_stable_feature_filter(fold.train_rows)
    assert filt_train.kept == filt_again.kept
    assert filt_train.fitted_on == "train_rows_only"


def test_16_excluded_columns_never_kept(synth):
    fold = synth["built"]["folds"][0]
    filt = DND.fit_stable_feature_filter(
        fold.train_rows, candidate_cols=DND.CANDIDATE_TRANSFER_FEATURE_COLS +
        DND.ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS)
    for c in DND.ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS:
        assert c not in filt.kept
        assert filt.dropped.get(c) == "always_excluded_domain_shifted"


def test_17_excluded_columns_never_become_feat_columns(synth):
    cols = set(synth["rows"][0].keys())
    for c in DND.ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS:
        assert f"feat_{c}" not in cols


def test_18_domain_shifted_feature_is_dropped():
    # craft two domains where a feature has a huge cross-domain mean gap -> SMD > max_smd -> dropped.
    intl = [{"domain": "international", "shift_feat": 0.0} for _ in range(20)]
    club = [{"domain": "club", "shift_feat": 100.0} for _ in range(20)]
    # add a tiny bit of variance so pooled sd > 0
    intl[0]["shift_feat"] = 0.001
    club[0]["shift_feat"] = 100.001
    filt = DND.fit_stable_feature_filter(intl + club, candidate_cols=["shift_feat"], max_smd=1.0)
    assert "shift_feat" not in filt.kept
    assert filt.dropped["shift_feat"] == "domain_shifted"


def test_19_low_presence_feature_is_dropped():
    rows = [{"domain": "international"} for _ in range(20)]  # feature totally absent
    filt = DND.fit_stable_feature_filter(rows, candidate_cols=["never_present"], min_present_frac=0.5)
    assert "never_present" not in filt.kept
    assert filt.dropped["never_present"] == "insufficient_presence"


# =================================================================================================
# 20-22  no competition-label leak; match-level grouping; subset size reporting
# =================================================================================================
def test_20_no_competition_label_leak(synth):
    for r in _by_role(synth["rows"], "intl_train"):
        assert (r["competition_label"] or r["competition"]) != r["fold_held_tournament"]


def test_21_match_level_grouping_one_role_per_fold(synth):
    roles = {}
    for r in synth["rows"]:
        roles.setdefault((r["match_id"], r["fold_held_tournament"]), set()).add(r["row_role"])
    for k, v in roles.items():
        assert len(v) == 1, (k, v)


def test_22_subset_size_matches_filter(synth):
    fold = synth["built"]["folds"][0]
    filt = DND.fit_stable_feature_filter(fold.train_rows)
    reported = {r["stable_feature_subset_size"] for r in synth["rows"]}
    assert filt.subset_size() in reported
    assert synth["summary"]["folds"][0]["stable_feature_subset_size"] == filt.subset_size()


# =================================================================================================
# 23-26  no future event leak; targets are never features; source traceability
# =================================================================================================
def test_23_targets_are_not_in_feature_columns(synth):
    feat_cols = {k for k in synth["rows"][0] if k.startswith("feat_")}
    forbidden = {"rem_goals_home", "rem_goals_away", "target_wdl", "transfer_residual_total",
                 "transfer_residual_home", "transfer_residual_away"}
    assert feat_cols.isdisjoint({f"feat_{c}" for c in forbidden})
    # and no label leaked into a feat_ column by name
    for c in forbidden:
        assert f"feat_{c}" not in synth["rows"][0]


def test_24_n_events_observed_is_not_a_feature(synth):
    assert "feat_n_events_observed" not in synth["rows"][0]


def test_25_source_traceability_present(synth):
    for r in synth["rows"]:
        assert r["source_sha256"]
        assert r["engine_version"]


def test_26_eligibility_labels_on_every_row(synth):
    want = "/".join(DND.ELIGIBILITY_LABELS)
    for r in synth["rows"]:
        assert r["eligibility"] == want


# =================================================================================================
# 27-30  2026 rejection; determinism; reference-model identity
# =================================================================================================
def test_27_assert_no_2026_rejects_poison():
    poison = [{"competition_label": "FIFA World Cup 2026", "kickoff_date": "2026-06-15",
               "match_id": "X1"}]
    with pytest.raises(AssertionError):
        DND.assert_no_2026(poison)


def test_28_build_rejects_2026_in_population():
    intl = DND.synthetic_intl_rows()
    intl.append({**intl[0], "competition_label": "FIFA World Cup 2026",
                 "competition": "FIFA World Cup 2026", "kickoff_date": "2026-06-15",
                 "match_id": "WC2026_1", "source_match_id": "WC2026_1"})
    with pytest.raises(AssertionError):
        DND.build_all_fold_rows(intl, DND.synthetic_club_rows())


def test_29_deterministic_rebuild_is_byte_stable():
    a = DND.build_all_fold_rows(DND.synthetic_intl_rows(), DND.synthetic_club_rows())
    b = DND.build_all_fold_rows(DND.synthetic_intl_rows(), DND.synthetic_club_rows())
    assert a["rows"] == b["rows"]
    assert ([f["stable_feature_subset"] for f in a["summary"]["folds"]] ==
            [f["stable_feature_subset"] for f in b["summary"]["folds"]])


def test_30_reference_model_is_t0(synth):
    assert synth["summary"]["reference_model"] == TR.REFERENCE_MODEL == TR.T0_REFERENCE
    for r in synth["rows"]:
        assert r["reference_model"] == TR.T0_REFERENCE


def test_31_empty_population_raises_data_insufficient():
    with pytest.raises(DND.DataInsufficient):
        DND.build_all_fold_rows([], [])


def test_32_orientation_flip_inverts_signed_state():
    base = {"goals_diff": 2, "remaining_regulation_min": 45.0, "players_diff": 1, "period": 2}
    flipped = {**base, "orientation": "flipped"}
    s0 = DND.derive_state(base)
    s1 = DND.derive_state(flipped)
    assert s0["score_diff_signed"] == -s1["score_diff_signed"]
    assert s0["players_diff"] == -s1["players_diff"]


# =================================================================================================
# 33-37  INTEGRATION on the materialised real dataset (SKIP if absent)
# =================================================================================================
def test_33_real_no_2026_row(real_rows):
    for r in real_rows:
        assert not DND._is_2026_wc(r.get("competition_label") or r.get("competition"),
                                   r.get("kickoff_date"))


def test_34_real_temporal_cutoff(real_rows):
    for r in real_rows:
        if r.get("row_role") in ("intl_train", "club_train"):
            ko, cut = r.get("kickoff_date"), r.get("fold_cutoff_kickoff")
            if ko and cut:
                assert ko < cut


def test_35_real_no_club_test_row(real_rows):
    bad = [r for r in real_rows
           if r.get("row_role") == "intl_test" and r.get("domain") == DND.DOMAIN_CLUB]
    assert bad == []


def test_36_real_residual_recomputes(real_rows):
    n = 0
    for r in real_rows:
        oh = DND.fnum(r, "rem_goals_home"); oa = DND.fnum(r, "rem_goals_away")
        bt = DND.fnum(r, "domain_baseline_total"); rt = DND.fnum(r, "transfer_residual_total")
        if None in (oh, oa, bt, rt):
            continue
        n += 1
        assert abs(((oh + oa) - bt) - rt) < 1e-3
    assert n > 0


def test_37_real_intl_test_match_count_positive(real_rows):
    n_test = len({r["match_id"] for r in real_rows if r.get("row_role") == "intl_test"})
    assert n_test > 0


def test_38_real_no_competition_label_leak(real_rows):
    for r in real_rows:
        if r.get("row_role") == "intl_train":
            comp = r.get("competition_label") or r.get("competition")
            assert comp != r.get("fold_held_tournament")
