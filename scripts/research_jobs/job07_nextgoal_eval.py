import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M
def main():
    rd = Path(_job.run_dir())
    rows = json.loads((rd/"snapshots_intl.json").read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 competitions"); return
    agg = {m: {"brier": [], "ll": [], "cal": [], "by_match": defaultdict(list)} for m in ["N0","N1","N2"]}
    base_rate = sum(r["next_goal_15"] for r in rows)/len(rows)
    for held, train, test in C.loco_folds(rows):
        preds = M.nextgoal_predictors(train)
        for name, fn in preds.items():
            for r in test:
                p = min(max(fn(r),1e-6),1-1e-6); y = r["next_goal_15"]
                br = (p-y)**2; ll = -(y*__import__("math").log(p)+(1-y)*__import__("math").log(1-p))
                agg[name]["brier"].append(br); agg[name]["ll"].append(ll); agg[name]["cal"].append((p,y))
                agg[name]["by_match"][r["match_id"]].append(br)
    out={}
    for name,d in agg.items():
        n=len(d["brier"]); per_match=[sum(v)/len(v) for v in d["by_match"].values()]
        out[name]={"n_rows":n,"brier":round(sum(d["brier"])/n,4),"logloss":round(sum(d["ll"])/n,4),
                   "calibration":C.calibration(d["cal"]),"brier_match_ci95":C.match_bootstrap_ci(per_match)}
    out["base_rate"]=round(base_rate,4)
    leader=min([k for k in out if k.startswith("N")], key=lambda k: out[k]["brier"])
    (rd/"job07_nextgoal.json").write_text(json.dumps({"models":out,"leader_by_brier":leader},indent=2),encoding="utf-8")
    _job.emit("complete", reason=f"N-eval leader_by_brier={leader}", state_updates={"nextgoal_leader":leader})
main()
