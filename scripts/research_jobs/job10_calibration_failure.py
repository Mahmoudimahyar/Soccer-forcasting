import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M
def main():
    rd = Path(_job.run_dir())
    rows = json.loads((rd/"snapshots_intl.json").read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows})<2:
        _job.emit("skipped", reason="need >=2 comps"); return
    # leader model calibration (use W3) + reliability by minute/score-state + worst overconfident matches
    cal_pairs_draw=[]; by_minute=defaultdict(lambda:{"rps":[],"n":0}); worst=[]
    for held, train, test in C.loco_folds(rows):
        fn = M.wdl_predictors(train)["W3"]
        for r in test:
            p = fn(r); t = r["target_wdl"]; rp = C.rps(p,t)
            cal_pairs_draw.append((p.get("D",0), 1 if t=="D" else 0))
            by_minute[r["minute"]]["rps"].append(rp); by_minute[r["minute"]]["n"]+=1
            conf = max(p.values())
            if conf>0.7 and rp>0.5: worst.append({"match":r["match_id"],"minute":r["minute"],"conf":round(conf,3),"rps":round(rp,3),"target":t})
    rel = {str(m): round(sum(d["rps"])/len(d["rps"]),4) for m,d in sorted(by_minute.items())}
    res = {"W3_draw_calibration": C.calibration(cal_pairs_draw),
           "reliability_by_minute_rps": rel,
           "n_overconfident_failures": len(worst), "worst_overconfident_examples": sorted(worst, key=lambda x:-x["rps"])[:10],
           "note": "match-level bootstrap only; correlated state rows not treated as independent for significance"}
    (rd/"job10_calibration_failure.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"calibration+failure: {len(worst)} overconfident failures")
main()
