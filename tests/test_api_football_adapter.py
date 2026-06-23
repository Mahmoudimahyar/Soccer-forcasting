"""Tests for the read-only API-Football adapter. Mock transport only; never calls a real API."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.operations.api_football_adapter import (  # noqa: E402
    ApiFootballReadOnly, EndpointNotAllowed, QuotaExceeded)

FAKE_KEY = "FAKEKEY_should_never_be_logged_0123456789"


def _mock(records):
    def transport(url, headers, params):
        records.append({"url": url, "headers": headers, "params": params})
        return 200, {"response": [{"ok": 1}], "errors": []}
    return transport


def _adapter(monkeypatch, tmp_path, **kw):
    monkeypatch.setenv("API_FOOTBALL_KEY", FAKE_KEY)
    clock = {"t": 0.0}
    slept = []
    a = ApiFootballReadOnly(raw_dir=tmp_path, clock=lambda: clock["t"],
                            sleep=lambda s: (slept.append(s), clock.__setitem__("t", clock["t"] + s)),
                            **kw)
    return a, clock, slept


def test_rejects_non_allowlisted_endpoint(monkeypatch, tmp_path):
    a, _, _ = _adapter(monkeypatch, tmp_path, transport=_mock([]))
    with pytest.raises(EndpointNotAllowed):
        a.get("/odds")  # not read-only allowlisted
    with pytest.raises(EndpointNotAllowed):
        a.get("/fixtures/lineups/delete")


def test_budget_and_reserve_enforced(monkeypatch, tmp_path):
    a, _, _ = _adapter(monkeypatch, tmp_path, daily_budget=3, reserve=1, min_interval_s=0,
                       transport=_mock([]))
    assert a.remaining_budget() == 2
    a.get("/status"); a.get("/status")
    assert a.remaining_budget() == 0
    with pytest.raises(QuotaExceeded):
        a.get("/status")


def test_rate_limit_sleeps_between_requests(monkeypatch, tmp_path):
    a, clock, slept = _adapter(monkeypatch, tmp_path, min_interval_s=5.0, transport=_mock([]))
    a.get("/status")            # first: no sleep
    assert slept == []
    a.get("/fixtures", {"league": 1})   # second immediately -> must sleep ~5s
    assert slept and abs(slept[0] - 5.0) < 1e-9


def test_key_never_logged_or_persisted(monkeypatch, tmp_path):
    recs = []
    a, _, _ = _adapter(monkeypatch, tmp_path, min_interval_s=0, transport=_mock(recs))
    a.get("/fixtures", {"league": 1, "season": 2026})
    # transport DID receive the key header (it must, to authenticate)...
    assert recs[0]["headers"]["x-apisports-key"] == FAKE_KEY
    # ...but the key must appear in NO log line and NO persisted file
    assert all(FAKE_KEY not in line for line in a.stats.sanitized_log)
    assert a.stats.sanitized_log == ["GET /fixtures params=['league', 'season']"]
    idx = (tmp_path / "index.jsonl").read_text(encoding="utf-8")
    assert FAKE_KEY not in idx and "x-apisports-key" not in idx


def test_raw_persistence_append_only(monkeypatch, tmp_path):
    a, _, _ = _adapter(monkeypatch, tmp_path, min_interval_s=0, transport=_mock([]))
    a.get("/status"); a.get("/fixtures", {"league": 1})
    lines = (tmp_path / "index.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    env = json.loads(lines[0])
    assert env["source"] == "api_football" and "payload_sha256" in env and env["status_class"] == "2xx"


def test_get_returns_sanitized_result(monkeypatch, tmp_path):
    a, _, _ = _adapter(monkeypatch, tmp_path, min_interval_s=0, transport=_mock([]))
    out = a.get("/status")
    assert out["status_class"] == "2xx" and out["ok"] is True and out["response"] == [{"ok": 1}]
