"""Phase 2/4: fit the precision models on ALL matched data and select per-class R4 thresholds (target
train precision 0.85), for SILVER-LABEL GENERATION on approved classes. The PRECISION GUARANTEE comes from
the leave-one-competition-out gate (evaluate_commentary_precision_models.py), NOT from this in-sample fit.

Outputs go to gitignored storage only (the fitted model's vocabulary contains commentary tokens, so it is
never committed). research_only / historical_weak_supervision_only / not_live_eligible.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import precision_models as PM  # noqa: E402
from wcdrawlab.research.commentary import silver_label_policy as SP  # noqa: E402
import evaluate_commentary_precision_models as EV  # noqa: E402  (reuse assemble/label_for)

OUT = ROOT / "data/processed/precision_models"  # gitignored


def main():
    matched, ev_idx, seg_idx = EV.assemble()
    texts, norms, meta = [], [], []
    y = {c: [] for c in EV.CLASSES}
    for m in matched:
        for s in seg_idx[m]:
            texts.append(s["text"]); norms.append(s["norm"]); meta.append((m, s["half"], s["t_s"]))
            for c in EV.CLASSES:
                lab, _ = EV.label_for(ev_idx, m, s["half"], s["t_s"], c)
                y[c].append(lab)
    pm = PM.PrecisionModels().fit(texts, y)
    Xtr = pm.vec.transform(texts)
    thresholds = {}
    for c in EV.CLASSES:
        mdl = pm.models.get(c)
        probs = list(mdl.predict_proba(Xtr)[:, 1]) if mdl is not None else [0.0] * len(texts)
        conf = [(pm.alpha * p + (1 - pm.alpha) * PM.r1_rule_score(nt, c)) if PM.r1_rule_score(nt, c) > 0 else 0.0
                for p, nt in zip(probs, norms)]
        thr, prec, cnt = SP.select_threshold(conf, y[c])
        thresholds[c] = {"threshold": round(thr, 4), "train_precision": round(prec, 4), "train_count": cnt}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    print("fitted on", len(texts), "segments; thresholds (gitignored):")
    print(json.dumps(thresholds, indent=2))


if __name__ == "__main__":
    main()
