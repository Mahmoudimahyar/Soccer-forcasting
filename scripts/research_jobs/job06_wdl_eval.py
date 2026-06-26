import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M
def main():
    rd = Path(_job.run_dir())
    rows = json.loads((rd/"snapshots_intl.json").read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 international competitions for LOCO"); return
    agg = {m: {"rps": [], "ll": [], "bd": [], "by_match": defaultdict(list)} for m in ["W0","W1","W2","W3","W4"]}
    for held, train, test in C.loco_folds(rows):
        preds = M.wdl_predictors(train)
        for name, fn in preds.items():
            for r in test:
                p = fn(r); t = r["target_wdl"]
                rp = C.rps(p, t); ll = C.logloss3(p, t); bd = C.brier_draw(p, t)
                agg[name]["rps"].append(rp); agg[name]["ll"].append(ll); agg[name]["bd"].append(bd)
                agg[name]["by_match"][r["match_id"]].append(rp)
    out = {}
    for name, d in agg.items():
        n = len(d["rps"])
        per_match = [sum(v)/len(v) for v in d["by_match"].values()]
        out[name] = {"n_rows": n, "n_matches": len(per_match),
                     "rps": round(sum(d["rps"])/n,4), "logloss": round(sum(d["ll"])/n,4),
                     "brier_draw": round(sum(d["bd"])/n,4),
                     "rps_match_ci95": C.match_bootstrap_ci(per_match)}
    leader = min(out, key=lambda k: out[k]["rps"])
    (rd/"job06_wdl.json").write_text(json.dumps({"models": out, "leader_by_rps": leader}, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"W-eval leader_by_rps={leader} rps={out[leader]['rps']}",
              state_updates={"wdl_leader": leader})
main()
