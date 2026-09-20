"""Deterministic leakage tests for the xG snapshot join: no future xG, no cross-match leakage, deterministic
aggregation, regulation/extra-time separation, on-target + completeness correctness."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("xgjoin", ROOT / "scripts/join_complete_xg_into_dynamic_snapshots.py")
J = importlib.util.module_from_spec(spec); spec.loader.exec_module(J)


def _ev(minute, team, etype="Shot", xg=None, outcome=None, period=1, index=0):
    e = {"minute": minute, "second": 0, "period": period, "type": {"name": etype},
         "team": {"name": team}, "index": index}
    if etype == "Shot":
        e["shot"] = {"statsbomb_xg": xg, "outcome": {"name": outcome} if outcome else None}
    return e


HOME, AWAY = "Argentina", "Brazil"


def _shots(events):
    from wcdrawlab.ingest import canonical_team_name as c
    return J._shots(events, c(HOME), c(AWAY))


def test_no_future_xg_leakage():
    events = [_ev(20, HOME, xg=0.5, outcome="Goal", index=1), _ev(70, AWAY, xg=0.4, outcome="Saved", index=2)]
    shots, _ = _shots(events)
    f30 = J._feat(shots, 30)
    assert f30["cum_xg_home"] == 0.5 and f30["cum_xg_away"] == 0.0  # the minute-70 shot must NOT enter at t=30
    f80 = J._feat(shots, 80)
    assert round(f80["cum_xg_away"], 5) == 0.4  # now it does


def test_extra_time_excluded_from_regulation():
    events = [_ev(20, HOME, xg=0.5, outcome="Goal", index=1), _ev(100, HOME, xg=0.9, outcome="Goal", period=4, index=2)]
    shots, et = _shots(events)
    assert et == 1                       # the period-4 shot is counted as extra-time, not regulation
    f90 = J._feat(shots, 90)
    assert f90["cum_xg_home"] == 0.5     # ET xG never enters the regulation state


def test_deterministic_aggregation():
    events = [_ev(20, HOME, xg=0.5, outcome="Goal", index=1), _ev(25, AWAY, xg=0.3, outcome="Saved", index=2)]
    shots, _ = _shots(events)
    a = J._feat(shots, 30); b = J._feat(shots, 30)
    assert a == b                        # identical inputs -> identical outputs


def test_no_cross_match_leakage():
    m1 = [_ev(20, HOME, xg=0.5, outcome="Goal", index=1)]
    m2 = [_ev(20, HOME, xg=0.9, outcome="Goal", index=1)]
    s1, _ = _shots(m1); s2, _ = _shots(m2)
    assert J._feat(s1, 30)["cum_xg_home"] == 0.5  # match 1 unaffected by match 2's events
    assert J._feat(s2, 30)["cum_xg_home"] == 0.9


def test_on_target_and_completeness():
    events = [_ev(20, HOME, xg=0.5, outcome="Goal", index=1),       # on target, has xg
              _ev(22, HOME, xg=None, outcome="Off T", index=2)]     # off target, missing xg
    shots, _ = _shots(events)
    f = J._feat(shots, 30)
    assert f["shot_on_target_diff"] == 1               # one on-target shot for home
    assert f["xg_completeness"] == 0.5                 # 1 of 2 shots carried xG
