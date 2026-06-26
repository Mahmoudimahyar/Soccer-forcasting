"""JOB10: X0-X3 xG-fusion evaluation. Fuses the player/state in-play W/D/L signal with the pre-registered
StatsBomb xG feature families. X0 = state-only baseline (no xG); X1 = + cumulative xG-before differential;
X2 = + short rolling xG (roll5/roll10); X3 = + shot-count / time-since-last-shot families. Requires the
StatsBomb xG bridge (JOB6) to have produced fused snapshots; skips with an explicit reason otherwise, since
xG fusion cannot be evaluated without StatsBomb shots. All xG features use shots strictly BEFORE the
decision minute (leakage-safe). No network. research_only / experimental / not_runtime_approved."""
import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M

XG_KEYS = ["xg_diff_before", "roll5_xg_diff", "roll10_xg_diff", "shotcount5_diff", "shotcount10_diff",
           "tsl_shot", "tsl_major"]
# X-tier -> which xG columns are fused on top of the state features
X_FAMILIES = {"X0": [], "X1": ["xg_diff_before"], "X2": ["xg_diff_before", "roll5_xg_diff", "roll10_xg_diff"],
              "X3": XG_KEYS}


def _has_xg(rows):
    return bool(rows) and any(any(k in r for k in XG_KEYS) for r in rows)


def _predictor(train, xg_cols):
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    def feat(r):
        return M._feat_w3(r) + [float(r.get(c, 0.0) or 0.0) for c in xg_cols]
    X = np.array([feat(r) for r in train], dtype=float)
    y = np.array([r["target_wdl"] for r in train])
    if len(set(y)) < 2:
        return lambda r: {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
    m = LogisticRegression(max_iter=500, multi_class="multinomial").fit(X, y)
    return lambda r: {cls: float(m.predict_proba(np.array([feat(r)], dtype=float))[0][i])
                      for i, cls in enumerate(m.classes_)}


def main():
    rd = Path(_job.run_dir())
    # prefer xG-fused snapshots if JOB6 produced them; otherwise fall back to intl snapshots
    fused = rd / "snapshots_xg.json"
    sp = fused if fused.exists() else rd / "snapshots_intl.json"
    if not sp.exists():
        _job.emit("skipped", reason="no snapshots available (JOB5/JOB6 produced no data)"); return
    rows = json.loads(sp.read_text(encoding="utf-8"))
    if not _has_xg(rows):
        _job.emit("skipped",
                  reason="snapshots carry no xG columns (StatsBomb bridge JOB6 not built) -> X0-X3 fusion not evaluable"); return
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 competitions for LOCO xG fusion"); return
    agg = {x: {"rps": [], "by_match": defaultdict(list)} for x in X_FAMILIES}
    for held, train, test in C.loco_folds(rows):
        for x, cols in X_FAMILIES.items():
            fn = _predictor(train, cols)
            for r in test:
                rp = C.rps(fn(r), r["target_wdl"])
                agg[x]["rps"].append(rp); agg[x]["by_match"][r["match_id"]].append(rp)
    out = {}
    for x, d in agg.items():
        n = len(d["rps"]); per_match = [sum(v) / len(v) for v in d["by_match"].values()]
        out[x] = {"xg_cols": X_FAMILIES[x], "n_rows": n, "rps": round(sum(d["rps"]) / n, 4),
                  "rps_match_ci95": C.match_bootstrap_ci(per_match)}
    leader = min(out, key=lambda k: out[k]["rps"])
    (rd / "job10_xg_fusion.json").write_text(json.dumps({"models": out, "leader_by_rps": leader}, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"xG-fusion leader_by_rps={leader} rps={out[leader]['rps']}",
              state_updates={"xg_fusion_leader": leader})


main()
