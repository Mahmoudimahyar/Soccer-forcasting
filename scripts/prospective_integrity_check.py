"""Integrity check for the prospective ledger (V1.5). Verifies first-write-wins (no duplicate keys),
research_only labelling, point-in-time safety (event_source_timestamp <= decision_timestamp), schema
completeness, and that no secret/raw key is present. Read-only; exits non-zero on any violation.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.operations.ledger import ImmutableLedger  # noqa: E402

REQUIRED = {"ledger_key", "model_id", "model_version", "approval_status", "match_id", "phase",
            "decision_timestamp", "p_home_win", "p_draw", "p_away_win"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(ROOT / "data/processed/prospective/ledger.jsonl"))
    a = ap.parse_args()
    led = ImmutableLedger(a.ledger)
    recs = led.records()
    problems = []
    seen = set()
    for r in recs:
        k = r.get("ledger_key")
        if k in seen:
            problems.append(f"DUPLICATE key {k} (first-write-wins violated)")
        seen.add(k)
        if r.get("approval_status") != "research_only":
            problems.append(f"{k}: approval_status != research_only")
        if REQUIRED - set(r):
            problems.append(f"{k}: missing fields {sorted(REQUIRED - set(r))}")
        est, dts = r.get("event_source_timestamp"), r.get("decision_timestamp")
        if est and dts and str(est) > str(dts):
            problems.append(f"{k}: LEAKAGE event_source_timestamp {est} > decision_timestamp {dts}")
        p = (r.get("p_home_win", 0), r.get("p_draw", 0), r.get("p_away_win", 0))
        if abs(sum(p) - 1.0) > 1e-6:
            problems.append(f"{k}: probabilities do not sum to 1 ({sum(p):.4f})")
        if "x-apisports-key" in json.dumps(r) or "API_FOOTBALL_KEY" in json.dumps(r):
            problems.append(f"{k}: possible secret leak in record")
    print(f"checked {len(recs)} ledger records")
    if problems:
        print("INTEGRITY FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("INTEGRITY OK: first-write-wins, research_only, point-in-time safe, schema complete, no secrets")


if __name__ == "__main__":
    main()
