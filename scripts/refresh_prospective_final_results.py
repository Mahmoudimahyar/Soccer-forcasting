"""PHASE 2 — Read-only result reconciliation refresh.

Refreshes FINAL results for 2026 WC fixtures from football-data.org (primary) and resolves each to a
canonical result record in team_a orientation. Writes ONLY to the worktree scoring results dir; never
overwrites the collector's results file; never calls The Odds API; never prints secret values.

Pure normalization functions (network-free) are unit-tested in tests/test_prospective_result_reconciliation.py.

Usage:
  python scripts/refresh_prospective_final_results.py            # fetch + write
  python scripts/refresh_prospective_final_results.py --offline  # rebuild from last raw payload (no network)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "prospective_harvest"))
from _harvest_common import (  # noqa: E402
    FORECAST_TARGETS, RESULTS_DIR, canon, load_collector_env, pair_key, stamp_labels, write_json,
)

RECON_VERSION = "prospective_result_reconciliation_v1"
RESULTS_CSV = RESULTS_DIR / "prospective_final_results.csv"
RECON_JSON = RESULTS_DIR / "prospective_result_reconciliation.json"

_FINAL = {"FINISHED", "AET", "PEN", "AWARDED"}
_AWAIT = {"TIMED", "SCHEDULED", "IN_PLAY", "PAUSED", "SUSPENDED"}


def normalize_status(s: str) -> str:
    s = str(s).strip().upper()
    return s if s else "TIMED"


def record_from_fd_match(m: dict) -> dict:
    """Build provider-level fields from a football-data.org match dict (no identity/outcome resolution)."""
    score = m.get("score", {}) or {}
    ft = score.get("fullTime", {}) or {}
    et = score.get("extraTime", {}) or {}
    pen = score.get("penalties", {}) or {}
    return {
        "provider_fixture_id": m.get("id"),
        "normalized_home_team": canon(m.get("homeTeam", {}).get("name", "")),
        "normalized_away_team": canon(m.get("awayTeam", {}).get("name", "")),
        "kickoff_utc": m.get("utcDate"),
        "competition": "WC",
        "matchday": m.get("matchday"),
        "final_status": normalize_status(m.get("status")),
        "duration": str(score.get("duration", "REGULAR")),
        "home_regulation_goals": ft.get("home"),
        "away_regulation_goals": ft.get("away"),
        "extra_time_home": et.get("home"),
        "extra_time_away": et.get("away"),
        "shootout_home": pen.get("home"),
        "shootout_away": pen.get("away"),
        "source_provider": "football_data_org",
    }


def outcome_home_orientation(home_goals, away_goals):
    if home_goals is None or away_goals is None:
        return None
    if pd.isna(home_goals) or pd.isna(away_goals):
        return None
    h, a = int(home_goals), int(away_goals)
    return "HOME" if h > a else ("DRAW" if h == a else "AWAY")


def resolve_identity_and_outcome(rec: dict, pair2mid: dict, mid2teamA: dict) -> dict:
    """Resolve canonical_fixture_id + team_a-orientation outcome + reconciliation_status."""
    rec = dict(rec)
    pk = frozenset((rec["normalized_home_team"], rec["normalized_away_team"]))
    mid = pair2mid.get(pk)
    rec["canonical_fixture_id"] = mid
    rec["team_a"] = mid2teamA.get(mid, {}).get("team_a") if mid else None
    rec["team_b"] = mid2teamA.get(mid, {}).get("team_b") if mid else None

    status = rec["final_status"]
    ho = outcome_home_orientation(rec["home_regulation_goals"], rec["away_regulation_goals"])
    rec["final_1x2_outcome_home_orientation"] = ho

    # team_a orientation
    oa = None
    if ho is not None and rec["team_a"] is not None:
        if canon(rec["normalized_home_team"]) == canon(rec["team_a"]):
            oa = {"HOME": "A", "DRAW": "D", "AWAY": "B"}[ho]
        elif canon(rec["normalized_home_team"]) == canon(rec["team_b"]):
            oa = {"HOME": "B", "DRAW": "D", "AWAY": "A"}[ho]
    rec["final_1x2_outcome_team_a_orientation"] = oa

    # reconciliation status
    if mid is None:
        rec["reconciliation_status"] = "unresolved_identity"
        rec["discrepancy_reason"] = "team-pair not found in forecast_targets"
    elif status in _FINAL and ho is not None:
        rec["reconciliation_status"] = "verified_final"
        rec["discrepancy_reason"] = None
    elif status == "POSTPONED":
        rec["reconciliation_status"] = "fixture_postponed"; rec["discrepancy_reason"] = None
    elif status == "CANCELLED":
        rec["reconciliation_status"] = "fixture_cancelled"; rec["discrepancy_reason"] = None
    elif status in _AWAIT or ho is None:
        rec["reconciliation_status"] = "awaiting_final"; rec["discrepancy_reason"] = None
    else:
        rec["reconciliation_status"] = "awaiting_final"; rec["discrepancy_reason"] = f"status={status}"
    rec["cross_check_status"] = "official_single_source"
    return rec


def build_result_records(matches: list[dict], ft: pd.DataFrame, retrieval_ts: str,
                         payload_hash: str) -> pd.DataFrame:
    pair2mid = {pair_key(r.team_a, r.team_b): r.match_id for r in ft.itertuples()}
    mid2teamA = {r.match_id: {"team_a": canon(r.team_a), "team_b": canon(r.team_b)} for r in ft.itertuples()}
    recs = []
    for m in matches:
        base = record_from_fd_match(m)
        rec = resolve_identity_and_outcome(base, pair2mid, mid2teamA)
        rec["source_retrieval_timestamp"] = retrieval_ts
        rec["source_payload_hash"] = payload_hash
        recs.append(rec)
    return pd.DataFrame(recs)


def fetch_footballdata():
    import requests
    load_collector_env(verbose=False)
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        raise SystemExit("FOOTBALL_DATA_KEY missing")
    r = requests.get("https://api.football-data.org/v4/competitions/WC/matches",
                     headers={"X-Auth-Token": key}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="rebuild from last saved raw payload (no network)")
    a = ap.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    retrieval_ts = datetime.now(timezone.utc).isoformat()

    raw_path = RESULTS_DIR / "footballdata_wc_raw_latest.json"
    if a.offline:
        if not raw_path.exists():
            raise SystemExit("no saved raw payload for --offline")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        retrieval_ts = payload.get("_retrieved_utc", retrieval_ts)
    else:
        payload = fetch_footballdata()
        payload["_retrieved_utc"] = retrieval_ts
        raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    payload_hash = hashlib.sha256(json.dumps(payload.get("matches", []), sort_keys=True,
                                             default=str).encode()).hexdigest()
    matches = [m for m in payload.get("matches", []) if m.get("stage") == "GROUP_STAGE"]
    ft = pd.read_csv(FORECAST_TARGETS)
    df = build_result_records(matches, ft, retrieval_ts, payload_hash)
    df.to_csv(RESULTS_CSV, index=False)

    vc = df["reconciliation_status"].value_counts().to_dict()
    manifest = stamp_labels({
        "reconciliation_version": RECON_VERSION,
        "source_retrieval_timestamp": retrieval_ts,
        "primary_provider": "football_data_org",
        "fallback_provider": "api_football_pro",
        "odds_api_called": False,
        "raw_payload_path": str(raw_path),
        "raw_payload_sha256": payload_hash,
        "counts": {
            "n_provider_fixtures": int(len(df)),
            "n_verified_final": int((df.reconciliation_status == "verified_final").sum()),
            "n_awaiting_final": int((df.reconciliation_status == "awaiting_final").sum()),
            "n_excluded": int(df.reconciliation_status.isin(
                ["fixture_cancelled", "fixture_postponed", "unresolved_identity", "provider_conflict"]).sum()),
            "n_resolved_to_ledger_fixture": int(df.canonical_fixture_id.notna().sum()),
            "status_distribution": vc,
        },
    })
    write_json(RECON_JSON, manifest)
    print(f"RECONCILE OK | provider_fixtures={len(df)} verified_final={manifest['counts']['n_verified_final']} "
          f"resolved={manifest['counts']['n_resolved_to_ledger_fixture']} | odds_api_called=False")
    print(f"  -> {RESULTS_CSV}")


if __name__ == "__main__":
    main()
