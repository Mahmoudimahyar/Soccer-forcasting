"""Preregistered transparent model families (no NN/transformer/LLM). research_only / experimental.

W0 static base-rate; W1 score-diff empirical; W2 remaining-time Poisson (parameter-free m2 base=1.35);
W3 logistic on team-state; W4 +lineup-continuity proxies. N0 base-rate; N1 logistic hazard; N2 +continuity.
C0 yellow base-rate hazard; C1 sending-off hazard (only if >=150 positives).
"""
from __future__ import annotations

import math

from . import _common as C

WDL = ["H", "D", "A"]
M2_BASE = 1.35  # goals per team per 90 (frozen prospective M2 reference; reimplemented, not imported)


def _norm(d):
    s = sum(d.values()) or 1.0
    return {k: v / s for k, v in d.items()}


def _base_rate_wdl(train):
    c = {"H": 0, "D": 0, "A": 0}
    for r in train:
        c[r["target_wdl"]] += 1
    return _norm({k: v + 1e-6 for k, v in c.items()})


def _poisson_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def w2_poisson(row):
    """Remaining-time Poisson: P(final H/D/A) from current score_diff + remaining minutes (parameter-free)."""
    rem = max(0, row["remaining"])
    lam = M2_BASE * rem / 90.0
    diff0 = row["score_diff"]
    pH = pD = pA = 0.0
    for fh in range(0, 8):
        for fa in range(0, 8):
            p = _poisson_pmf(fh, lam) * _poisson_pmf(fa, lam)
            d = diff0 + fh - fa
            if d > 0:
                pH += p
            elif d == 0:
                pD += p
            else:
                pA += p
    return _norm({"H": pH, "D": pD, "A": pA})


def _feat_w3(r):
    return [r["score_diff"], r["card_diff"], r["so_diff"], r["subs_diff"], r["player_count_diff"], r["remaining"]]


def _feat_w4(r):
    return _feat_w3(r) + [r.get("n_starters_home", 0)]


def _fit_logistic_multi(train, featfn):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    X = np.array([featfn(r) for r in train], dtype=float)
    y = np.array([r["target_wdl"] for r in train])
    if len(set(y)) < 2:
        return None
    m = LogisticRegression(max_iter=500, C=1.0, multi_class="multinomial")
    m.fit(X, y)
    return m


def _predict_logistic_multi(model, r, featfn):
    import numpy as np
    if model is None:
        return {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
    probs = model.predict_proba(np.array([featfn(r)], dtype=float))[0]
    return {cls: float(probs[i]) for i, cls in enumerate(model.classes_)}


def wdl_predictors(train):
    """Return {name: predict(row)->{H,D,A}} fitted on train competitions only."""
    br = _base_rate_wdl(train)
    # W1: empirical by score_diff bucket
    buckets = {}
    for r in train:
        b = max(-2, min(2, r["score_diff"]))
        buckets.setdefault(b, {"H": 0, "D": 0, "A": 0})[r["target_wdl"]] += 1
    bucket_p = {b: _norm({k: v + 1e-6 for k, v in c.items()}) for b, c in buckets.items()}
    m3 = _fit_logistic_multi(train, _feat_w3)
    m4 = _fit_logistic_multi(train, _feat_w4)
    return {
        "W0": lambda r: dict(br),
        "W1": lambda r: dict(bucket_p.get(max(-2, min(2, r["score_diff"])), br)),
        "W2": w2_poisson,
        "W3": lambda r: _predict_logistic_multi(m3, r, _feat_w3),
        "W4": lambda r: _predict_logistic_multi(m4, r, _feat_w4),
    }


# ---- next-goal (binary P(goal in next 15)) ----
def _feat_n1(r):
    return [r["minute"], r["score_diff"], r["player_count_diff"], r["card_diff"], r["subs_diff"]]


def _feat_n2(r):
    return _feat_n1(r) + [r.get("n_starters_home", 0)]


def _fit_logistic_bin(train, featfn, target):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    X = np.array([featfn(r) for r in train], dtype=float)
    y = np.array([r[target] for r in train], dtype=int)
    if len(set(y)) < 2:
        return None
    return LogisticRegression(max_iter=500).fit(X, y)


def _predict_bin(model, r, featfn, base):
    import numpy as np
    if model is None:
        return base
    return float(model.predict_proba(np.array([featfn(r)], dtype=float))[0][1])


def nextgoal_predictors(train):
    base = sum(r["next_goal_15"] for r in train) / max(1, len(train))
    n1 = _fit_logistic_bin(train, _feat_n1, "next_goal_15")
    n2 = _fit_logistic_bin(train, _feat_n2, "next_goal_15")
    return {
        "N0": lambda r: base,
        "N1": lambda r: _predict_bin(n1, r, _feat_n1, base),
        "N2": lambda r: _predict_bin(n2, r, _feat_n2, base),
    }
