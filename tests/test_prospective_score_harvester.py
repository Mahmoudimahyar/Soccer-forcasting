"""Phase 4 — deterministic tests for the independent idempotent harvester."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "prospective_harvest"))
from prospective_score_harvester_v1 import (  # noqa: E402
    SCORER_VERSION, build_scored_rows, model_metrics, prediction_id, result_hash, _rps, _onehot,
)

KO = "2026-06-25T00:00:00+00:00"
SS = "2026-06-20T00:00:00+00:00"
PT = "2026-06-20T00:05:00+00:00"


def _primary(fix="M1", models=("M1_B1", "M2_market"), pa=0.5, pdr=0.3, pb=0.2, ss=SS, pt=PT, ko=KO):
    rows = [{"canonical_fixture_id": fix, "model_version": m, "selected_window": "baseline",
             "selected_source_snapshot_timestamp": ss, "prediction_timestamp": pt, "kickoff_utc": ko,
             "p_team_a_win": pa, "p_draw": pdr, "p_team_b_win": pb} for m in models]
    return pd.DataFrame(rows)


def _results(fix="M1", outcome="A", hg=2, ag=0, status="FINISHED", recon="verified_final"):
    return pd.DataFrame([{"canonical_fixture_id": fix, "reconciliation_status": recon,
                          "final_1x2_outcome_team_a_orientation": outcome, "home_regulation_goals": hg,
                          "away_regulation_goals": ag, "final_status": status, "source_provider": "football_data_org"}])


def _append(prior, new):
    if prior is None:
        return new.drop_duplicates("score_key", keep="first")
    return pd.concat([prior, new]).drop_duplicates("score_key", keep="first")


def test_scores_verified_final():
    scored, excl = build_scored_rows(_primary(), _results(), "t0")
    assert len(scored) == 2 and excl.empty
    assert set(scored["outcome"]) == {"A"}


def test_idempotent_rerun():
    scored, _ = build_scored_rows(_primary(), _results(), "t0")
    merged = _append(None, scored)
    merged2 = _append(merged, scored)  # identical second run
    assert len(merged2) == len(merged)


def test_first_write_wins_on_same_key():
    a, _ = build_scored_rows(_primary(pa=0.5, pdr=0.3, pb=0.2), _results(), "t0")
    b, _ = build_scored_rows(_primary(pa=0.1, pdr=0.1, pb=0.8), _results(), "t1")  # same ids, diff prob
    merged = _append(_append(None, a), b)
    # same score_key -> original probability retained
    row = merged[merged.model_version == "M1_B1"].iloc[0]
    assert abs(row.p_team_a_win - 0.5) < 1e-9


def test_result_correction_appends_not_overwrites():
    a, _ = build_scored_rows(_primary(), _results(hg=2, ag=0), "t0")
    b, _ = build_scored_rows(_primary(), _results(hg=3, ag=0, outcome="A"), "t1")  # corrected score -> new rh
    merged = _append(_append(None, a), b)
    keys = merged[merged.model_version == "M1_B1"]
    assert len(keys) == 2  # prior preserved + superseding appended
    assert not merged.duplicated("score_key").any()


def test_no_post_kickoff_prediction_scored():
    p = _primary(pt="2026-06-25T01:00:00+00:00")  # after kickoff
    scored, excl = build_scored_rows(p, _results(), "t0")
    assert scored.empty
    assert set(excl["reason"]) == {"not_pre_kickoff"}


def test_no_future_market_snapshot():
    p = _primary(ss="2026-06-24T00:00:00+00:00", pt="2026-06-20T00:00:00+00:00")  # snapshot after prediction
    scored, excl = build_scored_rows(p, _results(), "t0")
    assert scored.empty
    assert set(excl["reason"]) == {"market_snapshot_after_prediction"}


def test_no_score_without_verified_final():
    scored, excl = build_scored_rows(_primary(), _results(recon="awaiting_final"), "t0")
    assert scored.empty
    assert set(excl["reason"]) == {"no_verified_final_result"}


def test_invalid_simplex_excluded():
    scored, excl = build_scored_rows(_primary(pa=0.9, pdr=0.9, pb=0.9), _results(), "t0")
    assert scored.empty
    assert "invalid_simplex" in set(excl["reason"])


def test_model_identity_and_match_grouping():
    p = pd.concat([_primary(fix="M1"), _primary(fix="M2")], ignore_index=True)
    res = pd.concat([_results(fix="M1", outcome="A"), _results(fix="M2", outcome="D", hg=1, ag=1)], ignore_index=True)
    scored, _ = build_scored_rows(p, res, "t0")
    m = model_metrics(scored, "primary")
    by = {r["model"]: r for r in m}
    assert by["M1_B1"]["n_fixtures"] == 2  # two fixtures grouped per model
    assert not scored.duplicated(["canonical_fixture_id", "model_version"]).any()  # no double count


def test_metrics_nonempty_when_eligible():
    scored, _ = build_scored_rows(_primary(), _results(), "t0")
    m = model_metrics(scored, "primary")
    assert len(m) == 2 and all("rps" in r for r in m)


def test_empty_cohort_explicit_no_eligible_state():
    scored, excl = build_scored_rows(_primary(), _results(recon="awaiting_final"), "t0")
    assert scored.empty
    assert model_metrics(scored, "primary") == []  # explicit empty, not a false success


def test_id_helpers_stable():
    assert prediction_id("M1", "M1_B1", SS, PT) == prediction_id("M1", "M1_B1", SS, PT)
    assert result_hash("M1", 2, 0, "FINISHED") != result_hash("M1", 3, 0, "FINISHED")


def test_rps_perfect_and_worst():
    y = _onehot(["A"])
    assert _rps(np.array([[1.0, 0.0, 0.0]]), y) == 0.0
    assert _rps(np.array([[0.0, 0.0, 1.0]]), y) == 1.0
