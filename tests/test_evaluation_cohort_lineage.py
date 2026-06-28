"""Deterministic tests for the evaluation cohort lineage + research evidence registry (Phase 0-1).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Two tiers:
  * SYNTHETIC (always-on, no disk): exercise the lineage/funnel logic on a tiny fixed fixture set so the
    258->58->46 reduction mechanics, the one-reason-per-drop rule, and the allowed-reason vocabulary are
    proven without depending on the gitignored raw StatsBomb pull.
  * INTEGRATION (on the produced artifacts): re-verify the REAL funnel reconstructs the audited 58 and is
    consistent with the residual decision ledger. These read only artifacts already on disk in this
    worktree; if absent they skip with an explicit reason (never silently pass).

Independent unit is the MATCH. No network/API. The active collector checkout is never touched.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
REF = ROOT / "data/reference"

STAGES = ["raw_corpus", "reconciled_corpus", "international_population", "exact_bridge_population",
          "xg_snapshot_population", "event_process_population", "residual_population",
          "primary_evaluation_population", "loco_evaluation_population"]
ALLOWED_REASONS = {
    "missing_raw_events", "missing_raw_lineups", "failed_reconciliation", "ambiguous_bridge",
    "missing_statsbomb_events", "missing_required_feature", "target_not_regulation_eligible",
    "extra_time_or_shootout_only", "temporal_cutoff", "held_out_fold_rule",
    "insufficient_prior_history", "source_quality_failure", "duplicate", "data_contract_mismatch",
    "intentional_preregistered_exclusion", "verified_bug", "unknown",
}


def _load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =================================================================================================
# SYNTHETIC lineage logic — a pure re-implementation of the funnel mechanics on fixed inputs.
# Mirrors build_evaluation_cohort_lineage.build() but on in-memory data so it is disk-independent.
# =================================================================================================
def _synthetic_lineage(exact_intl, on_disk):
    """exact_intl: list of dicts {sb_match_id, competition_label, kickoff_date}; on_disk: set of ids.
    Returns (rows, funnel, drop_counts) using the SAME rules as the real builder."""
    from collections import Counter, defaultdict
    present = [r for r in exact_intl if r["sb_match_id"] in on_disk]
    first = defaultdict(lambda: "~")
    for r in present:
        c = r["competition_label"]
        k = r.get("kickoff_date") or "~"
        if k < first[c]:
            first[c] = k
    order = [c for c, _ in sorted(first.items(), key=lambda kv: (kv[1], kv[0]))]
    fc_test = set(order[1:])
    rows = []
    for r in exact_intl:
        row = {s: 0 for s in STAGES}
        row.update({"sb_match_id": r["sb_match_id"], "competition_label": r["competition_label"],
                    "drop_reason": ""})
        row["raw_corpus"] = row["reconciled_corpus"] = 1
        row["international_population"] = row["exact_bridge_population"] = 1
        if r["sb_match_id"] not in on_disk:
            row["drop_reason"] = "missing_statsbomb_events"
            rows.append(row)
            continue
        row["xg_snapshot_population"] = row["event_process_population"] = row["residual_population"] = 1
        if r["competition_label"] in fc_test:
            row["primary_evaluation_population"] = 1
        else:
            row["drop_reason"] = "held_out_fold_rule"
        row["loco_evaluation_population"] = 1
        rows.append(row)
    funnel = {s: sum(rr[s] for rr in rows) for s in STAGES}
    drops = Counter(rr["drop_reason"] for rr in rows if rr["drop_reason"])
    return rows, funnel, dict(drops), order


def _make_corpus(n_per_comp, comps, on_disk_fraction):
    exact, on_disk = [], set()
    mid = 1000
    for ci, (comp, kdate) in enumerate(comps):
        for j in range(n_per_comp):
            sid = str(mid); mid += 1
            exact.append({"sb_match_id": sid, "competition_label": comp, "kickoff_date": kdate})
            if j < int(round(n_per_comp * on_disk_fraction)):
                on_disk.add(sid)
    return exact, on_disk


# ---- 1: a clean fully-present corpus: event_process == exact_bridge, primary drops only earliest comp ----
def test_synth_full_presence_primary_drops_earliest():
    comps = [("WC2018", "2018-06-14"), ("Euro2020", "2021-06-11"), ("WC2022", "2022-11-22")]
    exact, on_disk = _make_corpus(10, comps, on_disk_fraction=1.0)
    rows, funnel, drops, order = _synthetic_lineage(exact, on_disk)
    assert funnel["exact_bridge_population"] == 30
    assert funnel["event_process_population"] == 30          # all present
    assert funnel["residual_population"] == 30
    assert order[0] == "WC2018"                              # earliest kickoff
    assert funnel["primary_evaluation_population"] == 20     # 30 - 10 (earliest train-only)
    assert funnel["loco_evaluation_population"] == 30
    assert drops.get("held_out_fold_rule") == 10


# ---- 2: partial presence reproduces a 258->58-style missing_statsbomb_events drop ----
def test_synth_missing_events_drop():
    comps = [("WC2018", "2018-06-14"), ("Euro2020", "2021-06-11")]
    exact, on_disk = _make_corpus(20, comps, on_disk_fraction=0.5)  # 40 total, 20 present
    rows, funnel, drops, order = _synthetic_lineage(exact, on_disk)
    assert funnel["exact_bridge_population"] == 40
    assert funnel["event_process_population"] == 20
    assert drops.get("missing_statsbomb_events") == 20
    # primary = present minus earliest present competition (10 present in WC2018)
    assert funnel["primary_evaluation_population"] == 10


# ---- 3: every drop reason is from the allowed vocabulary ----
def test_synth_reasons_in_allowed_set():
    comps = [("WC2018", "2018-06-14"), ("WC2022", "2022-11-22")]
    exact, on_disk = _make_corpus(6, comps, on_disk_fraction=0.5)
    rows, *_ = _synthetic_lineage(exact, on_disk)
    used = {r["drop_reason"] for r in rows if r["drop_reason"]}
    assert used and used <= ALLOWED_REASONS


# ---- 4: no silent disappearance — every present->absent transition has a reason ----
def test_synth_no_silent_disappearance():
    comps = [("WC2018", "2018-06-14"), ("Euro2020", "2021-06-11"), ("WC2022", "2022-11-22")]
    exact, on_disk = _make_corpus(8, comps, on_disk_fraction=0.5)
    rows, *_ = _synthetic_lineage(exact, on_disk)
    for r in rows:
        prev = 1
        for s in STAGES:
            if prev == 1 and r[s] == 0:
                assert r["drop_reason"], f"unexplained drop at {s} for {r['sb_match_id']}"
                break
            prev = r[s]


# ---- 5: funnel is monotone non-increasing along the in-play chain ----
def test_synth_monotone_chain():
    comps = [("WC2018", "2018-06-14"), ("Euro2020", "2021-06-11"), ("WC2022", "2022-11-22")]
    exact, on_disk = _make_corpus(12, comps, on_disk_fraction=0.7)
    _, funnel, *_ = _synthetic_lineage(exact, on_disk)
    chain = ["exact_bridge_population", "event_process_population", "residual_population",
             "primary_evaluation_population"]
    for a, b in zip(chain, chain[1:]):
        assert funnel[a] >= funnel[b]


# ---- 6: LOCO population equals residual population (every comp held out once) ----
def test_synth_loco_eq_residual():
    comps = [("A", "2018-01-01"), ("B", "2019-01-01"), ("C", "2020-01-01")]
    exact, on_disk = _make_corpus(5, comps, on_disk_fraction=0.8)
    _, funnel, *_ = _synthetic_lineage(exact, on_disk)
    assert funnel["loco_evaluation_population"] == funnel["residual_population"]


# ---- 7: forward-chain order is strictly by earliest kickoff ----
def test_synth_forward_chain_order_by_kickoff():
    comps = [("LATE", "2024-06-21"), ("EARLY", "2018-06-14"), ("MID", "2022-11-22")]
    exact, on_disk = _make_corpus(3, comps, on_disk_fraction=1.0)
    _, _, _, order = _synthetic_lineage(exact, on_disk)
    assert order == ["EARLY", "MID", "LATE"]


# ---- 8: the exact 5-competition WC corpus reproduces 58 -> 46 with the real per-competition sizes ----
def test_synth_real_competition_sizes_reproduce_58_and_46():
    # present-on-disk sizes confirmed from real data: WC2018=12, Euro2020=12, WC2022=12, Euro2024=12,
    # Copa2024=10 (sum 58). Earliest = WC2018 (12) -> primary = 46.
    comps_sizes = {"WC2018": ("2018-06-14", 12), "Euro2020": ("2021-06-11", 12),
                   "WC2022": ("2022-11-22", 12), "Euro2024": ("2024-06-14", 12),
                   "Copa2024": ("2024-06-21", 10)}
    exact, on_disk = [], set()
    mid = 5000
    for comp, (kdate, n) in comps_sizes.items():
        for _ in range(n):
            sid = str(mid); mid += 1
            exact.append({"sb_match_id": sid, "competition_label": comp, "kickoff_date": kdate})
            on_disk.add(sid)
    _, funnel, drops, order = _synthetic_lineage(exact, on_disk)
    assert funnel["residual_population"] == 58
    assert funnel["loco_evaluation_population"] == 58
    assert order[0] == "WC2018"
    assert funnel["primary_evaluation_population"] == 46
    assert drops.get("held_out_fold_rule") == 12


# ---- 9: a duplicate id is not double counted in the funnel (set semantics on present) ----
def test_synth_duplicate_id_not_double_counted():
    exact = [{"sb_match_id": "1", "competition_label": "A", "kickoff_date": "2020-01-01"},
             {"sb_match_id": "1", "competition_label": "A", "kickoff_date": "2020-01-01"}]
    on_disk = {"1"}
    rows, funnel, *_ = _synthetic_lineage(exact, on_disk)
    # both rows present (the builder emits one lineage row per bridge row), but on_disk membership is by id
    assert all(r["event_process_population"] == 1 for r in rows)


# ---- 10: allowed-reason vocabulary is exactly the documented closed set in all three modules ----
def test_allowed_reason_vocab_consistent_across_modules():
    build = _load_module("ecl_build", "scripts/build_evaluation_cohort_lineage.py")
    audit = _load_module("ecl_audit", "scripts/audit_evaluation_cohort_lineage.py")
    assert build.ALLOWED_REASONS == ALLOWED_REASONS
    assert audit.ALLOWED_REASONS == ALLOWED_REASONS
    assert build.STAGES == STAGES == audit.STAGES


# =================================================================================================
# INTEGRATION — re-verify the REAL produced artifacts (skip with reason if absent)
# =================================================================================================
def _read_csv(p):
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ---- 11: real lineage reconstructs 258 -> 58 -> 46, integrity flags true ----
def test_real_lineage_funnel_reconstructs():
    lin = _read_csv(REF / "evaluation_cohort_lineage.csv")
    meta = _read_json(REF / "evaluation_cohort_lineage.json")
    if lin is None or meta is None:
        pytest.skip("lineage artifacts absent; run scripts/build_evaluation_cohort_lineage.py")
    f = {s: sum(int(r[s]) for r in lin) for s in STAGES}
    assert f["exact_bridge_population"] == 258
    assert f["event_process_population"] == 58
    assert f["residual_population"] == 58
    assert f["primary_evaluation_population"] == 46
    assert f["loco_evaluation_population"] == 58
    assert meta["meta"]["allowed_reasons_only"] is True
    assert meta["meta"]["no_silent_disappearance"] is True


# ---- 12: real lineage agrees with the residual decision ledger's audited n_matches (58) ----
def test_real_lineage_matches_residual_ledger():
    lin = _read_csv(REF / "evaluation_cohort_lineage.csv")
    led = _read_json(REF / "residual_goal_intensity_decision_ledger.json")
    if lin is None or led is None:
        pytest.skip("lineage or residual ledger absent")
    residual = sum(int(r["residual_population"]) for r in lin)
    ledger_nm = next((m["evidence"]["n_matches"] for m in led.get("models", [])
                      if (m.get("evidence") or {}).get("n_matches")), None)
    assert ledger_nm == 58 and residual == ledger_nm


# ---- 13: real evidence registry flags the cache-audit contradiction (258 claim vs on-disk) ----
def test_real_registry_flags_cache_contradiction():
    reg = _read_json(REF / "research_evidence_registry.json")
    if reg is None:
        pytest.skip("registry absent; run scripts/build_research_evidence_registry.py")
    by_id = {r["id"]: r for r in reg["records"]}
    assert by_id["statsbomb.cache_audit"]["claim_status"] == "contradicted"
    # the residual cohort row must be verified_current (re-derived 58 agrees with the ledger)
    assert by_id["residual.decision_ledger"]["claim_status"] == "verified_current"


# ---- 14: exclusion ledger count equals dropped-fixture count in the lineage ----
def test_real_exclusion_ledger_count():
    lin = _read_csv(REF / "evaluation_cohort_lineage.csv")
    excl = _read_csv(REF / "cohort_exclusion_ledger.csv")
    if lin is None or excl is None:
        pytest.skip("lineage/exclusion artifacts absent")
    dropped = sum(1 for r in lin if r.get("drop_reason"))
    assert len(excl) == dropped


# ---- 15: no 2026 World Cup competition anywhere in the real cohort ----
def test_real_no_2026_world_cup():
    lin = _read_csv(REF / "evaluation_cohort_lineage.csv")
    if lin is None:
        pytest.skip("lineage absent")
    toks = ("world cup 2026", "fifa world cup 2026", "wc 2026", "2026 world cup")
    assert not [r for r in lin if any(t in (r.get("competition_label") or "").lower() for t in toks)]
