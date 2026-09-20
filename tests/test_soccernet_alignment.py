"""Phase 4/5 alignment-engine tests. Synthetic events + commentary only; no real data, no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_alignment as A  # noqa: E402


def _events():
    return {"m1": [{"half": 1, "t_s": 100.0, "canonical": "goal"},
                   {"half": 1, "t_s": 200.0, "canonical": "yellow_card"}],
            "m2": [{"half": 1, "t_s": 50.0, "canonical": "goal"}]}


def _segs():
    return {"m1": [{"half": 1, "t_s": 105.0, "norm": "what a goal he scores it is in the net"},
                   {"half": 1, "t_s": 205.0, "norm": "he is booked that is a yellow card"},
                   {"half": 1, "t_s": 400.0, "norm": "nothing happening here just midfield play"}],
            "m2": [{"half": 1, "t_s": 56.0, "norm": "goal he scores"}]}


def test_keyword_rules():
    assert A.text_claims_event("what a goal he scores", "goal")
    assert A.text_claims_event("shown a yellow card", "yellow_card")
    assert not A.text_claims_event("just a normal pass", "goal")


def test_recall_and_precision_on_synthetic():
    r = A.evaluate(_events(), _segs(), ["m1"], window_s=45.0, offset_s=0.0)
    assert r["goal"]["recall_L1"] == 1.0
    assert r["goal"]["precision_L1"] == 1.0
    assert r["yellow_card"]["recall_L1"] == 1.0


def test_time_window_excludes_far_segments():
    # goal event at 100 but only commentary far away -> not witnessed
    segs = {"m1": [{"half": 1, "t_s": 300.0, "norm": "a goal earlier"}]}
    r = A.evaluate({"m1": [{"half": 1, "t_s": 100.0, "canonical": "goal"}]}, segs, ["m1"],
                   window_s=45.0, offset_s=0.0)
    assert r["goal"]["recall_L0"] == 0.0 and r["goal"]["recall_L1"] == 0.0


def test_train_offset_uses_only_train_matches():
    # offset estimated on m1 only; m2 (test) must not influence it
    off = A.estimate_train_offset(_events(), _segs(), ["m1"], window_s=45.0)
    # m1 goal dt = +5, yellow dt = +5 -> median 5.0
    assert abs(off - 5.0) < 1e-9


def test_calibration_shifts_timing():
    off = A.estimate_train_offset(_events(), _segs(), ["m1"], window_s=45.0)
    cal = A.evaluate(_events(), _segs(), ["m2"], window_s=45.0, offset_s=off)
    # m2 goal at 50, segment at 56 -> uncal dt=6; calibrated event time 55 -> dt=1
    assert cal["goal"]["n_pairs"] == 1
    assert cal["goal"]["timing_median_abs"] is not None


def test_deterministic():
    a = A.evaluate(_events(), _segs(), ["m1"], window_s=45.0, offset_s=0.0)
    b = A.evaluate(_events(), _segs(), ["m1"], window_s=45.0, offset_s=0.0)
    assert a == b
