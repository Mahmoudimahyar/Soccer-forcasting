"""Research-only sweep: explore candidate hyperparameters on DEV folds (2010/2014/2018) without
editing candidate.py. Patches runner.CandidateModel with parameterized variants. Reports dev
composite per combo so a real improvement (if any) can then be baked into candidate.py.

Selection is DEV-only; 2022 (gate) and 2026-MD1 (locked) are never used here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sklearn.linear_model import LogisticRegression  # noqa: E402
import wcdrawlab.research.runner as R  # noqa: E402
import wcdrawlab.research.candidate as C  # noqa: E402

TABLE = "data/processed/research_modeling_table.csv"
DEV = "configs/research_dev.yaml"
LEAN = ["elo_delta", "abs_elo_delta", "matchday", "prior_group_draws",
        "prior_group_goals_per_match", "group_state_points_delta", "group_state_gd_delta"]
FULL = list(C.FEATURES)


def make_cand(c_val):
    class Cand(C.CandidateModel):
        def __init__(self, random_state: int = 7):
            super().__init__(random_state)
            self.model = LogisticRegression(max_iter=2000, C=c_val, random_state=random_state)
    return Cand


def dev_composite(c_val, blend, features):
    C.ELO_BLEND_WEIGHT = blend
    C.FEATURES = features
    R.CandidateModel = make_cand(c_val)
    res = R.run_experiment(TABLE, DEV, "outputs/research/_sweep")
    folds = {f["fold"]: f["composite"] for f in res.folds if not f.get("skipped")}
    return res.summary["composite"], res.summary["draw_calibration_error"], folds


rows = []
for feat_name, feats in [("full", FULL), ("lean", LEAN)]:
    for c_val in [0.25, 0.5, 1.0]:
        for blend in [0.80, 0.85, 0.90]:
            comp, dece, folds = dev_composite(c_val, blend, feats)
            rows.append((comp, dece, feat_name, c_val, blend, folds))

rows.sort(key=lambda r: r[0])
print(f"{'rank':<5}{'devJ':<9}{'dECE':<8}{'feats':<6}{'C':<6}{'blend':<7} per-fold(2010/2014/2018)")
for i, (comp, dece, fn, c_val, blend, folds) in enumerate(rows):
    pf = "/".join(f"{folds.get(k,float('nan')):.4f}" for k in
                  ["dev_world_cup_2010", "dev_world_cup_2014", "dev_world_cup_2018"])
    star = "  <-- baseline" if (abs(c_val-0.5) < 1e-9 and abs(blend-0.85) < 1e-9 and fn == "full") else ""
    print(f"{i+1:<5}{comp:<9.4f}{dece:<8.4f}{fn:<6}{c_val:<6}{blend:<7}{pf}{star}")
