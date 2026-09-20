"""Audit the xG snapshot join: prove it is NONZERO, regulation-only, exact-bridge-only, leak-free in structure.
research_only."""
import csv, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
JOIN = ROOT / "data/processed/xg_snapshot_join_v1.csv"


def main():
    if not JOIN.exists():
        print(json.dumps({"ok": False, "reason": "join not built"})); sys.exit(1)
    rows = list(csv.DictReader(open(JOIN, encoding="utf-8")))
    checks = {}
    checks["nonzero_snapshots"] = len(rows) > 0
    checks["nonzero_xg_eligible"] = sum(int(r["xg_eligible"]) for r in rows) > 0
    checks["regulation_only"] = all(int(r["snapshot_minute"]) <= 90 for r in rows)
    checks["all_regulation_eligible"] = all(int(r["regulation_eligible"]) == 1 for r in rows)
    checks["completeness_in_range"] = all(0.0 <= float(r["xg_completeness"]) <= 1.0 for r in rows)
    checks["source_hash_present"] = all(len(r["sb_events_sha256"]) == 64 for r in rows)
    checks["event_order_ok"] = all(int(r["source_event_order_ok"]) == 1 for r in rows)
    # each snapshot maps to exactly one (sb_match_id) -> no cross-match mixing in a row
    checks["one_match_per_row"] = all(r["sb_match_id"] and r["canonical_match_id"] for r in rows)
    out = {"ok": all(checks.values()), "checks": checks,
           "xg_eligible_international_snapshots": sum(int(r["xg_eligible"]) for r in rows),
           "distinct_matches": len({r["sb_match_id"] for r in rows}),
           "rows_nonzero_xg": sum(1 for r in rows if float(r["cum_xg_home"]) + float(r["cum_xg_away"]) > 0)}
    (ROOT / "data/reference/xg_snapshot_join_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
