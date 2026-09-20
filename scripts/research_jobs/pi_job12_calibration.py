"""JOB12: calibration + match-level bootstrap + failure analysis. Evaluates the in-play W/D/L state model
(inherited W3 family) under LOCO: draw-probability calibration (slope/intercept/ECE), reliability of RPS by
decision minute, and the worst over-confident failures (conf>0.7 yet RPS>0.5). Significance uses match-level
bootstrap only (correlated within-match state rows are NOT treated as independent). Skips if <2 international
competitions. No network. research_only / experimental / not_runtime_approved."""
import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M


def main():
    rd = Path(_job.run_dir())
    sp = rd / "snapshots_intl.json"
    if not sp.exists():
        _job.emit("skipped", reason="snapshots_intl.json absent (JOB5 produced no data)"); return
    rows = json.loads(sp.read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 international competitions"); return
    cal_pairs_draw = []; by_minute = defaultdict(lambda: {"rps": []}); worst = []
    per_match = defaultdict(list)
    for held, train, test in C.loco_folds(rows):
        fn = M.wdl_predictors(train)["W3"]
        for r in test:
            p = fn(r); t = r["target_wdl"]; rp = C.rps(p, t)
            cal_pairs_draw.append((p.get("D", 0), 1 if t == "D" else 0))
            by_minute[r["minute"]]["rps"].append(rp)
            per_match[r["match_id"]].append(rp)
            conf = max(p.values())
            if conf > 0.7 and rp > 0.5:
                worst.append({"match": r["match_id"], "minute": r["minute"], "conf": round(conf, 3),
                              "rps": round(rp, 3), "target": t})
    rel = {str(m): round(sum(d["rps"]) / len(d["rps"]), 4) for m, d in sorted(by_minute.items())}
    pm = [sum(v) / len(v) for v in per_match.values()]
    res = {"W3_draw_calibration": C.calibration(cal_pairs_draw),
           "reliability_by_minute_rps": rel,
           "overall_rps_match_ci95": C.match_bootstrap_ci(pm),
           "n_overconfident_failures": len(worst),
           "worst_overconfident_examples": sorted(worst, key=lambda x: -x["rps"])[:10],
           "note": "match-level bootstrap only; correlated state rows not treated as independent for significance"}
    (rd / "job12_calibration.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"calibration+failure: {len(worst)} overconfident failures")


main()
