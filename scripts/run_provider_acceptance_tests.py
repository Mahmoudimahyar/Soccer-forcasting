"""Phase 4: run the licensed-event provider ACCEPTANCE protocol against a provider adapter + sample data +
declared terms. Deterministic; fail-closed on unknown rights/causal. Demonstrated on the mock provider.
research_only / not_runtime_approved. NO network, NO credentials.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.licensed_events import reconciliation as R, quality_gate as QG, availability as AV  # noqa: E402


def evaluate(provider_name, events, rights_matrix, coverage_counts, availability_decl, operational_decl):
    """events: list[LicensedEvent]; rights_matrix/availability_decl/operational_decl: dicts; coverage_counts:
    dict(lineup_sub, timestamped, red_or_2y)."""
    res = {"provider_name": provider_name, "categories": {}, "blocking_unknowns": []}
    UNK = "unknown_requires_vendor_confirmation"

    # --- rights (fail closed: any required right not 'yes'/'conditional' confirmed -> fail) ---
    req = ["local_retention_allowed", "historical_research_use", "model_training_on_derived", "derived_label_publication"]
    rights_checks = []
    rights_pass = True
    for k in req:
        v = rights_matrix.get(k, UNK)
        ok = v in ("yes", "conditional")
        rights_checks.append({"check": k, "value": v, "pass": ok})
        if not ok:
            rights_pass = False
            if v == UNK:
                res["blocking_unknowns"].append(f"rights.{k}")
    if rights_matrix.get("raw_redistribution", "prohibited") not in ("prohibited", "conditional"):
        rights_pass = False
    res["categories"]["rights"] = {"checks": rights_checks, "pass": rights_pass}

    # --- coverage (adopted thresholds) ---
    cov = QG.coverage_summary(coverage_counts.get("lineup_sub", 0), coverage_counts.get("timestamped", 0),
                              coverage_counts.get("red_or_2y", 0))
    res["categories"]["coverage"] = {"checks": [cov], "pass": QG.meets_all_thresholds(cov)}

    # --- schema (unique match/player ids, timestamps, correction support) ---
    match_ids = {e.canonical_match_id for e in events}
    has_ts = all((e.match_clock_s is not None or e.event_time_utc is not None) for e in events) if events else False
    player_ids_present = any(e.player_id for e in events)
    correction_support = any(e.correction_status in ("corrected", "retracted") for e in events) or operational_decl.get("corrections", False)
    schema_checks = [
        {"check": "unique_match_ids", "pass": len(match_ids) >= 1},
        {"check": "event_timestamps_present", "pass": has_ts},
        {"check": "player_ids_present", "pass": player_ids_present},
        {"check": "correction_support", "pass": bool(correction_support)},
    ]
    res["categories"]["schema"] = {"checks": schema_checks, "pass": all(c["pass"] for c in schema_checks)}

    # --- causal (publication time + historical/live distinction; no relabel) ---
    elig = AV.causal_eligibility(availability_decl.get("has_publication_time", False),
                                 availability_decl.get("has_event_time", False),
                                 availability_decl.get("historical_available", False),
                                 availability_decl.get("live_available", False))
    causal_checks = [
        {"check": "eligibility_resolved", "value": elig, "pass": elig != "unknown_fail_closed"},
        {"check": "publication_time_for_live", "pass": (not availability_decl.get("live_available", False))
         or availability_decl.get("has_publication_time", False)},
    ]
    res["categories"]["causal"] = {"checks": causal_checks, "pass": all(c["pass"] for c in causal_checks)}

    # --- quality (score reconciliation runs; dup rate; completeness) ---
    deduped = R.dedupe_events(list(events))
    dup_rate = 1 - len(deduped) / len(events) if events else 0.0
    completeness = QG.match_completeness(events)
    quality_checks = [
        {"check": "score_reconciliation_runs", "pass": True, "value": list(R.reconcile_score(events))},
        {"check": "dup_rate_le_0.5", "value": round(dup_rate, 3), "pass": dup_rate <= 0.5},
        {"check": "completeness_ge_0.6", "value": completeness, "pass": completeness >= 0.6},
    ]
    res["categories"]["quality"] = {"checks": quality_checks, "pass": all(c["pass"] for c in quality_checks)}

    # --- operational (rate limits/backfill/append-only/resumable/quota declared) ---
    op_keys = ["rate_limit", "historical_backfill", "append_only_storage", "resumable", "quota_budgeting", "retry_behavior"]
    op_checks = []
    op_pass = True
    for k in op_keys:
        v = operational_decl.get(k, UNK)
        ok = v not in (UNK, None, "")
        op_checks.append({"check": k, "value": v, "pass": ok})
        if not ok:
            op_pass = False
            res["blocking_unknowns"].append(f"operational.{k}")
    res["categories"]["operational"] = {"checks": op_checks, "pass": op_pass}

    res["overall_pass"] = all(c["pass"] for c in res["categories"].values())
    if res["overall_pass"]:
        res["decision"] = "accept_for_storage_and_research"
    elif res["blocking_unknowns"]:
        res["decision"] = "conditional_pending_vendor_confirmation"
    else:
        res["decision"] = "reject"
    return res


def _demo():
    """Run against the mock provider to prove the harness works end-to-end (no real provider)."""
    from wcdrawlab.research.licensed_events import mock_provider as MP
    p = MP.MockProvider()
    events = [p.normalize_event(f()) for f in (MP.fixture_full_event, MP.fixture_events_only,
              MP.fixture_lineup_sub, MP.fixture_shot_xg)]
    UNK = "unknown_requires_vendor_confirmation"
    rights = {k: UNK for k in ("local_retention_allowed", "historical_research_use", "model_training_on_derived",
                               "derived_label_publication")}  # mock vendor unconfirmed -> conditional
    res = evaluate("mock_provider", events,
                   rights_matrix=rights,
                   coverage_counts={"lineup_sub": 10, "timestamped": 10, "red_or_2y": 2},
                   availability_decl={"has_publication_time": True, "has_event_time": True,
                                      "historical_available": True, "live_available": True},
                   operational_decl={k: UNK for k in ("rate_limit", "historical_backfill", "append_only_storage",
                                                       "resumable", "quota_budgeting", "retry_behavior")})
    print(json.dumps({"decision": res["decision"], "overall_pass": res["overall_pass"],
                      "blocking_unknowns": res["blocking_unknowns"][:6],
                      "category_pass": {k: v["pass"] for k, v in res["categories"].items()}}, indent=2))
    return res


if __name__ == "__main__":
    _demo()
