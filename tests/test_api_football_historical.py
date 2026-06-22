"""No-network tests for the read-only API-Football historical ingestion command."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import ingest_api_football_historical as cli  # noqa: E402


def _a(argv):
    return cli.build_parser().parse_args(argv)


def test_season_gate_fails_closed():
    r = cli.run(_a(["--league", "1", "--season", "2026", "--kind", "fixtures", "--output-dir", "x"]))
    assert r["ok"] is False and "fail-closed" in r["error"]   # 2026 not on free plan, no request


def test_dry_run_no_network_no_write():
    r = cli.run(_a(["--dry-run", "--league", "1", "--season", "2022", "--kind", "fixtures", "--output-dir", "x"]))
    assert r["ok"] and r["mode"] == "dry-run" and r["wrote"] is False


def test_events_require_fixture_id():
    r = cli.run(_a(["--league", "1", "--season", "2022", "--kind", "events", "--output-dir", "x"]))
    assert r["ok"] is False and "fixture required" in r["error"]   # returns before any network call
