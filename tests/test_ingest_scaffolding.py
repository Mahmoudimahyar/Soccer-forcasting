"""Tests for read-only ingestion scaffolding. Temp dirs + sanitized fixtures only. No real APIs."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from wcdrawlab.ingestion.raw_store import (  # noqa: E402
    append_raw_snapshot, make_envelope, payload_sha256, RawStoreError,
)
from wcdrawlab.ingestion.validate import validate_envelope, validate_normalized, list_schemas  # noqa: E402
from wcdrawlab.ingestion import health  # noqa: E402
import ingest_dry_run as cli  # noqa: E402


def _env(**over):
    base = dict(
        source_name="local_fixture", provider_endpoint="/demo", match_id="MX1",
        raw_payload={"a": 1}, retrieval_timestamp_utc="2026-06-21T00:00:00Z",
        source_url_or_endpoint="local_fixture://demo.json", ingestion_run_id="run-1",
    )
    base.update(over)
    return make_envelope(**base)


# ---- envelope + hashing ----
def test_payload_hash_is_deterministic_and_order_independent():
    assert payload_sha256({"a": 1, "b": 2}) == payload_sha256({"b": 2, "a": 1})


def test_envelope_has_all_required_fields_and_validates():
    env = _env()
    assert env["raw_payload_hash"] == payload_sha256({"a": 1})
    for f in ["source_name", "provider_endpoint", "retrieval_timestamp_utc", "match_id",
              "source_url_or_endpoint", "raw_payload_hash", "schema_version", "ingestion_run_id",
              "quality_status", "reconciliation_status"]:
        assert f in env
    assert validate_envelope(env) == []


def test_envelope_validation_catches_missing_and_bad_enum():
    env = _env()
    env2 = dict(env); env2["source_name"] = ""
    assert any("source_name" in e for e in validate_envelope(env2))
    with pytest.raises(RawStoreError):
        _env(quality_status="bogus")


# ---- normalized validation ----
def test_normalized_schema_A_valid_and_invalid():
    good = {"match_id": "M1", "kickoff_utc": "2026-06-21T18:00:00Z", "tournament": "WC2026",
            "team_a": "A", "team_b": "B", "status": "scheduled"}
    assert validate_normalized("A_fixtures_match_identity", good) == []
    bad = {"tournament": "WC2026", "team_a": "A"}  # missing pk match_id + required kickoff/team_b
    errs = validate_normalized("A_fixtures_match_identity", bad)
    assert any("match_id" in e for e in errs)
    bad_enum = dict(good); bad_enum["status"] = "weird"
    assert any("status" in e for e in validate_normalized("A_fixtures_match_identity", bad_enum))


def test_unknown_schema_key_errors():
    assert validate_normalized("ZZ_nope", {}) and "unknown schema_key" in validate_normalized("ZZ_nope", {})[0]
    assert "A_fixtures_match_identity" in list_schemas()


# ---- append-only immutable raw store ----
def test_append_only_immutable_and_idempotent(tmp_path):
    env = _env(raw_payload={"x": 1})
    r1 = append_raw_snapshot(env, {"x": 1}, tmp_path)
    assert r1["wrote"] is True
    p = Path(r1["path"]); first = p.read_text(encoding="utf-8")
    r2 = append_raw_snapshot(env, {"x": 1}, tmp_path)  # same bytes -> idempotent, no overwrite
    assert r2["wrote"] is False
    assert p.read_text(encoding="utf-8") == first
    # different payload -> different content-addressed file; both retained (append-only)
    env3 = _env(raw_payload={"x": 2})
    r3 = append_raw_snapshot(env3, {"x": 2}, tmp_path)
    assert r3["wrote"] is True and r3["path"] != r1["path"]
    idx = (tmp_path / "index.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(idx) == 2  # two unique snapshots, idempotent re-write not double-logged


def test_envelope_hash_mismatch_is_refused(tmp_path):
    env = _env(raw_payload={"x": 1})
    with pytest.raises(RawStoreError):
        append_raw_snapshot(env, {"x": 999}, tmp_path)  # payload != envelope hash


# ---- dry-run CLI (no network ever) ----
def _args(argv):
    return cli.build_parser().parse_args(argv)


def test_cli_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "store"
    res = cli.run(_args(["--dry-run", "--source", "the_odds_api", "--match-id", "MX1",
                         "--as-of-utc", "2026-06-21T00:00:00Z", "--output-dir", str(out)]))
    assert res["ok"] and res["mode"] == "dry-run" and res["would_write"] is False
    assert not out.exists() or not any(out.rglob("*.json"))


def test_cli_non_dry_run_without_fixture_fails_closed(tmp_path):
    out = tmp_path / "store"
    res = cli.run(_args(["--source", "the_odds_api", "--match-id", "MX1",
                         "--as-of-utc", "2026-06-21T00:00:00Z", "--output-dir", str(out)]))
    assert res["ok"] is False and "fail-closed" in res["error"]


def test_cli_ingests_local_fixture(tmp_path):
    out = tmp_path / "store"
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps({"provider_endpoint": "/v4/sports/odds",
                              "source_url_or_endpoint": "local_fixture://fx.json",
                              "payload": {"book": "demo", "home": 1.8, "draw": 3.5, "away": 4.2}}),
                  encoding="utf-8")
    argv = ["--source", "the_odds_api", "--match-id", "MX1", "--as-of-utc", "2026-06-21T00:00:00Z",
            "--output-dir", str(out), "--fixture", str(fx)]
    res = cli.run(_args(argv))
    assert res["ok"] and res["wrote"] is True and Path(res["path"]).exists()
    # idempotent second run
    assert cli.run(_args(argv))["wrote"] is False


def test_cli_unknown_source_rejected(tmp_path):
    res = cli.run(_args(["--dry-run", "--source", "evil_scraper", "--match-id", "M",
                         "--as-of-utc", "2026-06-21T00:00:00Z", "--output-dir", str(tmp_path)]))
    assert res["ok"] is False and "unknown source" in res["error"]


# ---- health module: pure helpers, no network in tests, no secret leakage ----
def test_health_helpers_are_network_free_and_secret_safe():
    assert health._status_class(404) == "4xx"
    assert health._status_class(200) == "2xx"
    base = health._base("api_football", "GET /status", "API_FOOTBALL_KEY")
    # the sanitized result shape never contains a key/value/header field
    assert set(base) == {"provider", "endpoint", "configured", "auth_accepted", "mode_detected",
                         "status_class", "provider_error_flag", "rate_limit", "error_class"}
    assert base["configured"] in {"SET", "MISSING"}
