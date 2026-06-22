"""Read-only, season-gated, quota-aware, append-only API-Football HISTORICAL ingestion (dry-run capable).

Free plan covers seasons 2022-2024 only -> this command FAILS CLOSED for any other season. Uses the
existing provider interface (metered QuotaBudget) + append-only raw store. Does NOT begin
high-frequency polling and does NOT modify the protected provider adapter. Dry-run does no network.

Examples:
  python scripts/ingest_api_football_historical.py --dry-run --league 1 --season 2022 --kind fixtures
  python scripts/ingest_api_football_historical.py --league 1 --season 2022 --kind events --fixture 855736 --output-dir data/raw/api_football_hist
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except Exception:
    pass
from wcdrawlab.providers.interface import APIFootballProvider, QuotaBudget, QuotaExceeded  # noqa: E402
from wcdrawlab.ingestion.raw_store import append_raw_snapshot, make_envelope  # noqa: E402

FREE_SEASONS = {2022, 2023, 2024}
KINDS = {"fixtures", "events", "lineups", "statistics", "standings"}


def build_parser():
    p = argparse.ArgumentParser(description="read-only API-Football historical ingestion")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--league", type=int, required=True)
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--kind", choices=sorted(KINDS), required=True)
    p.add_argument("--fixture", type=int, default=None, help="fixture id (for events/lineups/statistics)")
    p.add_argument("--output-dir", default="data/raw/api_football_hist")
    p.add_argument("--max-requests", type=int, default=40, help="daily budget for this run")
    p.add_argument("--reserve", type=int, default=10, help="reserve held back from the daily cap")
    p.add_argument("--min-interval", type=float, default=7.0, help="seconds between calls (>=10/min cap)")
    return p


def run(args) -> dict:
    if args.season not in FREE_SEASONS:
        return {"ok": False, "error": f"season {args.season} not on free plan (allowed {sorted(FREE_SEASONS)}); "
                                      "fail-closed (no request made)"}
    if args.kind in {"events", "lineups", "statistics"} and not args.fixture and not args.dry_run:
        return {"ok": False, "error": f"--fixture required for kind={args.kind}"}
    plan = {"ok": True, "mode": "dry-run" if args.dry_run else "ingest", "league": args.league,
            "season": args.season, "kind": args.kind, "fixture": args.fixture,
            "output_dir": args.output_dir, "budget": args.max_requests, "reserve": args.reserve,
            "free_tier_gate": "season in 2022-2024 OK", "wrote": False}
    if args.dry_run:
        plan["note"] = "dry-run: validated plan; no provider call, no write."
        return plan

    budget = QuotaBudget(daily_limit=args.max_requests, reserve=args.reserve)
    prov = APIFootballProvider(budget=budget)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    try:
        if args.kind == "fixtures":
            payload = prov.fixtures(args.league, args.season); endpoint = "/fixtures"; mid = f"L{args.league}S{args.season}"
        elif args.kind == "standings":
            payload = prov.standings(args.league, args.season); endpoint = "/standings"; mid = f"L{args.league}S{args.season}"
        elif args.kind == "events":
            payload = prov.events(args.fixture); endpoint = "/fixtures/events"; mid = str(args.fixture)
        elif args.kind == "lineups":
            payload = prov.lineups(args.fixture); endpoint = "/fixtures/lineups"; mid = str(args.fixture)
        else:
            payload = prov.statistics(args.fixture); endpoint = "/fixtures/statistics"; mid = str(args.fixture)
    except QuotaExceeded as e:
        return {"ok": False, "error": f"quota exhausted: {e}"}
    time.sleep(args.min_interval)
    from datetime import datetime, timezone
    env = make_envelope(source_name="api_football", provider_endpoint=endpoint, match_id=mid,
                        raw_payload=payload, retrieval_timestamp_utc=datetime.now(timezone.utc).isoformat(),
                        source_url_or_endpoint=f"api-sports.io{endpoint}", ingestion_run_id=f"af-hist-{args.season}",
                        quality_status="ok", reconciliation_status="single_source")
    res = append_raw_snapshot(env, payload, out)
    plan.update({"wrote": res["wrote"], "path": res["path"], "credits_used": budget.used})
    return plan


def main():
    r = run(build_parser().parse_args())
    print(json.dumps(r, indent=2, ensure_ascii=False))
    sys.exit(0 if r.get("ok") else 2)


if __name__ == "__main__":
    main()
