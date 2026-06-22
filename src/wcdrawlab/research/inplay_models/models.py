"""In-play baseline models M0-M5 (research-only). W/D/L is HOME-perspective [home, draw, away].

Shared goal dynamics come from the validated remaining-time Poisson engine so every model can emit
the full output envelope; each model's NATIVE target is what it is evaluated on:
  M0 static B1 (control) · M1 time+score logit · M2 remaining-time Poisson (engine) ·
  M3 goal-within-5 hazard (logit) · M4 competing-risk next-goal team (multinomial) · M5 ensemble(M1,M2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.inplay.engine import InPlayState, update_inplay_probabilities

MODEL_VERSION = "inplay-baselines-v1"
WLD = ["home", "draw", "away"]


def pregame_lambdas(elo_delta_home: float) -> tuple[float, float]:
    """Pre-match expected goals per team from Elo supremacy (fixed transparent mapping)."""
    base = 1.35
    return base * np.exp(0.20 * elo_delta_home / 100.0), base * np.exp(-0.20 * elo_delta_home / 100.0)


def remaining_lambdas(row) -> tuple[float, float]:
    """Remaining expected goals (home, away) via the engine, conditioned on live state."""
    lh, la = pregame_lambdas(float(row["elo_delta_home"]))
    st = InPlayState(minute=float(row["decision_minute"]), goals_a=int(row["score_home"]),
                     goals_b=int(row["score_away"]), red_cards_a=int(row["red_home"]),
                     red_cards_b=int(row["red_away"]))
    p = update_inplay_probabilities(lh, la, st)
    return p.lambda_a_remaining, p.lambda_b_remaining


def _goal_dynamics(R, lh_rem, la_rem):
    """Rate fields from remaining-time Poisson. R = remaining minutes."""
    tot = max(1e-9, lh_rem + la_rem)
    R = max(1e-9, R)
    def within(h):
        return float(1.0 - np.exp(-tot * min(h, R) / R))
    return {
        "expected_remaining_goals_home": float(lh_rem),
        "expected_remaining_goals_away": float(la_rem),
        "probability_home_next_goal": float(lh_rem / tot),
        "probability_away_next_goal": float(la_rem / tot),
        "probability_no_goal_next_5_minutes": float(np.exp(-tot * min(5, R) / R)),
        "probability_goal_next_1_minutes": within(1),
        "probability_goal_next_3_minutes": within(3),
        "probability_goal_next_5_minutes": within(5),
        "probability_goal_next_10_minutes": within(10),
    }


def full_output_envelope(df: pd.DataFrame, wld: np.ndarray, model_id: str) -> pd.DataFrame:
    """Attach the full required output vector to a W/D/L prediction using shared goal dynamics."""
    rows = []
    for i, (_, row) in enumerate(df.reset_index(drop=True).iterrows()):
        lh, la = remaining_lambdas(row)
        gd = _goal_dynamics(row["remaining_minutes"], lh, la)
        p = wld[i]
        ent = float(-(p * np.log(np.clip(p, 1e-12, 1))).sum() / np.log(3))
        rows.append({"p_home_win": p[0], "p_draw": p[1], "p_away_win": p[2], **gd,
                     "uncertainty": float(np.sqrt((p * (1 - p)).sum())), "entropy": ent,
                     "model_id": model_id, "model_version": MODEL_VERSION, "research_only": True})
    return pd.DataFrame(rows)


# ---- W/D/L models ----
class M0_StaticB1:
    model_id = "M0_static_b1"
    def fit(self, train): return self
    def predict_wld(self, df):
        return normalize_probs(df[["p_home_elo", "p_draw_elo", "p_away_elo"]].to_numpy(dtype=float))


_FEATS = ["score_diff", "remaining_minutes", "elo_delta_home", "red_diff"]


class M1_TimeScore:
    model_id = "M1_time_score"
    def __init__(self):
        self.scaler = StandardScaler(); self.clf = LogisticRegression(max_iter=2000, C=1.0)
    def fit(self, train):
        X = self.scaler.fit_transform(train[_FEATS].fillna(0)); y = train["final_wld"].map({"H": 0, "D": 1, "A": 2})
        self.clf.fit(X, y); self.classes_ = list(self.clf.classes_); return self
    def predict_wld(self, df):
        X = self.scaler.transform(df[_FEATS].fillna(0)); raw = self.clf.predict_proba(X)
        full = np.full((len(df), 3), 1e-9)
        for j, c in enumerate(self.classes_):
            full[:, int(c)] = raw[:, j]
        return normalize_probs(full)


class M2_RemainingPoisson:
    model_id = "M2_remaining_poisson"
    def fit(self, train): return self
    def predict_wld(self, df):
        out = np.zeros((len(df), 3))
        for i, (_, row) in enumerate(df.reset_index(drop=True).iterrows()):
            lh, la = pregame_lambdas(float(row["elo_delta_home"]))
            st = InPlayState(minute=float(row["decision_minute"]), goals_a=int(row["score_home"]),
                             goals_b=int(row["score_away"]), red_cards_a=int(row["red_home"]),
                             red_cards_b=int(row["red_away"]))
            p = update_inplay_probabilities(lh, la, st)
            out[i] = [p.p_a_win, p.p_draw, p.p_b_win]
        return normalize_probs(out)


class M5_Ensemble:
    """Average of M1 and M2 W/D/L with a cross-fitted multinomial recalibration (train-fold only)."""
    model_id = "M5_ensemble"
    def __init__(self):
        self.m1 = M1_TimeScore(); self.m2 = M2_RemainingPoisson()
        self.cal = LogisticRegression(max_iter=2000, C=1.0); self._fit = False
    def fit(self, train):
        self.m1.fit(train); self.m2.fit(train)
        avg = 0.5 * self.m1.predict_wld(train) + 0.5 * self.m2.predict_wld(train)
        y = train["final_wld"].map({"H": 0, "D": 1, "A": 2})
        self.cal.fit(np.log(np.clip(avg, 1e-9, 1)), y); self.classes_ = list(self.cal.classes_)
        self._fit = True; return self
    def predict_wld(self, df):
        avg = 0.5 * self.m1.predict_wld(df) + 0.5 * self.m2.predict_wld(df)
        if not self._fit:
            return avg
        raw = self.cal.predict_proba(np.log(np.clip(avg, 1e-9, 1)))
        full = np.full((len(df), 3), 1e-9)
        for j, c in enumerate(self.classes_):
            full[:, int(c)] = raw[:, j]
        return normalize_probs(full)


WLD_MODELS = {"M0_static_b1": M0_StaticB1, "M1_time_score": M1_TimeScore,
              "M2_remaining_poisson": M2_RemainingPoisson, "M5_ensemble": M5_Ensemble}


# ---- next-event models ----
_HFEATS = ["score_diff", "decision_minute", "remaining_minutes", "elo_delta_home", "red_diff",
           "score_home", "score_away"]


class M3_GoalHazard:
    """P(any goal in next 5 minutes). Native target: goal_within_5."""
    model_id = "M3_goal_hazard"
    def __init__(self):
        self.scaler = StandardScaler(); self.clf = LogisticRegression(max_iter=2000, C=1.0)
    def fit(self, train):
        self.scaler.fit(train[_HFEATS].fillna(0))
        self.clf.fit(self.scaler.transform(train[_HFEATS].fillna(0)), train["goal_within_5"].astype(int))
        return self
    def predict_proba(self, df):
        return self.clf.predict_proba(self.scaler.transform(df[_HFEATS].fillna(0)))[:, 1]


class M4_CompetingRisk:
    """Competing risk: next goal team in {home, away, none} (within the rest of regulation).
    Native target: next_goal_team."""
    model_id = "M4_competing_risk"
    def __init__(self):
        self.scaler = StandardScaler(); self.clf = LogisticRegression(max_iter=2000, C=1.0)
        self.order = ["home", "away", "none"]
    def fit(self, train):
        self.scaler.fit(train[_HFEATS].fillna(0))
        y = train["next_goal_team"].map({"home": 0, "away": 1, "none": 2})
        self.clf.fit(self.scaler.transform(train[_HFEATS].fillna(0)), y)
        self.classes_ = list(self.clf.classes_); return self
    def predict_proba(self, df):
        raw = self.clf.predict_proba(self.scaler.transform(df[_HFEATS].fillna(0)))
        full = np.full((len(df), 3), 1e-9)
        for j, c in enumerate(self.classes_):
            full[:, int(c)] = raw[:, j]
        return full / full.sum(1, keepdims=True)
