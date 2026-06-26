"""JOB7: P1-P4 in-play W/D/L evaluation. Leave-one-competition-out (LOCO) over international
competitions with match-level bootstrap CIs. P1-P4 are the player/state-aware W/D/L families from the
inherited preregistered _models (P1=empirical score-diff, P2=remaining-time Poisson, P3=logistic on
team-state incl. player-count differential, P4=+lineup-continuity). Metrics: RPS / log-loss / Brier(draw).
Skips if <2 international competitions are available. No network. research_only / experimental."""
import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M

# sprint P-labels -> inherited preregistered predictor names
P_MAP = {"P1": "W1", "P2": "W2", "P3": "W3", "P4": "W4"}


def main():
    rd = Path(_job.run_dir())
    sp = rd / "snapshots_intl.json"
    if not sp.exists():
        _job.emit("skipped", reason="snapshots_intl.json absent (JOB5 produced no data)"); return
    rows = json.loads(sp.read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 international competitions for LOCO"); return
    agg = {p: {"rps": [], "ll": [], "bd": [], "by_match": defaultdict(list)} for p in P_MAP}
    for held, train, test in C.loco_folds(rows):
        preds = M.wdl_predictors(train)
        for p, wname in P_MAP.items():
            fn = preds[wname]
            for r in test:
                t = r["target_wdl"]; pr = fn(r)
                rp = C.rps(pr, t); ll = C.logloss3(pr, t); bd = C.brier_draw(pr, t)
                agg[p]["rps"].append(rp); agg[p]["ll"].append(ll); agg[p]["bd"].append(bd)
                agg[p]["by_match"][r["match_id"]].append(rp)
    out = {}
    for p, d in agg.items():
        n = len(d["rps"]); per_match = [sum(v) / len(v) for v in d["by_match"].values()]
        out[p] = {"maps_to": P_MAP[p], "n_rows": n, "n_matches": len(per_match),
                  "rps": round(sum(d["rps"]) / n, 4), "logloss": round(sum(d["ll"]) / n, 4),
                  "brier_draw": round(sum(d["bd"]) / n, 4), "rps_match_ci95": C.match_bootstrap_ci(per_match)}
    leader = min(out, key=lambda k: out[k]["rps"])
    (rd / "job07_wdl.json").write_text(json.dumps({"models": out, "leader_by_rps": leader}, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"P-eval leader_by_rps={leader} rps={out[leader]['rps']}",
              state_updates={"wdl_leader": leader})


main()
