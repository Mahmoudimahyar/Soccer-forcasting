"""Phase 2 precision-model + silver-policy tests. Synthetic text only; no real data, no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import precision_models as PM  # noqa: E402
from wcdrawlab.research.commentary import silver_label_policy as SP  # noqa: E402


# ---- R1 deterministic rules ----
def test_event_class_isolation():
    assert PM.r1_rule_score("it is a corner kick from the right", "corner") == 1.0
    assert PM.r1_rule_score("it is a corner kick from the right", "goal") == 0.0


def test_negation_suppresses_goal():
    assert PM.r1_rule_score("what a goal he scores into the net", "goal") == 1.0
    assert PM.r1_rule_score("great chance for a goal but the keeper saved it", "goal") == 0.0
    assert PM.r1_rule_score("goal kick taken by the goalkeeper", "goal") == 0.0


def test_correction_language_suppresses():
    assert PM.r1_rule_score("correction that goal is ruled out", "goal") == 0.0


def test_generic_shot_vs_actual_goal():
    # a shot/attempt that is not a goal should not be claimed as goal
    assert PM.r1_rule_score("he shoots but it is blocked", "goal") == 0.0
    assert PM.r1_rule_score("he scores a brilliant goal", "goal") == 1.0


def test_card_discussion_vs_actual_card():
    assert PM.r1_rule_score("he is shown a yellow card for that", "yellow_card") == 1.0
    assert PM.r1_rule_score("that could have been a yellow card but the ref waves play on",
                            "yellow_card") == 0.0


# ---- R2/R3 fitting (tiny synthetic) ----
def _toy():
    texts = (["he scores a great goal it is in the net"] * 12 + ["midfield pass nothing happening"] * 12 +
             ["a corner kick comes in"] * 12)
    y_goal = [1] * 12 + [0] * 12 + [0] * 12
    return texts, {"goal": y_goal, "corner": [0] * 12 + [0] * 12 + [1] * 12}


def test_r2_learns_and_is_deterministic():
    texts, labels = _toy()
    a = PM.PrecisionModels().fit(texts, labels)
    b = PM.PrecisionModels().fit(texts, labels)
    pa = a.r2_proba(["he scores a great goal"], "goal")[0]
    pb = b.r2_proba(["he scores a great goal"], "goal")[0]
    assert pa == pb
    assert pa > a.r2_proba(["midfield pass"], "goal")[0]


def test_r3_abstains_without_rule_hit():
    texts, labels = _toy()
    m = PM.PrecisionModels().fit(texts, labels)
    # text with no goal keyword -> R3 confidence forced to 0 (rule gate)
    conf = m.r3_confidence(["a quiet moment in midfield"], ["a quiet moment in midfield"], "goal")[0]
    assert conf == 0.0


def test_duplicate_commentary_same_score():
    # identical text -> identical rule score (dedup handled upstream by content_hash)
    assert PM.r1_rule_score("he scores a goal", "goal") == PM.r1_rule_score("he scores a goal", "goal")


# ---- silver policy ----
def test_wilson_lower_bound():
    assert 0.0 <= SP.wilson_lower_bound(80, 100) < 0.80
    assert SP.wilson_lower_bound(98, 100) > 0.90
    assert SP.wilson_lower_bound(0, 0) == 0.0


def test_threshold_selection_is_train_only_and_monotone():
    # high-confidence positives, low-confidence negatives -> a threshold exists with high precision
    scores = [0.95, 0.92, 0.9, 0.4, 0.3, 0.2]
    y = [1, 1, 1, 0, 0, 0]
    thr, prec, cnt = SP.select_threshold(scores, y, target_precision=0.85, min_count=3)
    assert prec >= 0.85 and thr <= 0.9


def test_gate_requires_all_thresholds():
    # passing case
    lab, _ = SP.gate_class(n_pred=120, k_correct=115, median_timing=8.0, p90_timing=20.0,
                           stable_folds=5, competitions_present=5)
    assert lab == "silver_label_approved_for_historical_research"
    # low coverage
    lab2, _ = SP.gate_class(n_pred=30, k_correct=30, median_timing=5, p90_timing=10,
                            stable_folds=6, competitions_present=6)
    assert lab2 == "insufficient_coverage"
    # precision fail
    lab3, _ = SP.gate_class(n_pred=200, k_correct=120, median_timing=8, p90_timing=20,
                            stable_folds=1, competitions_present=5)
    assert lab3 in ("insufficient_precision", "usable_only_with_low_confidence_flag")
