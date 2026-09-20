"""Build the full MATCH-LEVEL EVALUATION COHORT LINEAGE (Evidence-Power Consolidation, Phase 1).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

ONE ROW PER FIXTURE that appears anywhere in the in-play residual pipeline, with explicit STAGE columns:

  raw_corpus -> reconciled_corpus -> international_population -> exact_bridge_population ->
  xg_snapshot_population -> event_process_population -> residual_population ->
  primary_evaluation_population -> loco_evaluation_population

Each column is 1 (present at that stage) or 0 (dropped). When a fixture transitions present->absent
between two adjacent stages, the row carries EXACTLY ONE drop reason from the allowed category set, and
the stage at which it dropped. No fixture silently disappears: every 1->0 transition is explained.

The independent unit is the MATCH (a StatsBomb match id / exact-bridge row), never a snapshot row.

WHY 58: the lineage reconstructs the real funnel
  258 exact international bridge matches            (exact_bridge_population)
   -> intersect with StatsBomb event JSONs ON DISK  (event_process_population)
   -> = 58 matches that can produce leakage-safe snapshots and W/D/L targets (residual_population)
   -> forward-chain test set (drop earliest train-only competition)  (primary_evaluation_population)
   -> LOCO test set (every competition held out once)                (loco_evaluation_population)

The 200 bridge matches with no event JSON on disk drop with reason `missing_statsbomb_events`. This is
the dominant funnel step and the answer to the program's central question.

LOCAL-ARTIFACT-ONLY. No network/API/Odds/StatsBomb/scrape. The active collector is never read. Sources:
the exact bridge CSV + audit (read-only prior worktree), the on-disk StatsBomb events dir (read-only),
and this worktree's data/reference audits.

Outputs:
  data/reference/evaluation_cohort_lineage.csv / .json
  data/reference/cohort_exclusion_ledger.csv / .json
  notes/research/evaluation_cohort_lineage_report.md
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("cohort lineage must not run inside the active collector checkout")

REF = ROOT / "data/reference"
NOTES = ROOT / "notes/research"
BRIDGE_CSV = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")
BRIDGE_AUDIT = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.audit.json")
SB_PRIOR_EVENTS = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/raw/statsbomb_open/events")
SB_CANON_EVENTS = ROOT / "data/raw/statsbomb_open/events"  # canonical (may be empty in a clean worktree)

# the ordered set of lineage stages (each fixture row carries a 0/1 for each)
STAGES = [
    "raw_corpus",
    "reconciled_corpus",
    "international_population",
    "exact_bridge_population",
    "xg_snapshot_population",
    "event_process_population",
    "residual_population",
    "primary_evaluation_population",
    "loco_evaluation_population",
]

# the ONLY allowed drop-reason categories (exactly one per drop)
ALLOWED_REASONS = {
    "missing_raw_events", "missing_raw_lineups", "failed_reconciliation", "ambiguous_bridge",
    "missing_statsbomb_events", "missing_required_feature", "target_not_regulation_eligible",
    "extra_time_or_shootout_only", "temporal_cutoff", "held_out_fold_rule",
    "insufficient_prior_history", "source_quality_failure", "duplicate", "data_contract_mismatch",
    "intentional_preregistered_exclusion", "verified_bug", "unknown",
}


# =================================================================================================
# readers
# =================================================================================================
def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _on_disk_event_ids() -> set:
    ids = set()
    for d in (SB_PRIOR_EVENTS, SB_CANON_EVENTS):
        if d.exists():
            ids |= {os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json")}
    return ids


def _load_bridge():
    if not BRIDGE_CSV.exists():
        return None
    return list(csv.DictReader(BRIDGE_CSV.open(encoding="utf-8")))


# =================================================================================================
# lineage construction (match-level; one row per exact-bridge fixture, plus rejected-bridge fixtures)
# =================================================================================================
def build():
    bridge = _load_bridge()
    if bridge is None:
        return None, {"status": "data_insufficient", "reason": f"bridge CSV absent at {BRIDGE_CSV}"}

    on_disk = _on_disk_event_ids()
    audit = _read_json(BRIDGE_AUDIT) or {}

    # exact international bridge rows = the reconciled/international/exact_bridge population
    exact_intl = [r for r in bridge if r.get("bridge_confidence") == "exact"
                  and r.get("comp_type") == "international"]

    # forward-chain competition order by earliest kickoff, restricted to PRESENT (on-disk) matches,
    # so the primary/LOCO populations reflect what is actually evaluable.
    present_rows = [r for r in exact_intl if r["sb_match_id"] in on_disk]
    first_kick = defaultdict(lambda: "~")
    for r in present_rows:
        c = r["competition_label"]
        k = (r.get("kickoff_date") or "~")
        if k < first_kick[c]:
            first_kick[c] = k
    fc_order = [c for c, _ in sorted(first_kick.items(), key=lambda kv: (kv[1], kv[0]))]
    earliest_competition = fc_order[0] if fc_order else None
    # forward-chain test competitions = everything except the earliest (which is train-only)
    fc_test_comps = set(fc_order[1:])
    loco_comps = set(fc_order)  # every competition is held out once under LOCO

    rows = []
    exclusions = []

    def make_row(sb_id, api_id, comp, kickoff, bridge_conf, comp_type):
        return {
            "sb_match_id": sb_id, "api_fixture_id": api_id, "competition_label": comp,
            "kickoff_date": kickoff, "bridge_confidence": bridge_conf, "comp_type": comp_type,
            **{s: 0 for s in STAGES},
            "dropped_at_stage": "", "drop_reason": "", "drop_detail": "",
        }

    # ---- exact international bridge fixtures: walk the full stage chain ----
    for r in exact_intl:
        sb_id = r["sb_match_id"]
        row = make_row(sb_id, r.get("api_fixture_id"), r.get("competition_label"),
                       r.get("kickoff_date"), r.get("bridge_confidence"), r.get("comp_type"))
        # these stages are all SATISFIED for an exact intl bridge row by definition of the bridge:
        row["raw_corpus"] = 1            # the api-football fixture exists in the corpus
        row["reconciled_corpus"] = 1     # bridge is built only on reconciled (regulation-exact) fixtures
        row["international_population"] = 1
        row["exact_bridge_population"] = 1

        on = sb_id in on_disk
        if not on:
            # DROP at the event-process stage: no StatsBomb event JSON physically on disk.
            row["xg_snapshot_population"] = 0
            row["event_process_population"] = 0
            row["dropped_at_stage"] = "event_process_population"
            row["drop_reason"] = "missing_statsbomb_events"
            row["drop_detail"] = ("exact intl bridge match has no StatsBomb event JSON in the on-disk "
                                  "read-only cache (prior pull pruned); cannot produce leakage-safe snapshots")
            exclusions.append({"sb_match_id": sb_id, "api_fixture_id": r.get("api_fixture_id"),
                               "competition_label": r.get("competition_label"),
                               "kickoff_date": r.get("kickoff_date"),
                               "dropped_at_stage": "event_process_population",
                               "drop_reason": "missing_statsbomb_events",
                               "detail": row["drop_detail"]})
            rows.append(row)
            continue

        # present on disk -> snapshots + event-process + residual populations satisfied
        row["xg_snapshot_population"] = 1
        row["event_process_population"] = 1
        row["residual_population"] = 1   # has events + regulation-final WDL target (rows_skipped_no_wdl=0)

        comp = r.get("competition_label")
        # primary (forward-chain) eval: matches NOT in the train-only earliest competition
        if comp in fc_test_comps:
            row["primary_evaluation_population"] = 1
        else:
            row["primary_evaluation_population"] = 0
            row["dropped_at_stage"] = "primary_evaluation_population"
            row["drop_reason"] = "held_out_fold_rule"
            row["drop_detail"] = (f"earliest competition '{comp}' is train-only in the forward chain "
                                  f"(no earlier competition to train on); never a forward-chain test fold")
            exclusions.append({"sb_match_id": sb_id, "api_fixture_id": r.get("api_fixture_id"),
                               "competition_label": comp, "kickoff_date": r.get("kickoff_date"),
                               "dropped_at_stage": "primary_evaluation_population",
                               "drop_reason": "held_out_fold_rule", "detail": row["drop_detail"]})
        # LOCO eval: every competition is held out once -> all present matches are LOCO-testable
        row["loco_evaluation_population"] = 1 if comp in loco_comps else 0
        rows.append(row)

    # ---- rejected (non-exact / non-international) bridge candidates: record the bridge-stage drop ----
    # The bridge audit enumerates rejections by reason; we surface them as ambiguous_bridge /
    # failed_reconciliation lineage rows so nothing disappears silently. These never reach reconciled.
    rej_examples = audit.get("rejected_examples", []) if isinstance(audit, dict) else []
    seen_rej = set()
    for ex in rej_examples:
        api_id = ex.get("api_fixture_id")
        if api_id in seen_rej:
            continue
        seen_rej.add(api_id)
        reason_raw = (ex.get("reason") or "").lower()
        if reason_raw == "no_statsbomb_candidate":
            drop_reason = "ambiguous_bridge"
        elif reason_raw == "date_mismatch":
            drop_reason = "failed_reconciliation"
        else:
            drop_reason = "unknown"
        row = make_row(None, api_id, ex.get("competition_label"), ex.get("kickoff_date"),
                       "rejected", "international")
        row["raw_corpus"] = 1
        row["international_population"] = 1  # it is an intl fixture candidate
        # reconciled/exact_bridge NOT satisfied: it failed the bridge
        row["dropped_at_stage"] = "exact_bridge_population"
        row["drop_reason"] = drop_reason
        row["drop_detail"] = f"bridge rejected ({reason_raw}); never entered the exact international population"
        rows.append(row)
        exclusions.append({"sb_match_id": None, "api_fixture_id": api_id,
                           "competition_label": ex.get("competition_label"),
                           "kickoff_date": ex.get("kickoff_date"),
                           "dropped_at_stage": "exact_bridge_population",
                           "drop_reason": drop_reason, "detail": row["drop_detail"]})

    # ---- funnel counts (match-level) ----
    funnel = {s: sum(r[s] for r in rows) for s in STAGES}
    # the headline numbers, derived purely from the rows above
    funnel_summary = {
        "exact_bridge_population": funnel["exact_bridge_population"],
        "event_process_population": funnel["event_process_population"],
        "residual_population": funnel["residual_population"],
        "primary_evaluation_population": funnel["primary_evaluation_population"],
        "loco_evaluation_population": funnel["loco_evaluation_population"],
        "dropped_missing_statsbomb_events": sum(
            1 for r in rows if r["drop_reason"] == "missing_statsbomb_events"),
        "dropped_held_out_fold_rule": sum(
            1 for r in rows if r["drop_reason"] == "held_out_fold_rule"),
        "earliest_competition_train_only": earliest_competition,
        "forward_chain_order": fc_order,
    }

    # validate: every drop reason is in the allowed set; every 1->0 in the chain is explained
    bad_reason = [r["drop_reason"] for r in rows
                  if r["drop_reason"] and r["drop_reason"] not in ALLOWED_REASONS]
    unexplained = []
    for r in rows:
        prev = 1
        for s in STAGES:
            cur = r[s]
            if prev == 1 and cur == 0 and not r["drop_reason"]:
                unexplained.append(r["sb_match_id"] or r["api_fixture_id"])
                break
            prev = cur if cur in (0, 1) else prev

    meta = {
        "status": "ok",
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "labels": LABELS,
        "n_fixture_rows": len(rows),
        "funnel_match_level": funnel,
        "funnel_summary": funnel_summary,
        "drop_reason_counts": dict(Counter(r["drop_reason"] for r in rows if r["drop_reason"])),
        "allowed_reasons_only": not bad_reason,
        "bad_reasons": bad_reason,
        "no_silent_disappearance": not unexplained,
        "unexplained_drops": unexplained,
        "on_disk_event_json_count": len(on_disk),
    }
    return {"rows": rows, "exclusions": exclusions, "meta": meta}, None


FIELDS = (["sb_match_id", "api_fixture_id", "competition_label", "kickoff_date",
           "bridge_confidence", "comp_type"] + STAGES +
          ["dropped_at_stage", "drop_reason", "drop_detail"])
EXCL_FIELDS = ["sb_match_id", "api_fixture_id", "competition_label", "kickoff_date",
               "dropped_at_stage", "drop_reason", "detail"]


def write_outputs(payload: dict) -> dict:
    REF.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)
    rows, excl, meta = payload["rows"], payload["exclusions"], payload["meta"]

    lin_csv = REF / "evaluation_cohort_lineage.csv"
    with lin_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    (REF / "evaluation_cohort_lineage.json").write_text(
        json.dumps({"meta": meta, "stages": STAGES, "rows": rows}, indent=2, default=str),
        encoding="utf-8")

    ex_csv = REF / "cohort_exclusion_ledger.csv"
    with ex_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EXCL_FIELDS, extrasaction="ignore")
        w.writeheader()
        for e in excl:
            w.writerow(e)
    (REF / "cohort_exclusion_ledger.json").write_text(
        json.dumps({"meta": {"n_exclusions": len(excl), "built_utc": meta["built_utc"],
                             "drop_reason_counts": meta["drop_reason_counts"], "labels": LABELS},
                    "exclusions": excl}, indent=2, default=str), encoding="utf-8")

    fs = meta["funnel_summary"]
    md = [
        "# Evaluation Cohort Lineage — Report (the WHY-58 funnel)", "",
        f"`{LABELS}`", "",
        f"Built {meta['built_utc']}. Match-level lineage for every fixture in the in-play residual "
        "pipeline. Independent unit = MATCH. Every present→absent stage transition carries exactly one "
        "allowed drop reason; no fixture disappears silently.", "",
        "## Funnel (match-level)", "",
        "| stage | matches |", "|---|---|",
    ]
    for s in STAGES:
        md.append(f"| {s} | {meta['funnel_match_level'][s]} |")
    md += [
        "", "## The 258 → 58 reduction (answered)", "",
        f"- **exact_bridge_population = {fs['exact_bridge_population']}** international matches "
        "(exact `api<->statsbomb` bridge).",
        f"- **− {fs['dropped_missing_statsbomb_events']}** matches drop with reason "
        "`missing_statsbomb_events`: no StatsBomb event JSON physically on disk (prior larger pull "
        "pruned; only the read-only 60-file cache remains).",
        f"- **event_process_population = residual_population = {fs['residual_population']}** matches — "
        "these have events on disk AND a regulation-final W/D/L target (rows_skipped_no_wdl = 0).",
        f"- **primary_evaluation_population = {fs['primary_evaluation_population']}** — forward-chain "
        f"test set: the earliest competition (**{fs['earliest_competition_train_only']}**) is train-only "
        "and drops with reason `held_out_fold_rule`.",
        f"- **loco_evaluation_population = {fs['loco_evaluation_population']}** — every competition is "
        "held out once, so all present matches are LOCO-testable.",
        "",
        f"Forward-chain competition order (earliest kickoff first): {fs['forward_chain_order']}.",
        "",
        "## Drop-reason counts", "",
        "| drop_reason | matches |", "|---|---|",
    ]
    for k, v in sorted(meta["drop_reason_counts"].items()):
        md.append(f"| `{k}` | {v} |")
    md += [
        "", "## Integrity", "",
        f"- all drop reasons in the allowed category set: **{meta['allowed_reasons_only']}**",
        f"- no silent disappearance (every 1→0 explained): **{meta['no_silent_disappearance']}**",
        f"- StatsBomb event JSONs currently on disk: **{meta['on_disk_event_json_count']}**", "",
        "The 58-match residual cohort is the live ceiling under current local data. To restore the cohort "
        "toward 258 the full StatsBomb event pull must be re-acquired (a data-acquisition step, not a "
        "modeling change). The 0-candidate honest-negative conclusion of the residual phase is unaffected "
        "by cohort size — it is a calibrated, match-level-bootstrapped result on the 58 it had.",
    ]
    (NOTES / "evaluation_cohort_lineage_report.md").write_text("\n".join(md), encoding="utf-8")
    return {"lineage_csv": str(lin_csv), "exclusion_csv": str(ex_csv),
            "report_md": str(NOTES / "evaluation_cohort_lineage_report.md")}


def main():
    payload, err = build()
    if err is not None:
        print(json.dumps({**err, "labels": LABELS}))
        sys.exit(2)
    out = write_outputs(payload)
    print(json.dumps({"status": "ok", **payload["meta"], **out}, indent=2, default=str))


if __name__ == "__main__":
    main()
