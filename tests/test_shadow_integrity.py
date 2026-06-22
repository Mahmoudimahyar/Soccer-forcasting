"""Deterministic tests for live-shadow integrity invariants. No network."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.research import shadow_integrity as si  # noqa: E402


def _good():
    m1 = np.array([0.6, 0.25, 0.15]); m2 = np.array([0.5, 0.3, 0.2])
    rows = []
    base = dict(match_id="MX", kickoff_utc="2026-06-22T18:00:00Z",
                source_snapshot_timestamp="2026-06-22T16:30:00Z",
                prediction_timestamp="2026-06-22T16:30:00Z", snapshot_type="T-90",
                p_a_market=m2[0], p_draw_market=m2[1], p_b_market=m2[2])
    for name, p in [("M1_B1", m1), ("M2_market", m2),
                    ("M3_75_25", 0.75*m1+0.25*m2), ("M4_50_50", 0.5*m1+0.5*m2), ("M5_25_75", 0.25*m1+0.75*m2)]:
        p = p / p.sum()
        rows.append({**base, "model_version": name, "p_team_a_win": p[0], "p_draw": p[1], "p_team_b_win": p[2]})
    return pd.DataFrame(rows)


def test_clean_set_passes_all():
    out = si.run_all(_good())
    assert out["all_ok"], out


def test_detects_duplicate_snapshot():
    df = pd.concat([_good(), _good().iloc[[0]]])  # duplicate one row
    assert si.check_no_duplicate_snapshots(df)[0] is False


def test_detects_post_kickoff_snapshot():
    df = _good(); df.loc[df.index[0], "source_snapshot_timestamp"] = "2026-06-22T18:30:00Z"  # after kickoff
    assert si.check_snapshots_pre_kickoff(df)[0] is False


def test_detects_probs_not_summing():
    df = _good(); df.loc[df.index[0], "p_draw"] = 0.9  # break sum
    assert si.check_probs_sum_to_one(df)[0] is False


def test_detects_blend_weight_drift():
    df = _good()
    # corrupt M3 to a different weight (0.5 instead of 0.75)
    m1 = df[df.model_version == "M1_B1"][["p_team_a_win", "p_draw", "p_team_b_win"]].to_numpy()[0]
    m2 = df[df.model_version == "M2_market"][["p_team_a_win", "p_draw", "p_team_b_win"]].to_numpy()[0]
    bad = 0.5 * m1 + 0.5 * m2; bad = bad / bad.sum()
    idx = df.index[df.model_version == "M3_75_25"][0]
    df.loc[idx, ["p_team_a_win", "p_draw", "p_team_b_win"]] = bad
    assert si.check_blend_weights_frozen(df)[0] is False


def test_detects_bad_novig():
    df = _good(); df.loc[df.index[0], "p_a_market"] = 0.9  # market no longer sums to 1
    assert si.check_novig_sums_to_one(df)[0] is False


def test_duplicate_type_per_match_warning():
    df = _good()
    dup = df.copy(); dup["source_snapshot_timestamp"] = "2026-06-22T16:35:00Z"  # same type, new ts
    both = pd.concat([df, dup])
    ok, viol = si.check_no_duplicate_type_per_match(both)
    assert ok is False and len(viol) >= 1            # detects the double capture
    assert si.check_no_duplicate_type_per_match(df)[0] is True  # clean set: no warning
