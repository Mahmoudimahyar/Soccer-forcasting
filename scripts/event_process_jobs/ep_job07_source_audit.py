"""EPJOB7 -- SOURCE-QUALITY + LEAKAGE audit of the built snapshot products.

Recomputes, independently of the builder, three things on the produced INTERNATIONAL snapshot CSV:
  (1) a row-level leakage re-check: every cumulative count at minute t never exceeds the same count at a
      later minute t' within the same match -- a cheap, model-free leakage tripwire on produced rows;
  (2) a club/international separation check (no club source_match_id appears in the intl file);
  (3) the per-capability source-availability roll-up from competition_source_quality.csv, classifying
      each capability as available_verified / available_partial / unavailable / unknown (never imputed).

Emits data_insufficient (honest) if the snapshot products are absent.
research_only / experimental.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

INTL = L.PROC / "intl_event_process_snapshots.csv"
CLUB = L.PROC / "club_event_process_snapshots.csv"
CQ = L.PROC / "competition_source_quality.csv"


def _read(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    if not INTL.exists() or not CQ.exists():
        L.emit("data_insufficient", reason=f"snapshot products absent (run EPJOB6 first): {INTL.name}/{CQ.name}")
        return
    snaps = _read(INTL)
    if not snaps:
        L.emit("data_insufficient", reason="intl snapshot CSV empty")
        return

    # (1) monotonicity tripwire on cumulative quantities within a match (model-free leakage check)
    MONO = ["goals_home", "goals_away", "shots_home", "shots_away", "yellow_home", "yellow_away",
            "sendoff_home", "sendoff_away", "corners_home", "corners_away", "n_events_observed"]
    by_match = defaultdict(list)
    for r in snaps:
        by_match[r["source_match_id"]].append(r)
    violations = []
    for mid, rs in by_match.items():
        rs = sorted(rs, key=lambda r: float(r["snapshot_minute"]))
        for col in MONO:
            prev = None
            for r in rs:
                try:
                    v = float(r.get(col) or 0)
                except (TypeError, ValueError):
                    continue
                if prev is not None and v + 1e-9 < prev:
                    violations.append({"match": mid, "col": col, "minute": r["snapshot_minute"],
                                       "value": v, "prev": prev})
                prev = v
    mono_ok = len(violations) == 0

    # (2) club/intl separation: no club source_match_id leaks into the intl file
    club_ids = set()
    if CLUB.exists():
        for r in _read(CLUB):
            club_ids.add(str(r["source_match_id"]))
    intl_ids = {str(r["source_match_id"]) for r in snaps}
    overlap = sorted(intl_ids & club_ids)
    separation_ok = len(overlap) == 0
    intl_comp_types = {r.get("comp_type") for r in snaps}
    comp_type_ok = intl_comp_types == {"international"}

    # (3) per-capability availability roll-up (honest flags, never imputed)
    cap_roll = defaultdict(lambda: defaultdict(int))
    for r in _read(CQ):
        cap = r["capability"]
        for flag in ("available_verified", "available_partial", "unavailable", "unknown"):
            cap_roll[cap][flag] += int(float(r.get(flag) or 0))
    cap_summary = {}
    for cap, counts in cap_roll.items():
        dominant = max(counts.items(), key=lambda kv: kv[1])[0] if counts else "unknown"
        cap_summary[cap] = {**dict(counts), "dominant": dominant}

    all_ok = mono_ok and separation_ok and comp_type_ok
    L.write_json("ep_source_quality_leakage_audit.json", {
        "n_intl_snapshots": len(snaps), "n_matches": len(by_match),
        "leakage_monotonicity_ok": mono_ok, "n_violations": len(violations), "violations": violations[:20],
        "club_intl_separation_ok": separation_ok, "n_overlap_ids": len(overlap),
        "intl_comp_type_ok": comp_type_ok, "intl_comp_types": sorted(intl_comp_types),
        "capability_availability": cap_summary, "all_ok": all_ok, "utc": L.utc(),
    })
    L.emit("complete" if all_ok else "failed",
           reason=f"leakage_mono_ok={mono_ok}(viol={len(violations)}) club_intl_sep_ok={separation_ok} "
                  f"comp_type_ok={comp_type_ok} capabilities_audited={len(cap_summary)}",
           state_updates={"source_audit_ok": all_ok, "leakage_mono_violations": len(violations)})


main()
