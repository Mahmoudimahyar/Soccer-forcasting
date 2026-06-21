"""Materially-different hypothesis: TRAIN-ONLY draw recalibration on top of the V8 candidate.
Tests whether a draw-specific calibrator (fit on train draws only) improves draw_brier + dECE
without hurting RPS, on DEV folds (2010/2014/2018). No candidate.py edit unless a variant wins.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sklearn.linear_model import LogisticRegression  # noqa: E402
import wcdrawlab.research.runner as R  # noqa: E402
import wcdrawlab.research.candidate as C  # noqa: E402
from wcdrawlab.evaluation import normalize_probs  # noqa: E402

TABLE = "data/processed/research_modeling_table.csv"
DEV = "configs/research_dev.yaml"


def _recal_class(mode):
    base = C.CandidateModel

    class Recal(base):
        def fit(self, X, y):
            super().fit(X, y)
            p = super().predict_proba(X)
            pd_ = np.clip(p[:, 1], 1e-6, 1 - 1e-6)
            yd = (y.astype(str).to_numpy() == "D").astype(int) if hasattr(y, "astype") else (np.asarray(y) == 1).astype(int)
            if mode == "platt":
                z = np.log(pd_ / (1 - pd_)).reshape(-1, 1)
                self._cal = LogisticRegression(max_iter=1000).fit(z, yd)
            elif mode == "temp":
                # single global temperature on the draw logit chosen to match train draw rate
                self._base_rate = yd.mean()
            return self

        def predict_proba(self, X):
            p = super().predict_proba(X)
            pd_ = np.clip(p[:, 1], 1e-6, 1 - 1e-6)
            if mode == "platt":
                z = np.log(pd_ / (1 - pd_)).reshape(-1, 1)
                new_d = self._cal.predict_proba(z)[:, 1]
            else:  # temp: shift draw mass toward train base rate (mild)
                new_d = 0.5 * pd_ + 0.5 * self._base_rate
            rest = 1.0 - new_d
            ab = p[:, [0, 2]]
            ab = ab / np.clip(ab.sum(1, keepdims=True), 1e-9, None) * rest.reshape(-1, 1)
            out = np.column_stack([ab[:, 0], new_d, ab[:, 1]])
            return normalize_probs(out)
    return Recal


def run(label, cls):
    R.CandidateModel = cls
    res = R.run_experiment(TABLE, DEV, "outputs/research/_expdraw")
    s = res.summary
    folds = {f["fold"]: f["composite"] for f in res.folds if not f.get("skipped")}
    pf = "/".join(f"{folds[k]:.4f}" for k in ["dev_world_cup_2010", "dev_world_cup_2014", "dev_world_cup_2018"])
    print(f"  {label:<22} devJ={s['composite']:.4f}  rps={s['rps']:.4f}  dBrier={s['draw_brier']:.4f}  dECE={s['draw_calibration_error']:.4f}  folds={pf}")


print("baseline (V8)         devJ=0.3541  rps=0.1901  dBrier=0.1733  dECE=0.0581  folds=0.3770/0.3312/0.3541")
run("E_draw_platt", _recal_class("platt"))
run("E_draw_temp", _recal_class("temp"))
