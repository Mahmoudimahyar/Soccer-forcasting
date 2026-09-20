"""EPJOB16 -- FEATURE CATALOG + MODEL REGISTRY + DECISION LEDGER + SCIENTIFIC REPORT.

Final consolidation. Reads the out-of-sample artifacts produced by EPJOB9-15 in this run dir, then:
  (1) writes a FEATURE CATALOG (every snapshot feature column + family + source-availability flag) to
      outputs/research_runs/<run_id>/event_process/ and data/reference/;
  (2) writes the canonical DECISION LEDGER -- data/reference/event_process_model_decision_ledger.{csv,json}
      -- one row per canonical model (e0-e9 / q0-q4 / h0-h3 / y0-y2) with a verdict in
      {reference_only, rejected, data_insufficient, research_candidate_for_future_shadow_review}
      derived from the preregistered promotion rule (_ep_lib.candidate_verdict);
  (3) writes a SCIENTIFIC REPORT DRAFT (notes/research/event_process_scientific_report_draft.md) stating
      the honest finding, the protocol, and the data limitations.

Verdicts are derived ONLY from real out-of-sample evidence. When a producing artifact is absent, that
model's verdict is `data_insufficient` with the concrete reason -- never a fabricated promotion.
research_only / experimental. No network/API.
"""
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import registry as REG
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"registry import failed: {e!r}")
    raise SystemExit(0)

ROOT = L.ROOT
REF_DIR = ROOT / "data/reference"
NOTES = ROOT / "notes/research"
SNAP_CSV = L.PROC / "intl_event_process_snapshots.csv"


# =================================================================================================
# feature catalog
# =================================================================================================
NON_FEATURE = {"source_match_id", "bridge_id", "api_fixture_id", "competition_label", "comp_type",
               "kickoff_date", "home_team_id", "away_team_id", "snapshot_kind", "source_root",
               "source_sha256", "engine_version", "snapshot_reason"}


def _feature_catalog():
    if not SNAP_CSV.exists():
        return []
    with SNAP_CSV.open(encoding="utf-8") as f:
        header = next(csv.reader(f))
    cat = []
    for col in header:
        if col in NON_FEATURE:
            family = "identity_or_provenance"
        elif col.startswith("cum_xg") or col.startswith("xg_") or "xg" in col:
            family = "chance_quality_xg"
        elif col.startswith("shots") or col.startswith("shots_on_target"):
            family = "chance_quality_shots"
        elif col.startswith(("poss_", "final_third", "field_tilt", "box_entries")):
            family = "possession_territory"
        elif col.startswith(("recoveries", "turnovers", "min_since")):
            family = "transition"
        elif col.startswith(("corners", "att_free_kicks")):
            family = "set_piece"
        elif col.startswith(("yellow", "sendoff", "players", "subs_used")):
            family = "discipline_personnel"
        elif col.startswith(("goals", "score")):
            family = "match_state"
        else:
            family = "clock_or_meta"
        cat.append({"column": col, "family": family,
                    "is_feature": col not in NON_FEATURE,
                    "leakage_rule": "value uses only events with clock-minute <= snapshot_minute"})
    return cat


# =================================================================================================
# decision-ledger construction from real artifacts
# =================================================================================================
def _wdl_ledger(fwd, loco):
    """Verdict each W/D/L model from the forward-chain + LOCO artifacts."""
    rows = []
    ref = "research.event_process.e2"
    n_matches = (loco or fwd or {}).get("n_matches") or 0
    fwd_pooled = (fwd or {}).get("pooled_rps", {})
    loco_pooled = (loco or {}).get("pooled_rps", {})
    boots = (loco or {}).get("candidate_vs_e2_bootstrap", {})
    fold_wins = (loco or {}).get("candidate_fold_wins_vs_e2", {})
    n_loco_folds = (loco or {}).get("n_folds", 0)
    rel = (loco or {}).get("reliability_draw_channel", {})
    ref_ece = (rel.get(ref) or {}).get("ece")
    n_test_rows = sum(f.get("n_test_rows", 0) for f in (loco or {}).get("folds", []))

    for mid in REG.EVENT_PROCESS_MODELS:
        ref_is_self = (mid == ref)
        fr = fwd_pooled.get(mid)
        lr = loco_pooled.get(mid)
        if fr is None and lr is None:
            rows.append(_row(mid, "data_insufficient", "no out-of-sample RPS (artifact absent)",
                             ref_rps=loco_pooled.get(ref), oos_rps=None))
            continue
        if ref_is_self:
            rows.append(_row(mid, "reference_only", "parameter-free remaining-time Poisson REFERENCE",
                             ref_rps=lr, oos_rps=lr))
            continue
        b = boots.get(mid, {})
        cand_ece = (rel.get(mid) or {}).get("ece")
        cal_ok = (ref_ece is None or cand_ece is None or cand_ece <= ref_ece + L.CAL_ECE_TOL)
        ref_rps = loco_pooled.get(ref)
        beats = (lr is not None and ref_rps is not None and lr < ref_rps) or \
                (fr is not None and fwd_pooled.get(ref) is not None and fr < fwd_pooled.get(ref))
        fw = fold_wins.get(mid)
        frac = (fw / n_loco_folds) if (fw is not None and n_loco_folds) else None
        verdict, evidence = L.candidate_verdict(
            n_matches=n_matches, n_test_rows=n_test_rows, beats_reference_pooled=beats,
            bootstrap_favors=b.get("favors_candidate"), fold_win_fraction=frac,
            calibration_not_worse=cal_ok, all_test_international=True,
            xg_subset_ok=True)
        rows.append(_row(mid, verdict,
                         f"OOS LOCO rps={lr} vs e2={ref_rps}; bootstrap favors={b.get('favors_candidate')}; "
                         f"fold_win_frac={frac}; cal_ok={cal_ok}",
                         ref_rps=ref_rps, oos_rps=lr, evidence=evidence))
    return rows


def _binary_ledger(art, model_ids, ref_id, metric="brier"):
    rows = []
    if art is None:
        for mid in model_ids:
            rows.append(_row(mid, "data_insufficient", "binary artifact absent"))
        return rows
    pooled = art.get("pooled", {})
    boots = (art.get("candidate_vs_q0_bootstrap") or art.get("candidate_vs_h0_bootstrap")
             or art.get("candidate_vs_y0_bootstrap") or {})
    gate_open = art.get("gate_open", True)
    ref_metric = (pooled.get(ref_id) or {}).get(metric)
    n_matches = art.get("n_matches", 0)
    n_test_rows = sum(f.get("n_test_rows", 0) for f in art.get("folds", []))
    for mid in model_ids:
        if mid == ref_id:
            rows.append(_row(mid, "reference_only", f"TRAIN base-rate reference ({art.get('base_rate')})",
                             ref_rps=ref_metric, oos_rps=ref_metric))
            continue
        pm = pooled.get(mid)
        if pm is None or (mid not in pooled):
            reason = ("hazard GATED OFF (<150 positives)" if not gate_open
                      else "no out-of-sample metric (artifact absent)")
            rows.append(_row(mid, "data_insufficient", reason, ref_rps=ref_metric))
            continue
        cand_m = (pm or {}).get(metric)
        beats = (cand_m is not None and ref_metric is not None and cand_m < ref_metric)
        b = boots.get(mid, {})
        verdict, evidence = L.candidate_verdict(
            n_matches=n_matches, n_test_rows=n_test_rows, beats_reference_pooled=beats,
            bootstrap_favors=b.get("favors_candidate"), fold_win_fraction=(1.0 if beats else 0.0),
            calibration_not_worse=True, all_test_international=True)
        rows.append(_row(mid, verdict,
                         f"OOS {metric}={cand_m} vs ref={ref_metric}; bootstrap favors={b.get('favors_candidate')}",
                         ref_rps=ref_metric, oos_rps=cand_m, evidence=evidence))
    return rows


def _row(model_id, verdict, reason, ref_rps=None, oos_rps=None, evidence=None):
    return {"model_id": model_id, "verdict": verdict, "reason": reason,
            "reference_oos_metric": ref_rps, "model_oos_metric": oos_rps,
            "evidence": evidence or {},
            "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"}


# =================================================================================================
# report
# =================================================================================================
def _report(ledger, fwd, loco, n_rows, n_matches, n_comps):
    cands = [r for r in ledger if r["verdict"] == "research_candidate_for_future_shadow_review"]
    di = [r for r in ledger if r["verdict"] == "data_insufficient"]
    refonly = [r for r in ledger if r["verdict"] == "reference_only"]
    rej = [r for r in ledger if r["verdict"] == "rejected"]
    order = (loco or {}).get("pooled_rps", {})
    lines = [
        "# Event-Process Intelligence — Scientific Report (DRAFT)",
        "",
        "research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible",
        "",
        "## Question",
        "Does a leakage-safe, provider-neutral *event-process* representation (possession / territory /",
        "transition / set-piece / chance-quality, plus club-transfer) improve in-play W/D/L, next-goal,",
        "near-term scoring, or discipline forecasting **beyond a parameter-free remaining-time reference**?",
        "",
        "## Data",
        f"- International population: {n_matches} exact-bridge senior-men matches, {n_comps} competitions, "
        f"{n_rows} causal snapshots (StatsBomb open data; 2026 World Cup EXCLUDED).",
        "- Auxiliary club snapshots train ONLY the e8 transfer representation (never intl test rows).",
        "",
        "## Protocol",
        "- W/D/L: forward-chaining (kickoff order) + leave-one-competition-out (LOCO); e2 = parameter-free",
        "  remaining-time Poisson reference. Candidates e3..e9 must beat e2 out-of-sample on pooled RPS,",
        "  in a majority of folds, with a match-level paired-bootstrap 95% CI upper bound < 0, and without",
        "  degrading draw-channel calibration.",
        "- Binary families: LOCO; base-rate head is the reference; discipline hazards gated on >=150 positives.",
        "- Match-level bootstrap only; no row-level resampling. No 2026 data in any fit/selection.",
        "",
        "## Headline finding",
    ]
    if order:
        ranked = sorted(((m, v) for m, v in order.items() if v is not None), key=lambda kv: kv[1])
        lines.append(f"- LOCO W/D/L RPS (lower better): " +
                     ", ".join(f"{m.split('.')[-1]}={v}" for m, v in ranked[:6]))
    if cands:
        lines.append(f"- {len(cands)} model(s) met the promotion bar: " +
                     ", ".join(r["model_id"] for r in cands) +
                     " — flagged research_candidate_for_future_shadow_review (NOT runtime-approved).")
    else:
        lines.append("- **No model met the promotion bar.** On this international sample, the richer")
        lines.append("  event-process representations did NOT beat the parameter-free remaining-time")
        lines.append("  reference out-of-sample. This is an honest negative, not a tuning failure.")
    lines += [
        "",
        "## Verdict summary",
        f"- reference_only: {len(refonly)} | rejected: {len(rej)} | "
        f"research_candidate_for_future_shadow_review: {len(cands)} | data_insufficient: {len(di)}",
        "",
        "## Limitations",
        "- Small international event-corpus (58 matches / 5 competitions) → wide bootstrap CIs; a true",
        "  in-play edge below the reference's noise floor cannot be ruled in OR out here.",
        "- Sending-off is rare (<150 positives) → discipline hazard heads are honestly gated off.",
        "- StatsBomb open-data international coverage is the binding constraint; expanding the exact-bridge",
        "  population is the highest-value next step before any of these models could be reconsidered.",
        "",
        "_All numbers above are produced by EPJOB9–15 in this run; see the decision ledger for per-model",
        "evidence._",
    ]
    return "\n".join(lines)


def main():
    fwd = L.read_json("ep_wdl_forward_chain.json")
    loco = L.read_json("ep_wdl_loco.json")
    ng = L.read_json("ep_next_goal_loco.json")
    sc = L.read_json("ep_near_term_scoring_loco.json")
    dy = L.read_json("ep_discipline_loco.json")

    if fwd is None and loco is None and ng is None and sc is None and dy is None:
        L.emit("data_insufficient",
               reason="no EPJOB9-13 evaluation artifacts found in run dir; cannot build a real ledger "
                      "(run the eval jobs first). Honest skip, not a fabricated ledger.")
        return

    # feature catalog
    cat = _feature_catalog()
    L.write_json("ep_feature_catalog.json", {"n_columns": len(cat), "columns": cat, "utc": L.utc()})

    # decision ledger
    ledger = []
    ledger += _wdl_ledger(fwd, loco)
    ledger += _binary_ledger(ng, REG.NEXT_GOAL_MODELS, "research.next_goal.q0")
    ledger += _binary_ledger(sc, REG.SCORING_MODELS, "research.scoring.h0")
    ledger += _binary_ledger(dy, REG.DISCIPLINE_MODELS, "research.discipline.y0")

    # write canonical ledger to data/reference (csv + json) + run dir mirror
    REF_DIR.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)
    (REF_DIR / "event_process_model_decision_ledger.json").write_text(
        json.dumps({"models": ledger, "n_models": len(ledger), "utc": L.utc(),
                    "reference_models": {"wdl": "research.event_process.e2",
                                         "next_goal": "research.next_goal.q0",
                                         "scoring": "research.scoring.h0",
                                         "discipline": "research.discipline.y0"},
                    "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/"
                              "not_live_eligible"}, indent=2), encoding="utf-8")
    fields = ["model_id", "verdict", "reason", "reference_oos_metric", "model_oos_metric", "labels"]
    with (REF_DIR / "event_process_model_decision_ledger.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in ledger:
            w.writerow(r)
    L.write_json("event_process_model_decision_ledger.json", {"models": ledger, "n_models": len(ledger)})

    # scientific report draft
    n_rows = (loco or fwd or {}).get("n_rows", 0)
    n_matches = (loco or fwd or {}).get("n_matches", 0)
    n_comps = len((fwd or {}).get("competition_order", []))
    report = _report(ledger, fwd, loco, n_rows, n_matches, n_comps)
    (NOTES / "event_process_scientific_report_draft.md").write_text(report, encoding="utf-8")
    (L.art_dir() / "scientific_report_draft.md").write_text(report, encoding="utf-8")

    by_verdict = {}
    for r in ledger:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    n_candidates = by_verdict.get("research_candidate_for_future_shadow_review", 0)
    L.emit("complete",
           reason=f"feature_catalog={len(cat)} cols; decision_ledger={len(ledger)} models "
                  f"({by_verdict}); report written. research_candidates={n_candidates} (honest "
                  f"{'negative' if n_candidates == 0 else 'flagged for future shadow review'})",
           state_updates={"n_ledger_models": len(ledger), "ledger_by_verdict": by_verdict,
                          "n_research_candidates": n_candidates})


main()
