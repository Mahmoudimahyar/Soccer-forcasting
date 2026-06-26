"""Phase 5: coverage-recovery (masking) experiment. Question: can high-confidence silver labels expand
historical event coverage where structured labels are masked? For APPROVED classes, on each held-out
competition (models fit on the OTHER competitions), mask the true events and reconstruct from silver
emissions; measure recovered coverage, false-positive burden, timing. NOT an outcome-model experiment.
research_only / historical_weak_supervision_only / not_live_eligible.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from wcdrawlab.research.commentary import precision_models as PM  # noqa: E402
from wcdrawlab.research.commentary import silver_label_policy as SP  # noqa: E402
import evaluate_commentary_precision_models as EV  # noqa: E402


def _approved():
    g = ROOT / "notes/research/commentary_silver_label_gate.json"
    if not g.exists():
        return []
    d = json.loads(g.read_text(encoding="utf-8"))
    return [c for c, v in d.get("classes", {}).items()
            if v.get("label") == "silver_label_approved_for_historical_research"]


def main():
    approved = _approved()
    res = {"approved_classes": approved, "per_class": {}}
    if not approved:
        res["verdict"] = "insufficient_quality_or_coverage"
        res["note"] = "no class passed the silver gate -> nothing to recover with"
        _write(res); print(json.dumps(res, indent=2)); return

    matched, ev_idx, seg_idx = EV.assemble()
    comps = sorted({m.split("/")[0] for m in matched})
    per = {c: {"true": 0, "recovered": 0, "emitted": 0, "fp": 0, "timings": [], "comps": set()} for c in approved}

    for held in comps:
        train_m = [m for m in matched if m.split("/")[0] != held]
        test_m = [m for m in matched if m.split("/")[0] == held]
        tr_text, tr_norm = [], []
        tr_y = {c: [] for c in approved}
        for m in train_m:
            for s in seg_idx[m]:
                tr_text.append(s["text"]); tr_norm.append(s["norm"])
                for c in approved:
                    lab, _ = EV.label_for(ev_idx, m, s["half"], s["t_s"], c)
                    tr_y[c].append(lab)
        pm = PM.PrecisionModels().fit(tr_text, tr_y)
        Xtr = pm.vec.transform(tr_text)
        thr = {}
        for c in approved:
            mdl = pm.models.get(c)
            probs = list(mdl.predict_proba(Xtr)[:, 1]) if mdl is not None else [0.0] * len(tr_text)
            conf = [(pm.alpha * p + (1 - pm.alpha) * PM.r1_rule_score(nt, c)) if PM.r1_rule_score(nt, c) > 0 else 0.0
                    for p, nt in zip(probs, tr_norm)]
            thr[c], _, _ = SP.select_threshold(conf, tr_y[c])
        # test emissions
        te_text, te_norm, te_meta = [], [], []
        for m in test_m:
            for s in seg_idx[m]:
                te_text.append(s["text"]); te_norm.append(s["norm"]); te_meta.append((m, s["half"], s["t_s"]))
        Xte = pm.vec.transform(te_text) if te_text else None
        for c in approved:
            mdl = pm.models.get(c)
            probs = list(mdl.predict_proba(Xte)[:, 1]) if (mdl is not None and Xte is not None) else [0.0] * len(te_text)
            recovered_events = set()
            for idx, (p, nt) in enumerate(zip(probs, te_norm)):
                rule = PM.r1_rule_score(nt, c)
                conf = (pm.alpha * p + (1 - pm.alpha) * rule) if rule > 0 else 0.0
                if conf < thr[c] or conf <= 0:
                    continue
                m_, half_, t_ = te_meta[idx]
                dts = ev_idx[m_].get((half_, c), [])
                per[c]["emitted"] += 1
                if dts:
                    ne = min(dts, key=lambda et: abs(et - t_))
                    if abs(ne - t_) <= EV.WINDOW:
                        recovered_events.add((m_, half_, round(ne, 1)))
                        per[c]["timings"].append(abs(ne - t_))
                        per[c]["comps"].add(held)
                        continue
                per[c]["fp"] += 1
            # true events for this held-out comp
            for m_ in test_m:
                for (half_, cc), dts in ev_idx[m_].items():
                    if cc == c:
                        per[c]["true"] += len(dts)
            per[c]["recovered"] += len(recovered_events)
        print(f"  recovery fold {held} done", flush=True)

    for c in approved:
        d = per[c]
        cov = d["recovered"] / d["true"] if d["true"] else None
        fp_burden = d["fp"] / d["emitted"] if d["emitted"] else None
        res["per_class"][c] = {
            "true_events": d["true"], "recovered_events": d["recovered"],
            "coverage_recall": _r(cov), "emitted": d["emitted"], "false_positive_burden": _r(fp_burden),
            "timing_median_s": _r(statistics.median(d["timings"]) if d["timings"] else None),
            "timing_p90_s": _r(sorted(d["timings"])[max(0, int(0.9 * len(d["timings"])) - 1)] if d["timings"] else None),
            "competitions": len(d["comps"]),
        }
    # verdict
    good = [c for c, v in res["per_class"].items()
            if v["coverage_recall"] and v["coverage_recall"] >= 0.5 and v["false_positive_burden"] is not None
            and v["false_positive_burden"] <= 0.20]
    if good and len(good) == len(approved):
        res["verdict"] = "useful_for_historical_event_coverage_recovery"
    elif good:
        res["verdict"] = "useful_for_high-confidence_subset_only"
    else:
        res["verdict"] = "not_useful_beyond_taxonomy_research"
    _write(res); print(json.dumps(res, indent=2))


def _write(res):
    (ROOT / "data/processed").mkdir(parents=True, exist_ok=True)
    (ROOT / "notes/research/_phase5_recovery.json").write_text(json.dumps(res, indent=2), encoding="utf-8")


def _r(x):
    return round(x, 4) if isinstance(x, float) else x


if __name__ == "__main__":
    main()
