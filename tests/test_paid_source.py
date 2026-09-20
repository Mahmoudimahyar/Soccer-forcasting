"""Paid-source tests. Sanitized synthetic fixtures only; no real data, no network, no real keys."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
import api_football_reconcile_events as RC  # noqa: E402


def test_safe_config_returns_status_only_never_value(tmp_path):
    env = tmp_path / ".env"
    env.write_text("API_FOOTBALL_KEY=FAKE_should_never_be_returned\nODDS_API_KEY=FAKE2\n", encoding="utf-8")
    status = safe_config.load_paid_keys(root=tmp_path)
    assert status == {"API_FOOTBALL_KEY": "SET", "ODDS_API_KEY": "SET"}
    # the returned dict must NOT contain any key value
    assert "FAKE_should_never_be_returned" not in str(status)
    assert "FAKE2" not in str(status)


def test_safe_config_missing(tmp_path):
    (tmp_path / ".env").write_text("SOMETHING_ELSE=1\n", encoding="utf-8")
    status = safe_config.load_paid_keys(root=tmp_path)
    assert status == {"API_FOOTBALL_KEY": "MISSING", "ODDS_API_KEY": "MISSING"}


def _ev(elapsed, etype, team_id, detail=""):
    return {"time": {"elapsed": elapsed}, "type": etype, "detail": detail, "team": {"id": team_id},
            "player": {"id": 1}}


def test_reconcile_score_basic_and_owngoal():
    fx = {"home": 2, "away": 1, "home_id": 10, "away_id": 20}
    events = [_ev(10, "Goal", 10), _ev(30, "Goal", 20, "Own Goal"),  # own goal by away -> home +1 => home 2
              _ev(70, "Goal", 20)]                                    # away 1
    h, a, ok = RC.reconcile_one(events, fx)
    assert (h, a) == (2, 1) and ok is True


def test_reconcile_excludes_shootout():
    fx = {"home": 1, "away": 1, "home_id": 10, "away_id": 20}
    events = [_ev(10, "Goal", 10), _ev(70, "Goal", 20),
              _ev(125, "Goal", 10, "Penalty"), _ev(125, "Goal", 10, "Penalty")]  # shootout (elapsed>120) excluded
    h, a, ok = RC.reconcile_one(events, fx)
    assert (h, a) == (1, 1)


def test_reconcile_flags_bad_ordering():
    fx = {"home": 1, "away": 0, "home_id": 10, "away_id": 20}
    events = [_ev(70, "Goal", 10), _ev(10, "subst", 10)]  # elapsed goes backwards
    _, _, ok = RC.reconcile_one(events, fx)
    assert ok is False


def test_no_runtime_or_trading_imports_paid_source():
    offenders = []
    for sub in ("runtime", "trading"):
        d = ROOT / "src" / "wcdrawlab" / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            t = f.read_text(encoding="utf-8", errors="ignore")
            if "paid_source" in t or "api_football_historical" in t:
                offenders.append(str(f))
    assert offenders == []
