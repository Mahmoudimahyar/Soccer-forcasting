"""Autoresearch batch: explore the candidate surface against the FIXED evaluator folds.

This does NOT alter the evaluator, the folds, or the objective. It reuses runner.py's
leakage guard and metrics verbatim, and only swaps the candidate model. Decisions follow
governance: judge on the DEV+GATE folds (2018, 2022); the 2026 Matchday-1 fold is LOCKED
(reported as transfer only, never used to select). The winning config is then written into
src/wcdrawlab/research/candidate.py and confirmed with the official runner + pytest.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402
from wcdrawlab.research.runner import (  # noqa: E402
    leakage_safe_feature_frame, draw_calibration_error, composite_score,
    load_research_config, _ensure_outcome, _year,
)

DATA = ROOT / "data" / "processed" / "research_modeling_table.csv"
CONFIG = ROOT / "configs" / "research.yaml"

BASE_FEATURES = ["elo_delta", "abs_elo_delta", "matchday", "p_a_market", "p_draw_market",
                 "p_b_market", "market_total_goals", "prior_group_draws", "low_block_risk",
                 "travel_fatigue"]
STATE_FEATURES = ["group_state_points_delta", "group_state_gd_delta", "prior_group_goals_per_match"]
CTX_FEATURES = ["venue_host_advantage", "confed_same"]


@dataclass
class Variant:
    name: str
    hypothesis: str
    features: list[str]
    C: float = 0.3
    scaler: bool = False
    class_weight: str | None = None
    blend_elo: float = 0.0          # weight on ternary-Elo probs in a blend
    platt_draw: bool = False        # in-sample Platt recalibration of p_draw


class VariantModel:
    def __init__(self, v: Variant, random_state: int = 7):
        self.v = v
        self.columns: list[str] = []
        self.scaler = StandardScaler() if v.scaler else None
        self.model = LogisticRegression(max_iter=2000, C=v.C, random_state=random_state,
                                        class_weight=v.class_weight)
        self._platt = None

    def _design(self, X):
        d = X.reindex(columns=self.columns, fill_value=0.0).fillna(0.0)
        if self.scaler is not None:
            d = self.scaler.transform(d) if hasattr(self.scaler, "mean_") else self.scaler.fit_transform(d)
        return d

    def fit(self, X, y):
        self.columns = [c for c in self.v.features if c in X.columns] or ["elo_delta"]
        if "elo_delta" not in X.columns:
            X = X.copy(); X["elo_delta"] = 0.0
        design = self._design(X)
        label_map = {"A": 0, "D": 1, "B": 2, 0: 0, 1: 1, 2: 2}
        enc = y.map(label_map).astype(int)
        self.model.fit(design, enc)
        if self.v.platt_draw:
            base = self._raw_proba(X)
            self._fit_platt(base[:, 1], (y.values == "D").astype(int))
        return self

    def _raw_proba(self, X):
        design = self._design(X)
        raw = self.model.predict_proba(design)
        full = np.full((len(X), 3), 1e-9)
        for i, cls in enumerate(self.model.classes_):
            full[:, int(cls)] = raw[:, i]
        probs = normalize_probs(full)
        if self.v.blend_elo > 0 and "elo_delta" in X.columns:
            elo = ternary_elo_probs(X["elo_delta"].to_numpy())
            probs = normalize_probs((1 - self.v.blend_elo) * probs + self.v.blend_elo * elo)
        return probs

    def _fit_platt(self, p_draw, y_draw):
        def logit(p):
            p = np.clip(p, 1e-4, 1 - 1e-4); return np.log(p / (1 - p))
        lr = LogisticRegression(C=1.0, max_iter=1000)
        lr.fit(logit(p_draw).reshape(-1, 1), y_draw)
        self._platt = lr

    def predict_proba(self, X):
        probs = self._raw_proba(X)
        if self._platt is not None:
            def logit(p):
                p = np.clip(p, 1e-4, 1 - 1e-4); return np.log(p / (1 - p))
            nd = self._platt.predict_proba(logit(probs[:, 1]).reshape(-1, 1))[:, 1]
            ab = probs[:, [0, 2]]; ab_sum = np.clip(ab.sum(1, keepdims=True), 1e-9, None)
            nondraw = np.clip(1 - nd, 1e-9, None)
            probs = np.column_stack([nondraw * ab[:, 0] / ab_sum.ravel(), nd,
                                     nondraw * ab[:, 1] / ab_sum.ravel()])
        return normalize_probs(probs)


def eval_variant(data, folds, config, v: Variant) -> dict:
    work = _ensure_outcome(data)
    years = _year(work["kickoff_utc"])
    stage = work.get("stage", pd.Series("group", index=work.index)).astype(str).str.lower()
    res = {}
    for f in folds:
        train = work[(years < f.train_before_year) & (stage == f.stage)].copy()
        test = work[(years == f.test_year) & (stage == f.stage)].copy()
        if f.matchday is not None and "matchday" in test.columns:
            test = test[test["matchday"].astype(int) == int(f.matchday)].copy()
        if train.empty or test.empty:
            res[f.name] = None; continue
        Xtr = leakage_safe_feature_frame(train, config)
        Xte = leakage_safe_feature_frame(test, config).reindex(columns=Xtr.columns, fill_value=0.0)
        m = VariantModel(v).fit(Xtr, train["outcome"])
        probs = m.predict_proba(Xte)
        met = metric_report(test["outcome"], probs)
        met["draw_calibration_error"] = draw_calibration_error(test["outcome"], probs[:, 1])
        met["composite"] = composite_score(met, config["objective"]["weights"])
        res[f.name] = met
    return res


def main():
    data = pd.read_csv(DATA, parse_dates=["kickoff_utc"])
    config, folds = load_research_config(CONFIG)

    variants = [
        Variant("V0_baseline", "current candidate: unscaled logit C=0.3 on base features",
                BASE_FEATURES, C=0.3),
        Variant("V1_scaler", "standardizing features improves the regularized logit",
                BASE_FEATURES, C=0.3, scaler=True),
        Variant("V2_scaler_C1", "less regularization (C=1.0) helps once scaled",
                BASE_FEATURES, C=1.0, scaler=True),
        Variant("V3_scaler_C05", "moderate regularization C=0.5 with scaling is best",
                BASE_FEATURES, C=0.5, scaler=True),
        Variant("V4_add_state", "adding pre-match group-state deltas helps MD2/MD3",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True),
        Variant("V5_add_ctx", "adding host/confederation context helps",
                BASE_FEATURES + STATE_FEATURES + CTX_FEATURES, C=0.5, scaler=True),
        Variant("V6_balanced", "class_weight=balanced improves draw recall/calibration",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True, class_weight="balanced"),
        Variant("V7_blend_elo", "blending 30% ternary-Elo stabilizes the logit",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True, blend_elo=0.3),
        Variant("V8_blend_elo50", "blending 50% ternary-Elo is even more robust",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True, blend_elo=0.5),
        Variant("V9_platt", "in-sample Platt draw recalibration lowers draw error",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True, platt_draw=True),
        Variant("V10_blend_platt", "blend Elo + Platt draw recalibration combined",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True, blend_elo=0.3, platt_draw=True),
        Variant("V11_ctx_blend", "context features + Elo blend (full model)",
                BASE_FEATURES + STATE_FEATURES + CTX_FEATURES, C=0.5, scaler=True, blend_elo=0.3),
    ]

    base = eval_variant(data, folds, config, variants[0])
    f2018, f2022, f2026 = "world_cup_2018", "world_cup_2022", "world_cup_2026_matchday_1_locked"

    def devgate(r):
        return np.mean([r[f2018]["composite"], r[f2022]["composite"]])

    base_dg = devgate(base)
    rows = []
    for v in variants:
        r = eval_variant(data, folds, config, v)
        dg = devgate(r)
        reg2018 = r[f2018]["composite"] - base[f2018]["composite"]
        reg2022 = r[f2022]["composite"] - base[f2022]["composite"]
        rel_impr = (base_dg - dg) / base_dg
        promotable = (rel_impr >= 0.002) and (reg2018 <= 0.001) and (reg2022 <= 0.001)
        rows.append({
            "variant": v.name,
            "devgate_composite": round(dg, 4),
            "rel_impr_vs_base": round(rel_impr, 4),
            "c2018": round(r[f2018]["composite"], 4),
            "c2022": round(r[f2022]["composite"], 4),
            "c2026_locked": round(r[f2026]["composite"], 4) if r[f2026] else None,
            "drawcal2026_locked": round(r[f2026]["draw_calibration_error"], 4) if r[f2026] else None,
            "promotable": promotable,
            "hypothesis": v.hypothesis,
        })
    out = pd.DataFrame(rows)
    OUT = ROOT / "outputs" / "research" / "autoresearch"
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "batch_cycle_1.csv", index=False)
    pd.set_option("display.width", 200)
    print(out.drop(columns=["hypothesis"]).to_string(index=False))
    prom = out[out.promotable].sort_values("devgate_composite")
    print("\nBASE devgate composite:", round(base_dg, 4))
    if len(prom):
        print("WINNER:", prom.iloc[0]["variant"], "->", prom.iloc[0]["devgate_composite"])
    else:
        print("No variant meets the promotion bar; KEEP baseline.")


if __name__ == "__main__":
    main()
