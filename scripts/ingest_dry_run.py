"""Read-only / dry-run ingestion command (Data Enrichment Gate 1, section 5).

Supports the required flags: --dry-run --source --match-id --as-of-utc --output-dir
(plus --fixture for local, sanitized demonstration ingestion).

Safety by construction:
  - --dry-run produces a validated PLAN only; it writes nothing and calls no provider/network.
  - Without --dry-run, ingestion is allowed ONLY from a local --fixture file (sanitized). There is
    no approved live event feed, so live/network ingestion FAILS CLOSED.
  - All snapshots go through the append-only, immutable raw store with a full provenance envelope.
  - --as-of-utc is the decision timestamp: only data known at/before it is feature-eligible.

This command never trades, polls markets, scrapes, or bypasses any provider control.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingestion.raw_store import append_raw_snapshot, make_envelope  # noqa: E402
from wcdrawlab.ingestion.validate import validate_envelope  # noqa: E402

KNOWN_SOURCES = {
    "the_odds_api", "football_data_org", "open_meteo", "api_football",
    "official_feed", "secondary_provider", "open_dataset", "local_fixture",
}
# Sources with an approved + working LIVE ingestion path right now. Empty for event feeds:
# no licensed event feed is approved, and the API-Football key is currently rejected.
LIVE_APPROVED_SOURCES: set[str] = set()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only / dry-run data ingestion")
    p.add_argument("--dry-run", action="store_true", help="plan + validate only; no writes, no network")
    p.add_argument("--source", required=True, help="canonical source id")
    p.add_argument("--match-id", required=True, help="our canonical match id")
    p.add_argument("--as-of-utc", required=True, help="decision timestamp (ISO-8601); gates feature eligibility")
    p.add_argument("--output-dir", required=True, help="append-only raw store root")
    p.add_argument("--fixture", default=None, help="local sanitized JSON to ingest (non-dry-run only)")
    p.add_argument("--ingestion-run-id", default="dryrun-run", help="uuid grouping the run")
    return p


def run(args: argparse.Namespace) -> dict:
    if args.source not in KNOWN_SOURCES:
        return {"ok": False, "error": f"unknown source {args.source!r}; known={sorted(KNOWN_SOURCES)}"}

    plan = {
        "ok": True,
        "mode": "dry-run" if args.dry_run else "ingest",
        "source": args.source,
        "match_id": args.match_id,
        "as_of_utc": args.as_of_utc,
        "decision_time_rule": "only data with effective_known_time <= as_of_utc is feature-eligible",
        "output_dir": args.output_dir,
        "would_write": (not args.dry_run) and bool(args.fixture),
        "wrote": False,
    }

    if args.dry_run:
        plan["note"] = "dry-run: validated plan only; no provider call, no write."
        return plan

    # Non-dry-run: fail closed unless we have a local fixture (no approved live feed).
    if not args.fixture:
        if args.source not in LIVE_APPROVED_SOURCES:
            return {"ok": False, "error": (
                f"no approved live ingestion source for {args.source!r}; "
                "provide --fixture for local ingestion or use --dry-run (fail-closed).")}
    fx = Path(args.fixture)
    if not fx.exists():
        return {"ok": False, "error": f"fixture not found: {fx}"}
    fixture = json.loads(fx.read_text(encoding="utf-8"))
    payload = fixture.get("payload", fixture)

    env = make_envelope(
        source_name=args.source,
        provider_endpoint=fixture.get("provider_endpoint", f"/{args.source}"),
        match_id=args.match_id,
        raw_payload=payload,
        retrieval_timestamp_utc=fixture.get("retrieval_timestamp_utc", args.as_of_utc),
        source_url_or_endpoint=fixture.get("source_url_or_endpoint", f"local_fixture://{fx.name}"),
        ingestion_run_id=args.ingestion_run_id,
        event_timestamp_utc=fixture.get("event_timestamp_utc"),
        published_timestamp_utc=fixture.get("published_timestamp_utc"),
        provider_match_id=fixture.get("provider_match_id"),
        provider_event_id=fixture.get("provider_event_id"),
        quality_status=fixture.get("quality_status", "ok"),
        reconciliation_status=fixture.get("reconciliation_status", "single_source"),
    )
    errors = validate_envelope(env)
    if errors:
        return {"ok": False, "error": "envelope validation failed", "details": errors}

    res = append_raw_snapshot(env, payload, args.output_dir)
    plan["wrote"] = res["wrote"]
    plan["raw_payload_hash"] = res["raw_payload_hash"]
    plan["path"] = res["path"]
    return plan


def main():
    args = build_parser().parse_args()
    result = run(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("ok"):
        sys.exit(2)


if __name__ == "__main__":
    main()
