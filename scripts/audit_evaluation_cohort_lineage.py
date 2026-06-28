"""Audit the EVALUATION COHORT LINEAGE against its integrity contract (Phase 1).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Re-verifies, on the PRODUCED lineage artifacts (no rebuild required), every invariant the lineage must
satisfy, and INDEPENDENTLY re-derives the headline funnel counts from the real source files so the audit
cannot pass on a fabricated lineage:

  * one row per fixture; stage columns are 0/1 only
  * every present->absent transition along the stage chain carries exactly one ALLOWED drop reason
  * no fixture disappears silently (no unexplained 1->0)
  * the stage funnel is monotone non-increasing across the in-play chain
    (exact_bridge >= xg_snapshot >= event_process >= residual >= primary; loco between residual and itself)
  * independent re-derivation: exact_bridge == 258 from the bridge CSV; event_process == |on-disk events
    INTERSECT exact-intl bridge|; residual == event_process; missing_statsbomb_events drops == bridge-258
    minus present; held_out_fold_rule drops == size of the earliest forward-chain competition
  * cross-check vs the residual decision ledger's audited n_matches (must equal residual_population)
  * the exclusion ledger row count == number of dropped fixtures in the lineage
  * NO 2026 World Cup competition appears anywhere in the cohort

Exits non-zero / status=fail with the offending detail on any breach.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
REF = ROOT / "data/reference"
BRIDGE_CSV = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")
SB_PRIOR_EVENTS = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/raw/statsbomb_open/events")
SB_CANON_EVENTS = ROOT / "data/raw/statsbomb_open/events"

STAGES = ["raw_corpus", "reconciled_corpus", "international_population", "exact_bridge_population",
          "xg_snapshot_population", "event_process_population", "residual_population",
          "primary_evaluation_population", "loco_evaluation_population"]
# the in-play chain that must be monotone non-increasing (loco is a re-expansion to all residual, audited separately)
MONOTONE_CHAIN = ["exact_bridge_population", "xg_snapshot_population", "event_process_population",
                  "residual_population", "primary_evaluation_population"]
ALLOWED_REASONS = {
    "missing_raw_events", "missing_raw_lineups", "failed_reconciliation", "ambiguous_bridge",
    "missing_statsbomb_events", "missing_required_feature", "target_not_regulation_eligible",
    "extra_time_or_shootout_only", "temporal_cutoff", "held_out_fold_rule",
    "insufficient_prior_history", "source_quality_failure", "duplicate", "data_contract_mismatch",
    "intentional_preregistered_exclusion", "verified_bug", "unknown",
}
FORBIDDEN_2026 = ("world cup 2026", "fifa world cup 2026", "wc 2026", "2026 world cup")


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_csv(p: Path):
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _on_disk_event_ids() -> set:
    ids = set()
    for d in (SB_PRIOR_EVENTS, SB_CANON_EVENTS):
        if d.exists():
            ids |= {os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json")}
    return ids


def main():
    checks = []

    def rec(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})

    lin = _read_csv(REF / "evaluation_cohort_lineage.csv")
    excl = _read_csv(REF / "cohort_exclusion_ledger.csv")
    if lin is None or excl is None:
        print(json.dumps({"status": "data_insufficient",
                          "reason": "lineage/exclusion artifacts absent; run build_evaluation_cohort_lineage.py",
                          "labels": LABELS}))
        return 2

    # 0/1 stage columns
    bad01 = [r for r in lin for s in STAGES if r.get(s) not in ("0", "1")]
    rec("stage_columns_binary", not bad01, f"non-binary cells: {len(bad01)}")

    # allowed reasons only
    bad_reason = sorted({r["drop_reason"] for r in lin
                         if r.get("drop_reason") and r["drop_reason"] not in ALLOWED_REASONS})
    rec("allowed_reasons_only", not bad_reason, f"bad: {bad_reason}")

    # no silent disappearance + exactly-one-reason on a drop
    unexplained = []
    for r in lin:
        prev = 1
        dropped = False
        for s in STAGES:
            cur = int(r[s])
            if prev == 1 and cur == 0:
                dropped = True
                if not r.get("drop_reason"):
                    unexplained.append(r.get("sb_match_id") or r.get("api_fixture_id"))
                break
            prev = cur
    rec("no_silent_disappearance", not unexplained, f"unexplained: {unexplained[:5]}")

    # monotone non-increasing along the in-play chain
    funnel = {s: sum(int(r[s]) for r in lin) for s in STAGES}
    mono_ok = all(funnel[MONOTONE_CHAIN[i]] >= funnel[MONOTONE_CHAIN[i + 1]]
                  for i in range(len(MONOTONE_CHAIN) - 1))
    rec("monotone_inplay_chain", mono_ok, {k: funnel[k] for k in MONOTONE_CHAIN})

    # ---- independent re-derivation from real sources ----
    bridge = _read_csv(BRIDGE_CSV)
    exact_intl = [r for r in (bridge or []) if r.get("bridge_confidence") == "exact"
                  and r.get("comp_type") == "international"]
    on_disk = _on_disk_event_ids()
    ids_intl = {r["sb_match_id"] for r in exact_intl}
    present = ids_intl & on_disk

    rec("exact_bridge_matches_258", funnel["exact_bridge_population"] == len(exact_intl),
        f"lineage={funnel['exact_bridge_population']} source={len(exact_intl)}")
    rec("event_process_eq_present_intersection",
        funnel["event_process_population"] == len(present),
        f"lineage={funnel['event_process_population']} source_intersection={len(present)}")
    rec("residual_eq_event_process",
        funnel["residual_population"] == funnel["event_process_population"],
        f"residual={funnel['residual_population']} event_process={funnel['event_process_population']}")

    # missing_statsbomb_events drops == 258 - present
    n_missing = sum(1 for r in lin if r.get("drop_reason") == "missing_statsbomb_events")
    rec("missing_statsbomb_events_count",
        n_missing == (len(exact_intl) - len(present)),
        f"lineage={n_missing} expected={len(exact_intl) - len(present)}")

    # held_out_fold_rule == size of earliest present competition
    present_rows = [r for r in exact_intl if r["sb_match_id"] in present]
    first_kick = defaultdict(lambda: "~")
    cnt = Counter()
    for r in present_rows:
        c = r["competition_label"]
        cnt[c] += 1
        k = r.get("kickoff_date") or "~"
        if k < first_kick[c]:
            first_kick[c] = k
    order = [c for c, _ in sorted(first_kick.items(), key=lambda kv: (kv[1], kv[0]))]
    earliest_n = cnt[order[0]] if order else 0
    n_heldout = sum(1 for r in lin if r.get("drop_reason") == "held_out_fold_rule")
    rec("held_out_fold_rule_eq_earliest_competition",
        n_heldout == earliest_n and funnel["primary_evaluation_population"] == (len(present) - earliest_n),
        f"heldout={n_heldout} earliest({order[0] if order else None})={earliest_n} "
        f"primary={funnel['primary_evaluation_population']}")

    # loco == residual (every present competition held out once)
    rec("loco_eq_residual",
        funnel["loco_evaluation_population"] == funnel["residual_population"],
        f"loco={funnel['loco_evaluation_population']} residual={funnel['residual_population']}")

    # cross-check vs residual decision ledger audited n_matches
    led = _read_json(REF / "residual_goal_intensity_decision_ledger.json")
    ledger_nm = None
    if led:
        for m in led.get("models", []):
            if (m.get("evidence") or {}).get("n_matches"):
                ledger_nm = m["evidence"]["n_matches"]
                break
    rec("residual_ledger_n_matches_consistent",
        ledger_nm is None or ledger_nm == funnel["residual_population"],
        f"ledger_n_matches={ledger_nm} residual_population={funnel['residual_population']}")

    # exclusion ledger count == dropped fixtures in lineage
    n_dropped_lineage = sum(1 for r in lin if r.get("drop_reason"))
    rec("exclusion_ledger_count_matches", len(excl) == n_dropped_lineage,
        f"exclusions={len(excl)} dropped_in_lineage={n_dropped_lineage}")

    # NO 2026 World Cup anywhere
    has_2026 = [r.get("competition_label") for r in lin
                if any(tok in (r.get("competition_label") or "").lower() for tok in FORBIDDEN_2026)]
    rec("no_2026_world_cup", not has_2026, f"offending: {has_2026[:3]}")

    all_ok = all(c["ok"] for c in checks)
    out = {
        "status": "ok" if all_ok else "fail",
        "funnel_match_level": funnel,
        "n_fixture_rows": len(lin),
        "rederived": {"exact_intl_bridge": len(exact_intl), "on_disk_events": len(on_disk),
                      "present_intersection": len(present), "earliest_competition": order[0] if order else None,
                      "earliest_n": earliest_n, "forward_chain_order": order},
        "checks": checks,
        "labels": LABELS,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
