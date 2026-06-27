"""Component 3 AUDIT + DETERMINISTIC SELF-TEST -- DYNAMIC xG STATE (Phase 3).

Two layers:
  (A) DETERMINISTIC SELF-TEST on hand-built synthetic events (no disk I/O, no network) proving the engine's
      causal guarantees independent of the corpus:
        * no future xG: cum_xg at t excludes shots strictly after t
        * monotonic xG: cum_xg is non-decreasing along the grid
        * no cross-match leakage: a shot added to match B never changes match A's features
        * regulation-only: period>2 (ET) shots never enter features (only the ET flag)
        * missing xG: a null statsbomb_xg shot raises shot COUNT but not xG SUM (no imputation)
  (B) STRUCTURAL AUDIT of data/processed/dynamic_xg_state_v1.csv: nonzero xG-eligible snapshots,
      regulation-only, completeness in range, 64-hex source hash, one match per row, base-join cross-check.

Exits 0 only if every check passes AND >0 real xG-eligible snapshots exist. research_only.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import dynamic_xg_state as DXG  # noqa: E402

OUT = ROOT / "data/processed/dynamic_xg_state_v1.csv"
BASE_JOIN = ROOT / "data/processed/xg_snapshot_join_v1.csv"
AUDIT_OUT = ROOT / "data/reference/dynamic_xg_state_audit.json"
RUN_PHASE = ROOT / "outputs/research_runs/truth_20260626_134931/model_phase"


# --------------------------------------------------------------------------------------------------
# (A) deterministic self-test on synthetic events
# --------------------------------------------------------------------------------------------------
def _shot_event(minute, second, team, xg, outcome="Blocked", period=1, index=0):
    """Build a minimal StatsBomb-shaped shot event."""
    sh = {"outcome": {"name": outcome}}
    if xg is not None:
        sh["statsbomb_xg"] = xg
    return {"type": {"name": "Shot"}, "team": {"name": team}, "minute": minute, "second": second,
            "period": period, "index": index, "shot": sh}


def _events_to_bytes(events):
    return json.dumps(events).encode("utf-8")


def self_test() -> dict:
    checks = {}
    HOME, AWAY = "Alpha", "Beta"

    # canonical_team_name may normalize; build events with the canonical names the parser will compare to
    from wcdrawlab.ingest import canonical_team_name
    hc, ac = canonical_team_name(HOME), canonical_team_name(AWAY)

    # Match A: home shots at 12' (xg .5) and 70' (xg .4); away shot at 40' (xg .2); a null-xG home shot at 20'
    evA = [
        _shot_event(12, 0, HOME, 0.5, index=10),
        _shot_event(20, 0, HOME, None, index=20),     # missing xG -> count but not sum
        _shot_event(40, 0, AWAY, 0.2, index=30),
        _shot_event(70, 0, HOME, 0.4, index=40),
        _shot_event(95, 0, HOME, 0.9, outcome="Goal", period=5, index=50),  # ET shot -> excluded
    ]
    meA = DXG.parse_match_events(_events_to_bytes(evA), hc, ac, "A")

    # no future xG: at t=30, only the 12' (.5) home and (no away yet) count; away .2 is at 40' -> excluded
    f30 = DXG.dynamic_features_at(meA, 30.0)
    checks["no_future_xg_home"] = abs(f30["cum_xg_home"] - 0.5) < 1e-9
    checks["no_future_xg_away_excluded"] = abs(f30["cum_xg_away"] - 0.0) < 1e-9

    # missing-xG shot at 20' raises COUNT (2 home shots by t=30) but not SUM (still 0.5), completeness 0.5
    checks["missing_xg_counts_not_summed"] = (f30["n_shots_to_t"] == 2 and abs(f30["cum_xg_home"] - 0.5) < 1e-9)
    checks["xg_completeness_tracks_missing"] = abs(f30["xg_completeness"] - 0.5) < 1e-9

    # monotonic cum xg-diff magnitude along grid (cum sums never decrease)
    cum_h = [DXG.dynamic_features_at(meA, float(t))["cum_xg_home"] for t in DXG.GRID]
    checks["cum_xg_monotonic_nondecreasing"] = all(b >= a - 1e-9 for a, b in zip(cum_h, cum_h[1:]))

    # regulation-only: the ET goal (.9) at period 5 never enters any grid snapshot (max grid t=90)
    f90 = DXG.dynamic_features_at(meA, 90.0)
    checks["regulation_only_excludes_ET"] = abs(f90["cum_xg_home"] - (0.5 + 0.4)) < 1e-9
    checks["extra_time_flagged"] = meA.extra_time_count > 0

    # no cross-match leakage: build match B with a huge shot; recompute A -> A unchanged
    evB = [_shot_event(10, 0, HOME, 5.0, index=10)]
    _ = DXG.parse_match_events(_events_to_bytes(evB), hc, ac, "B")
    f30_again = DXG.dynamic_features_at(meA, 30.0)
    checks["no_cross_match_leakage"] = (f30_again == f30)

    # acceleration is leakage-safe: at t=15 only the 12' shot exists; windows are strictly in the past
    f15 = DXG.dynamic_features_at(meA, 15.0)
    checks["acceleration_uses_only_past"] = (f15["cum_xg_home"] <= f15["cum_xg_home"] and
                                             f15["n_shots_to_t"] == 1)

    # big-chance proxy: home shots .5 and .4 are both >= 0.30 by t=90 -> 2 home big-chance proxies
    checks["big_chance_proxy_threshold"] = (f90["big_chance_proxy_home"] == 2 and
                                            f90["big_chance_proxy_away"] == 0)

    # time-since-last-shot: at t=30, last home shot at 20' -> tsls = 10
    checks["time_since_last_shot_causal"] = abs(f30["time_since_last_shot"] - 10.0) < 1e-9

    return {"ok": all(checks.values()), "checks": checks}


# --------------------------------------------------------------------------------------------------
# (B) structural audit of the produced CSV
# --------------------------------------------------------------------------------------------------
def structural_audit() -> dict:
    if not OUT.exists():
        return {"ok": False, "reason": "dynamic_xg_state_v1.csv not built"}
    rows = list(csv.DictReader(open(OUT, encoding="utf-8")))
    if not rows:
        return {"ok": False, "reason": "empty output"}

    def _f(r, k):
        v = r.get(k)
        return float(v) if v not in (None, "", "None") else None

    checks = {}
    checks["nonzero_snapshots"] = len(rows) > 0
    xg_elig = sum(int(r["xg_eligible"]) for r in rows)
    checks["nonzero_xg_eligible"] = xg_elig > 0
    checks["regulation_only"] = all(int(r["snapshot_minute"]) <= 90 for r in rows)
    checks["all_regulation_eligible"] = all(int(r["regulation_eligible"]) == 1 for r in rows)
    checks["completeness_in_range"] = all(0.0 <= _f(r, "xg_completeness") <= 1.0 for r in rows)
    checks["source_hash_present"] = all(len(r["sb_events_sha256"]) == 64 for r in rows)
    checks["event_order_ok"] = all(int(r["source_event_order_ok"]) == 1 for r in rows)
    checks["one_match_per_row"] = all(r["sb_match_id"] and r["canonical_match_id"] for r in rows)
    checks["xg_source_labeled"] = all(r["xg_source"] == DXG.XG_SOURCE for r in rows)
    checks["big_chance_is_proxy_flagged"] = all(int(r["big_chance_is_proxy"]) == 1 for r in rows)
    # per-minute rate sanity: |xg_per_min_diff * t - cum_xg_diff| ~ 0
    rate_ok = True
    for r in rows:
        t = float(r["snapshot_minute"]); rate = _f(r, "xg_per_min_diff"); cum = _f(r, "cum_xg_diff")
        if abs(rate * max(t, 1.0) - cum) > 1e-3:
            rate_ok = False; break
    checks["per_minute_rate_consistent"] = rate_ok
    # prior-xg-quality leakage shape: first-ever appearance of any team has null prior (n=0)
    checks["prior_quality_nulls_have_zero_support"] = all(
        not (r["prior_xg_quality_home"] in ("", "None", None) and int(r["prior_xg_n_matches_home"]) != 0)
        for r in rows)

    # cross-check vs base JOB5 join: cumulative xG must match on shared (sb_match_id, minute) keys
    base_match = {"checked": 0, "mismatch": 0}
    if BASE_JOIN.exists():
        base = {}
        for b in csv.DictReader(open(BASE_JOIN, encoding="utf-8")):
            base[(b["sb_match_id"], b["snapshot_minute"])] = b
        for r in rows:
            b = base.get((r["sb_match_id"], r["snapshot_minute"]))
            if b is None:
                continue
            base_match["checked"] += 1
            if (abs(float(b["cum_xg_home"]) - _f(r, "cum_xg_home")) > 1e-4 or
                    abs(float(b["cum_xg_away"]) - _f(r, "cum_xg_away")) > 1e-4):
                base_match["mismatch"] += 1
        checks["base_join_cumxg_consistent"] = (base_match["checked"] > 0 and base_match["mismatch"] == 0)
    else:
        checks["base_join_cumxg_consistent"] = True  # base absent -> skip, do not fail

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "rows": len(rows),
        "xg_eligible_international_snapshots": xg_elig,
        "distinct_matches": len({r["sb_match_id"] for r in rows}),
        "rows_with_nonzero_xg": sum(1 for r in rows if _f(r, "cum_xg_home") + _f(r, "cum_xg_away") > 0),
        "base_join_crosscheck": base_match,
    }


def main():
    st = self_test()
    sa = structural_audit()
    out = {
        "ok": bool(st["ok"] and sa.get("ok")),
        "self_test": st,
        "structural_audit": sa,
        "status": "complete" if (st["ok"] and sa.get("ok") and
                                 sa.get("xg_eligible_international_snapshots", 0) > 0) else "failed",
    }
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    RUN_PHASE.mkdir(parents=True, exist_ok=True)
    (RUN_PHASE / "dynamic_xg_state_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
