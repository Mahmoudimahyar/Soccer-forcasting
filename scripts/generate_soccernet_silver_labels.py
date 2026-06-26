"""Phase 4: emit deduped SILVER-LABEL candidates (one per detected event) for APPROVED classes, using the
all-data fit + train-selected thresholds. Writes gitignored data/processed/silver_emissions.json (consumed
by build_soccernet_silver_label_release.py). NO raw text. historical_weak_supervision_only / not_live_eligible.
"""
import json
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
    out = ROOT / "data/processed/silver_emissions.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not approved:
        out.write_text("[]", encoding="utf-8")
        print("no approved classes -> empty silver emissions"); return
    matched, ev_idx, seg_idx = EV.assemble()
    texts, norms, meta = [], [], []
    y = {c: [] for c in EV.CLASSES}
    for m in matched:
        for s in seg_idx[m]:
            texts.append(s["text"]); norms.append(s["norm"]); meta.append((m, s["half"], s["t_s"], s["content_hash"]))
            for c in EV.CLASSES:
                lab, _ = EV.label_for(ev_idx, m, s["half"], s["t_s"], c)
                y[c].append(lab)
    pm = PM.PrecisionModels().fit(texts, y)
    Xtr = pm.vec.transform(texts)
    emissions = []
    for c in approved:
        mdl = pm.models.get(c)
        if mdl is None:
            continue
        probs = list(mdl.predict_proba(Xtr)[:, 1])
        conf = [(pm.alpha * p + (1 - pm.alpha) * PM.r1_rule_score(nt, c)) if PM.r1_rule_score(nt, c) > 0 else 0.0
                for p, nt in zip(probs, norms)]
        thr, _, _ = SP.select_threshold(conf, y[c])
        # collect emissions, dedup to nearest segment per real event
        best_per_event = {}
        for idx, cf in enumerate(conf):
            if cf < thr or cf <= 0:
                continue
            m_, half_, t_, chash = meta[idx]
            dts = ev_idx[m_].get((half_, c), [])
            if not dts:
                continue
            # nearest real event
            ne = min(dts, key=lambda et: abs(et - t_))
            if abs(ne - t_) > EV.WINDOW:
                continue
            key = (m_, half_, round(ne, 1), c)
            if key not in best_per_event or cf > best_per_event[key][0]:
                best_per_event[key] = (cf, idx, ne, t_, chash, m_, half_)
        for key, (cf, idx, ne, t_, chash, m_, half_) in best_per_event.items():
            emissions.append({
                "match_id": m_, "commentary_record_id": f"{m_}#h{half_}#{t_:.1f}",
                "content_hash": chash, "competition": m_.split("/")[0],
                "season": "/".join(m_.split("/")[:2]).split("/")[-1] if "/" in m_ else "",
                "event_class": c, "confidence": cf, "event_time_s": ne, "alignment_delta_s": t_ - ne,
            })
    out.write_text(json.dumps(emissions), encoding="utf-8")
    by = defaultdict(int)
    for e in emissions:
        by[e["event_class"]] += 1
    print("silver emissions:", len(emissions), dict(by))


if __name__ == "__main__":
    main()
