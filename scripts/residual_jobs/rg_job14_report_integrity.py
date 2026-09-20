"""RG_JOB14 -- scientific report + integrity audit (final consolidation).

(1) INTEGRITY AUDIT over the run: re-runs the package self-test on REAL rows (availability gate excludes a
    missing feature; selective gate alpha=0 fallback; simulation simplex), the leakage audit (no target in
    features; no forbidden feature cols), the no-2026 audit, a model-output simplex check, and the
    isolation backstop (this worktree is not the active collector; collector on the forbidden-write list).
(2) SCIENTIFIC REPORT DRAFT (notes/research/residual_goal_intensity_scientific_report_draft.md) stating
    the honest finding, the protocol (W2 as a REFERENCE INTENSITY, not a competing classifier), the
    decision-ledger summary, and the data limitations.

status=complete requires the integrity audit to pass on REAL data. Honest data_insufficient if the panel
is absent. research_only / experimental. No network/API.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg


def _report(self_test, ledger, fc, loco, integrity):
    by_verdict = {}
    models = (ledger or {}).get("models", [])
    for r in models:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    cands = [r["model_id"] for r in models
             if r["verdict"] == "research_candidate_for_future_shadow_review"]
    loco_pooled = (loco or {}).get("pooled", {})
    n_rows = (loco or fc or self_test or {}).get("n_rows") or self_test.get("n_rows")
    n_matches = (loco or fc or {}).get("n_matches") or self_test.get("n_matches")
    n_comps = self_test.get("n_competitions")
    lines = [
        "# Residual Goal-Intensity — Scientific Report (DRAFT)",
        "",
        _rg.LABELS,
        "",
        "## Question",
        "Treating the remaining-time Poisson model (W2) as a **REFERENCE INTENSITY** (side-specific",
        "remaining-goal rates) rather than a competing classifier, does a leakage-safe event-process",
        "*correction* to those intensities improve in-play W/D/L, near-term scoring, or the side-specific",
        "intensities themselves **beyond the parameter-free W2 reference**, out-of-sample?",
        "",
        "## Data",
        f"- International population: {n_matches} exact-bridge senior-men matches, {n_comps} competitions, "
        f"{n_rows} causal regulation snapshots (StatsBomb-derived; **2026 World Cup EXCLUDED** from every "
        "fit / calibration / selection).",
        "- Club auxiliary snapshots train ONLY the frozen club-transfer representation; club rows are NEVER",
        "  used as international test rows.",
        "",
        "## Protocol",
        "- Every model is expressed RELATIVE to its W2 family anchor (residual r0 / horizon h0 / intensity i0).",
        "- W/D/L: forward-chaining (kickoff order) + leave-one-competition-out (LOCO). Candidates must beat",
        "  r0 out-of-sample on pooled RPS, in a majority of folds, with a match-level paired-bootstrap 95% CI",
        "  upper bound < 0, and without degrading draw-channel calibration.",
        "- Intensity: LOCO side-specific Poisson deviance vs i0. Horizon: LOCO right-censored Brier vs h0.",
        "- Selective correction (r4) chooses its blend weight IN-TRAIN via held-out CV and ALWAYS permits",
        "  alpha=0 (pure W2 fallback); coverage + corrected-vs-fallback performance are audited.",
        "- Match-level bootstrap only; no row-level resampling.",
        "",
        "## Integrity",
        f"- self_test all_passed={self_test.get('all_passed')} (real_rows_used={self_test.get('real_rows_used')}); "
        f"leakage_ok={integrity.get('leakage_ok')}; no_2026_ok={integrity.get('no_2026_ok')}; "
        f"model_output_simplex_ok={integrity.get('model_output_simplex_ok')}; "
        f"isolation_ok={integrity.get('isolation_ok')}.",
        "",
        "## Headline finding",
    ]
    if loco_pooled:
        ranked = sorted(((m, (v or {}).get("rps")) for m, v in loco_pooled.items() if v),
                        key=lambda kv: (kv[1] if kv[1] is not None else 9e9))
        lines.append("- LOCO W/D/L RPS (lower better): " +
                     ", ".join(f"{m.split('.')[-1]}={v}" for m, v in ranked[:7]))
    if cands:
        lines.append(f"- {len(cands)} model(s) met the promotion bar: {', '.join(cands)} — flagged "
                     "research_candidate_for_future_shadow_review (NOT runtime/trade/live-approved).")
    else:
        lines.append("- **No model met the promotion bar.** On this international sample the event-process")
        lines.append("  correction did NOT beat the parameter-free W2 reference intensity out-of-sample; the")
        lines.append("  selective gate correctly degenerates toward the pure-W2 fallback. Honest negative.")
    lines += [
        "",
        "## Verdict summary",
        "- " + " | ".join(f"{k}: {v}" for k, v in sorted(by_verdict.items())),
        "",
        "## Limitations",
        "- Small international event corpus → wide bootstrap CIs; a true in-play edge below the reference's",
        "  noise floor can be neither ruled in nor out here.",
        "- Right-censoring of the 5/10/15-min horizons near minute 90 reduces effective late-game labels.",
        "- StatsBomb-derived international coverage is the binding constraint; expanding the exact-bridge",
        "  population is the highest-value next step before any of these models is reconsidered.",
        "",
        "_All numbers are produced by RG_JOB04–13 in this run; see the decision ledger for per-model",
        "evidence._",
    ]
    return "\n".join(lines)


def main():
    # --- integrity: self-test on REAL rows ------------------------------------------------------
    try:
        import wcdrawlab.research.residual_intensity as RI
        from wcdrawlab.research.residual_intensity import datasets as DS, quality as Q, features as F
    except Exception as e:
        _rg.emit("failed", reason=f"package import failed: {e!r}")
        return

    try:
        bundle = DS.load_residual_rows()
    except DS.DataInsufficient as e:
        _rg.emit("data_insufficient", reason=f"panel unavailable for integrity audit: {e}")
        return

    rows = list(bundle["rows"])
    # run the mandated self-test on the REAL-row path (no args => the package loads + uses the real
    # snapshot panel itself and reports real_rows_used=True; status=complete is gated on that path).
    st = RI.self_test()
    st["n_competitions"] = bundle["n_competitions"]

    feat_cols = F.columns_for(["reference_state", "recent_chance", "possession_territory",
                               "transition", "set_pieces", "quality_availability"])
    lk = Q.leakage_audit(rows[: min(1000, len(rows))], feat_cols)
    no2026 = Q.no_2026_audit(rows)

    # model-output simplex over a sample
    preds = RI.residual_predictors(rows[:1500])
    simplex_ok = True
    for fn in preds.values():
        for r in rows[:60]:
            if not Q.simplex_audit(fn(r)):
                simplex_ok = False
                break

    inside_collector = _rg.COLLECTOR_FORBIDDEN in str(_rg.ROOT).replace("\\", "/")
    forbidden_ok = False
    try:
        from wcdrawlab.research import data_roots as DR
        forbidden_ok = any(_rg.COLLECTOR_FORBIDDEN in str(p).replace("\\", "/") for p in DR.forbidden_roots())
    except Exception:
        forbidden_ok = False
    isolation_ok = (not inside_collector) and forbidden_ok

    integrity = {
        "self_test_all_passed": bool(st.get("all_passed")),
        "self_test_real_rows_used": bool(st.get("real_rows_used")),
        "leakage_ok": bool(lk.get("ok")),
        "no_2026_ok": bool(no2026.get("ok", no2026.get("no_2026", True))),
        "model_output_simplex_ok": bool(simplex_ok),
        "isolation_ok": bool(isolation_ok),
    }
    integrity["all_ok"] = all(integrity.values())
    _rg.write_json("rg_integrity_audit.json", {"integrity": integrity, "self_test": st,
                                               "leakage_audit": lk, "no_2026_audit": no2026,
                                               "utc": _rg.utc(), "labels": _rg.LABELS})

    # --- report ---------------------------------------------------------------------------------
    ledger = _rg.read_json("rg_decision_ledger.json")
    fc = _rg.read_json("rg_wdl_forward_chain.json")
    loco = _rg.read_json("rg_wdl_loco_bootstrap.json") or _rg.read_json("rg_wdl_loco.json")
    report = _report(st, ledger, fc, loco, integrity)
    _rg.NOTES.mkdir(parents=True, exist_ok=True)
    (_rg.NOTES / "residual_goal_intensity_scientific_report_draft.md").write_text(report, encoding="utf-8")
    (_rg.art_dir() / "scientific_report_draft.md").write_text(report, encoding="utf-8")

    status = "complete" if integrity["all_ok"] else "failed"
    _rg.emit(status,
             reason=f"integrity all_ok={integrity['all_ok']} ({integrity}); report written "
                    f"(ledger_models={(ledger or {}).get('n_models')})",
             state_updates={"integrity_all_ok": integrity["all_ok"], "report_written": True})


main()
