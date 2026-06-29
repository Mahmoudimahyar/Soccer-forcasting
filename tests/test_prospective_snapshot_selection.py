"""Phase 3 — deterministic tests for the primary one-snapshot-per-fixture selection rule."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "prospective_harvest"))
from select_primary_prospective_snapshots import COMPARED, select_primary  # noqa: E402

FT = pd.DataFrame([{"match_id": "M1", "team_a": "A", "team_b": "B"},
                   {"match_id": "M2", "team_a": "C", "team_b": "D"}])


def _snapshot(mid, ss, ko, with_market=True, pred_ts=None, window="baseline"):
    pred_ts = pred_ts or ss
    rows = []
    for model in (COMPARED if with_market else ["M1_B1"]):
        mk = (0.4, 0.3, 0.3) if (with_market and model != "M1_B1") else (None, None, None)
        rows.append({"match_id": mid, "model_version": model, "prediction_timestamp": pred_ts,
                     "kickoff_utc": ko, "source_snapshot_timestamp": ss, "snapshot_type": window,
                     "p_team_a_win": 0.5, "p_draw": 0.3, "p_team_b_win": 0.2,
                     "p_a_market": mk[0], "p_draw_market": mk[1], "p_b_market": mk[2], "n_books": 8})
    return rows


def test_one_primary_snapshot_per_fixture():
    rows = _snapshot("M1", "2026-06-20T00:00:00+00:00", "2026-06-25T00:00:00+00:00")
    rows += _snapshot("M1", "2026-06-24T00:00:00+00:00", "2026-06-25T00:00:00+00:00", window="T-15")
    primary, excl = select_primary(pd.DataFrame(rows), FT)
    assert excl.empty
    assert primary["canonical_fixture_id"].nunique() == 1
    assert len(primary) == 5  # one row per compared model
    # latest snapshot chosen
    assert set(primary["selected_source_snapshot_timestamp"]) == {"2026-06-24 00:00:00+00:00"}


def test_latest_window_preference():
    rows = _snapshot("M1", "2026-06-20T00:00:00+00:00", "2026-06-25T00:00:00+00:00", window="baseline")
    rows += _snapshot("M1", "2026-06-24T23:00:00+00:00", "2026-06-25T00:00:00+00:00", window="T-15")
    primary, _ = select_primary(pd.DataFrame(rows), FT)
    assert primary["selected_window"].iloc[0] == "T-15"


def test_exclude_when_no_market_snapshot():
    rows = _snapshot("M1", "2026-06-20T00:00:00+00:00", "2026-06-25T00:00:00+00:00", with_market=False)
    primary, excl = select_primary(pd.DataFrame(rows), FT)
    assert primary.empty
    assert excl.iloc[0]["reason"] == "no_common_market_snapshot"


def test_pre_kickoff_required():
    # only snapshot is AFTER kickoff -> excluded
    rows = _snapshot("M1", "2026-06-26T00:00:00+00:00", "2026-06-25T00:00:00+00:00",
                     pred_ts="2026-06-26T00:00:00+00:00")
    primary, excl = select_primary(pd.DataFrame(rows), FT)
    assert primary.empty
    assert excl.iloc[0]["reason"] == "no_common_market_snapshot"


def test_unresolved_identity_excluded():
    rows = _snapshot("UNKNOWN", "2026-06-20T00:00:00+00:00", "2026-06-25T00:00:00+00:00")
    primary, excl = select_primary(pd.DataFrame(rows), FT)
    assert primary.empty
    assert excl.iloc[0]["reason"] == "unresolved_fixture_identity"


def test_deterministic():
    rows = _snapshot("M1", "2026-06-24T00:00:00+00:00", "2026-06-25T00:00:00+00:00")
    p1, _ = select_primary(pd.DataFrame(rows), FT)
    p2, _ = select_primary(pd.DataFrame(rows), FT)
    pd.testing.assert_frame_equal(p1.reset_index(drop=True), p2.reset_index(drop=True))
