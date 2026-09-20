"""Follow-on: build the FLAGGED low-confidence historical-signal dataset for the classes the V2 gate marked
'usable_only_with_low_confidence_flag' (corner, foul, yellow_card). These are explicitly NOT silver labels
and NOT ground truth. NO raw commentary text. historical_weak_supervision_only / not_live_eligible /
not_runtime_approved / not_trade_eligible.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

MODEL_VERSION = "precision_v2_lowconf"
FORBIDDEN = {"text", "normalized_text", "norm", "raw", "commentary_text", "utterance"}
SOURCE_RIGHTS = "echoes=CC_BY_4.0;soccernet_labels=non_commercial_research"
ALLOWED_LABEL = "usable_only_with_low_confidence_flag"


def low_conf_classes():
    g = ROOT / "notes/research/commentary_silver_label_gate.json"
    if not g.exists():
        return {}
    d = json.loads(g.read_text(encoding="utf-8"))
    return {c: v.get("wilson_lb") for c, v in d.get("classes", {}).items() if v.get("label") == ALLOWED_LABEL}


def to_low_conf_record(em, wilson_lb, source_hash=""):
    """Build one schema-compliant flagged low-confidence record (NO raw text, is_silver=false)."""
    return {
        "canonical_match_id": em["match_id"],
        "commentary_record_id": em["commentary_record_id"],
        "commentary_content_hash": em["content_hash"],
        "source_id": "soccernet_echoes+soccernet_labels",
        "source_rights_classification": SOURCE_RIGHTS,
        "competition": em["competition"], "season": em["season"],
        "event_class": em["event_class"],
        "model_confidence_score": round(float(em["confidence"]), 4),
        "confidence_tier": "low_confidence",
        "quality_estimate_precision_wilson_lb": round(float(wilson_lb), 4) if wilson_lb is not None else None,
        "event_time_s": round(float(em["event_time_s"]), 2),
        "alignment_delta_s": round(float(em["alignment_delta_s"]), 2),
        "parser_model_version": MODEL_VERSION, "source_hash": source_hash,
        "is_silver": False,
        "causal_status": "historical_weak_supervision_only",
        "live_eligibility": False, "runtime_eligibility": False, "trading_eligibility": False,
    }


def assert_no_raw_text(records):
    for r in records:
        bad = FORBIDDEN & set(r.keys())
        if bad:
            raise AssertionError(f"raw-text field leaked into low-confidence dataset: {bad}")


def assert_flagged_non_silver_non_live(records, allowed_classes):
    for r in records:
        assert r["is_silver"] is False
        assert r["confidence_tier"] == "low_confidence"
        assert r["causal_status"] == "historical_weak_supervision_only"
        assert r["live_eligibility"] is False and r["runtime_eligibility"] is False and r["trading_eligibility"] is False
        assert r["event_class"] in allowed_classes, f"non-eligible class {r['event_class']}"


def main():
    import evaluate_commentary_precision_models as EV
    from wcdrawlab.research.commentary import precision_models as PM
    from wcdrawlab.research.commentary import silver_label_policy as SP
    classes = low_conf_classes()
    out = ROOT / "data/processed/commentary_low_confidence_signals.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not classes:
        (ROOT / "notes/research/commentary_low_confidence_signals_manifest.json").write_text(
            json.dumps({"n_records": 0, "classes": []}, indent=2), encoding="utf-8")
        print("no low-confidence classes -> empty"); return
    matched, ev_idx, seg_idx = EV.assemble()
    texts, norms, meta = [], [], []
    y = {c: [] for c in classes}
    for m in matched:
        for s in seg_idx[m]:
            texts.append(s["text"]); norms.append(s["norm"]); meta.append((m, s["half"], s["t_s"], s["content_hash"]))
            for c in classes:
                lab, _ = EV.label_for(ev_idx, m, s["half"], s["t_s"], c)
                y[c].append(lab)
    pm = PM.PrecisionModels().fit(texts, y)
    Xtr = pm.vec.transform(texts)
    records = []
    for c, wlb in classes.items():
        mdl = pm.models.get(c)
        if mdl is None:
            continue
        probs = list(mdl.predict_proba(Xtr)[:, 1])
        conf = [(pm.alpha * p + (1 - pm.alpha) * PM.r1_rule_score(nt, c)) if PM.r1_rule_score(nt, c) > 0 else 0.0
                for p, nt in zip(probs, norms)]
        thr, _, _ = SP.select_threshold(conf, y[c])
        best = {}
        for idx, cf in enumerate(conf):
            if cf < thr or cf <= 0:
                continue
            m_, half_, t_, chash = meta[idx]
            dts = ev_idx[m_].get((half_, c), [])
            if not dts:
                continue
            ne = min(dts, key=lambda et: abs(et - t_))
            if abs(ne - t_) > EV.WINDOW:
                continue
            key = (m_, half_, round(ne, 1), c)
            if key not in best or cf > best[key][0]:
                best[key] = (cf, ne, t_, chash, m_, half_)
        for key, (cf, ne, t_, chash, m_, half_) in best.items():
            em = {"match_id": m_, "commentary_record_id": f"{m_}#h{half_}#{t_:.1f}", "content_hash": chash,
                  "competition": m_.split("/")[0], "season": m_.split("/")[1] if "/" in m_ else "",
                  "event_class": c, "confidence": cf, "event_time_s": ne, "alignment_delta_s": t_ - ne}
            records.append(to_low_conf_record(em, wlb, source_hash=MODEL_VERSION))
    assert_no_raw_text(records)
    assert_flagged_non_silver_non_live(records, set(classes))
    import pandas as pd
    if records:
        pd.DataFrame(records).to_parquet(out, index=False)
    by = defaultdict(int)
    for r in records:
        by[r["event_class"]] += 1
    man = {"n_records": len(records), "classes": list(classes),
           "quality_estimate_precision_wilson_lb": {c: classes[c] for c in classes},
           "by_class": dict(by), "is_silver": False, "confidence_tier": "low_confidence",
           "causal_status": "historical_weak_supervision_only", "live_eligible": False,
           "parser_model_version": MODEL_VERSION, "rights": SOURCE_RIGHTS}
    (ROOT / "notes/research/commentary_low_confidence_signals_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    print("low-confidence signals:", len(records), dict(by))


if __name__ == "__main__":
    main()
