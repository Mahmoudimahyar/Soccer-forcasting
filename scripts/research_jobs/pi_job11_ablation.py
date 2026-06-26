"""JOB11: ablation. Quantifies the marginal contribution of each feature group in the in-play W/D/L
state model by leave-one-group-out, comparing LOCO RPS to the full model. Groups: score-state, discipline
(cards/sendings-off), substitutions, player-count differential (the player-impact channel), and xG (when
StatsBomb-fused snapshots are present). A positive delta_rps means the group HELPS (removing it worsens RPS).
Skips if <2 international competitions. No network. research_only / experimental."""
import sys, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C

GROUPS = {
    "score_state": ["score_diff"],
    "discipline": ["card_diff", "so_diff"],
    "substitutions": ["subs_diff"],
    "player_count": ["player_count_diff"],   # player-impact channel
    "time": ["remaining"],
}
XG_COLS = ["xg_diff_before", "roll5_xg_diff", "roll10_xg_diff", "shotcount5_diff", "shotcount10_diff",
           "tsl_shot", "tsl_major"]
BASE_FEATS = ["score_diff", "card_diff", "so_diff", "subs_diff", "player_count_diff", "remaining"]


def _fit_eval(train, test, feats):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    Xtr = np.array([[float(r.get(c, 0.0) or 0.0) for c in feats] for r in train], dtype=float)
    ytr = np.array([r["target_wdl"] for r in train])
    if len(set(ytr)) < 2 or not feats:
        per = defaultdict(list)
        for r in test:
            per[r["match_id"]].append(C.rps({"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}, r["target_wdl"]))
        return per
    m = LogisticRegression(max_iter=500, multi_class="multinomial").fit(Xtr, ytr)
    per = defaultdict(list)
    for r in test:
        probs = m.predict_proba(np.array([[float(r.get(c, 0.0) or 0.0) for c in feats]], dtype=float))[0]
        pr = {cls: float(probs[i]) for i, cls in enumerate(m.classes_)}
        per[r["match_id"]].append(C.rps(pr, r["target_wdl"]))
    return per


def _mean_rps(rows, feats):
    vals = []
    for held, train, test in C.loco_folds(rows):
        per = _fit_eval(train, test, feats)
        vals.extend(sum(v) / len(v) for v in per.values())
    return round(sum(vals) / len(vals), 4) if vals else None


def main():
    rd = Path(_job.run_dir())
    fused = rd / "snapshots_xg.json"
    sp = fused if fused.exists() else rd / "snapshots_intl.json"
    if not sp.exists():
        _job.emit("skipped", reason="no snapshots available (JOB5/JOB6 produced no data)"); return
    rows = json.loads(sp.read_text(encoding="utf-8"))
    if len({r["competition"] for r in rows}) < 2:
        _job.emit("skipped", reason="need >=2 international competitions for ablation LOCO"); return
    groups = dict(GROUPS)
    full = list(BASE_FEATS)
    if any(any(k in r for k in XG_COLS) for r in rows):
        groups["xg"] = XG_COLS; full = full + XG_COLS
    full_rps = _mean_rps(rows, full)
    ablations = {}
    for gname, cols in groups.items():
        reduced = [f for f in full if f not in cols]
        r_rps = _mean_rps(rows, reduced)
        ablations[gname] = {"dropped": cols, "rps_without": r_rps,
                            "delta_rps": round(r_rps - full_rps, 4) if (r_rps is not None and full_rps is not None) else None}
    ranked = sorted((g for g in ablations), key=lambda g: -(ablations[g]["delta_rps"] or -1))
    res = {"full_model_rps": full_rps, "ablations": ablations,
           "most_valuable_group": ranked[0] if ranked else None,
           "note": "delta_rps>0 => group helps (removal worsens RPS); player_count is the player-impact channel"}
    (rd / "job11_ablation.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"ablation full_rps={full_rps}; most_valuable={res['most_valuable_group']}",
              state_updates={"ablation_most_valuable": res["most_valuable_group"]})


main()
