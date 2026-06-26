"""JOB8: N0-N3 next-goal (P(goal in next 15 regulation minutes)) evaluation. LOCO over international
competitions with match-level bootstrap. N0 base-rate; N1 logistic hazard; N2 +lineup-continuity proxy
(from inherited _models); N3 adds the player-count differential / discipline-state interaction as an extra
hazard feature (defined here so the inherited _models stays untouched). Metrics: Brier / log-loss /
calibration. Skips if <2 international competitions. No network. research_only / experimental."""
import sys, json, math
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M


def _feat_n3(r):
    # N1 features + player-count differential and a card/player-count interaction (leakage-safe state)
    return M._feat_n1(r) + [r.get("n_starters_home", 0), r["player_count_diff"],
                            r["player_count_diff"] * r["card_diff"]]


def _n3_predictor(train):
    base = sum(r["next_goal_15"] for r in train) / max(1, len(train))
    m3 = M._fit_logistic_bin(train, _feat_n3, "next_goal_15")
    return lambda r: M._predict_bin(m3, r, _feat_n3, base)


def main():
    rd = Path(_job.run_dir())
    sp = rd / "snapshots_intl.json"
    if not sp.exists():
        _job.emit("skipped", reason="snapshots_intl.json absent (JOB5 produced no data)"); return
    rows = json.loads(sp.read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 international competitions"); return
    names = ["N0", "N1", "N2", "N3"]
    agg = {m: {"brier": [], "ll": [], "cal": [], "by_match": defaultdict(list)} for m in names}
    base_rate = sum(r["next_goal_15"] for r in rows) / len(rows)
    for held, train, test in C.loco_folds(rows):
        preds = dict(M.nextgoal_predictors(train)); preds["N3"] = _n3_predictor(train)
        for name in names:
            fn = preds[name]
            for r in test:
                p = min(max(fn(r), 1e-6), 1 - 1e-6); y = r["next_goal_15"]
                br = (p - y) ** 2; ll = -(y * math.log(p) + (1 - y) * math.log(1 - p))
                agg[name]["brier"].append(br); agg[name]["ll"].append(ll); agg[name]["cal"].append((p, y))
                agg[name]["by_match"][r["match_id"]].append(br)
    out = {}
    for name in names:
        d = agg[name]; n = len(d["brier"]); per_match = [sum(v) / len(v) for v in d["by_match"].values()]
        out[name] = {"n_rows": n, "brier": round(sum(d["brier"]) / n, 4), "logloss": round(sum(d["ll"]) / n, 4),
                     "calibration": C.calibration(d["cal"]), "brier_match_ci95": C.match_bootstrap_ci(per_match)}
    out["base_rate"] = round(base_rate, 4)
    leader = min(names, key=lambda k: out[k]["brier"])
    (rd / "job08_nextgoal.json").write_text(json.dumps({"models": out, "leader_by_brier": leader}, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"N-eval leader_by_brier={leader}", state_updates={"nextgoal_leader": leader})


main()
