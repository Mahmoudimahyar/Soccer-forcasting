"""Phase 2: precision-first event-extraction model ladder (transparent, local; NO external LLM/NLP APIs).

R0  time-only candidate alignment (any within-window segment witnesses the event)  -> in soccernet_alignment
R1  deterministic preregistered rules + class-specific NEGATION/correction handling
R2  local TF-IDF (word + char n-grams) + regularized logistic regression, per class
R3  hybrid confidence = blend(R2 prob, R1 rule score)  (text-only; no event-time peeking -> no leakage)
R4  abstention: emit only when R3 confidence > a TRAIN-selected threshold (see silver_label_policy)

Supervision is the proximity weak-label y_C(segment) = 1 iff a real SoccerNet event of class C lies within
the alignment window of the segment (half-relative). Precision is measured against the same proximity truth.
research_only / historical_weak_supervision_only / not_live_eligible.
"""
from __future__ import annotations

import re

from . import soccernet_alignment as A  # KEYWORD_RULES, _COMPILED, text_claims_event
from . import quality as Q

# Class-specific NEGATION / near-miss patterns. Firing one of these suppresses the rule hit for that class.
# This is the core precision lever for 'goal' (keyword 'goal' is highly polysemous).
NEGATORS = {
    "goal": [r"\bno goal\b", r"disallow", r"ruled out", r"chalked off", r"\bchance\b", r"\bnearly\b",
             r"\balmost\b", r"\bsaved?\b", r"\bsave\b", r"goal\s*kick", r"goalkeeper", r"\bkeeper\b",
             r"\bwide\b", r"over the bar", r"off the post", r"hits the (post|bar)", r"\bblocked\b",
             r"\bclose\b", r"could have", r"should have", r"\boffside\b"],
    "shot_on_target": [r"\bblocked\b", r"\bwide\b", r"over the bar"],
    "shot": [r"\bgoal\b", r"on target"],
    "corner": [r"corner flag", r"corner of the (box|area)"],
    "yellow_card": [r"no card", r"\bescapes? a", r"\bwaves? (play|it) on\b", r"avoids? a"],
    "red_card": [r"no card", r"\byellow\b", r"\bnot a red\b"],
    "penalty_awarded": [r"penalty (box|area|spot)", r"no penalty", r"waves? (it|play) on", r"\bappeal"],
    "substitution": [r"substitutes'? bench", r"about to (come|be)"],
    "offside": [r"\bnot offside\b", r"onside"],
    "foul": [r"no foul", r"\bplay on\b", r"\bclean\b"],
    "kickoff": [],
}


def _compiled_neg(cls):
    return [re.compile(p) for p in NEGATORS.get(cls, [])]


_NEG = {c: _compiled_neg(c) for c in A.KEYWORD_RULES}


def r1_rule_score(norm_text: str, cls: str) -> float:
    """1.0 if the class keyword fires and no class-negator/correction fires, else 0.0 (deterministic)."""
    t = norm_text or ""
    if not A.text_claims_event(t, cls):
        return 0.0
    if Q.is_correction(t):
        return 0.0
    if any(p.search(t) for p in _NEG.get(cls, [])):
        return 0.0
    return 1.0


def r1_keyword_hits(norm_text: str, cls: str) -> int:
    return sum(1 for p in A._COMPILED.get(cls, []) if p.search(norm_text or ""))


def build_vectorizer():
    """FeatureUnion of word(1,2) + char_wb(3,5) TF-IDF, capped. Fit on TRAIN segments only (unsupervised)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    word = TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_features=30000, sublinear_tf=True)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, max_features=20000,
                           sublinear_tf=True)
    return FeatureUnion([("word", word), ("char", char)])


class PrecisionModels:
    """Per-class TF-IDF + logistic regression (R2) and an R3 hybrid blend with the R1 rule score.

    Fit only on training-competition data. Stores a shared (unsupervised) vectorizer + per-class linear models.
    """

    def __init__(self, alpha=0.5, C=4.0):
        self.alpha = alpha        # R3 weight on R2 prob (1-alpha on R1 rule score)
        self.C = C
        self.vec = None
        self.models = {}          # cls -> fitted LogisticRegression

    def fit(self, texts, labels_by_class):
        from sklearn.linear_model import LogisticRegression
        self.vec = build_vectorizer()
        X = self.vec.fit_transform(texts)
        for cls, y in labels_by_class.items():
            if sum(y) < 10 or sum(y) == len(y):
                self.models[cls] = None
                continue
            m = LogisticRegression(C=self.C, class_weight="balanced", max_iter=400, solver="liblinear")
            m.fit(X, y)
            self.models[cls] = m
        return self

    def r2_proba(self, texts, cls):
        m = self.models.get(cls)
        if m is None:
            return [0.0] * len(texts)
        X = self.vec.transform(texts)
        return list(m.predict_proba(X)[:, 1])

    def r3_confidence(self, texts, norm_texts, cls):
        """Hybrid text-only confidence in [0,1]; gated by the R1 rule (no rule hit -> 0)."""
        probs = self.r2_proba(texts, cls)
        out = []
        for p, nt in zip(probs, norm_texts):
            rule = r1_rule_score(nt, cls)
            conf = self.alpha * p + (1 - self.alpha) * rule
            out.append(conf if rule > 0 else 0.0)  # abstain unless the deterministic rule also fires
        return out
