"""Tests for the flagged low-confidence historical-signal product. Synthetic emissions; no real data."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import build_commentary_low_confidence_signals as L  # noqa: E402


def _em(cls="corner"):
    return {"match_id": "epl/2015-2016/m1", "commentary_record_id": "epl/2015-2016/m1#h1#100.0",
            "content_hash": "abc123", "competition": "epl", "season": "2015-2016",
            "event_class": cls, "confidence": 0.71, "event_time_s": 101.0, "alignment_delta_s": -1.0}


def test_record_is_flagged_non_silver_non_live_with_no_raw_text():
    r = L.to_low_conf_record(_em(), wilson_lb=0.768, source_hash="H")
    L.assert_no_raw_text([r])
    assert r["is_silver"] is False and r["confidence_tier"] == "low_confidence"
    assert r["live_eligibility"] is False and r["runtime_eligibility"] is False and r["trading_eligibility"] is False
    assert r["causal_status"] == "historical_weak_supervision_only"
    assert r["quality_estimate_precision_wilson_lb"] == 0.768
    assert not (L.FORBIDDEN & set(r.keys()))


def test_raw_text_injection_caught():
    r = L.to_low_conf_record(_em(), 0.77, "H"); r["norm"] = "leaked"
    try:
        L.assert_no_raw_text([r]); raised = False
    except AssertionError:
        raised = True
    assert raised


def test_only_eligible_classes_allowed():
    recs = [L.to_low_conf_record(_em("corner"), 0.77), L.to_low_conf_record(_em("goal"), 0.56)]
    try:
        L.assert_flagged_non_silver_non_live(recs, {"corner", "foul", "yellow_card"}); raised = False
    except AssertionError:
        raised = True
    assert raised  # 'goal' is not an eligible low-confidence class


def test_deterministic_record():
    assert L.to_low_conf_record(_em(), 0.77, "H") == L.to_low_conf_record(_em(), 0.77, "H")


def test_not_imported_by_runtime_or_trading():
    offenders = []
    for sub in ("runtime", "trading"):
        d = ROOT / "src" / "wcdrawlab" / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            t = f.read_text(encoding="utf-8", errors="ignore")
            if any(k in t for k in ("low_confidence_signals", "precision_models", "research.commentary", "soccernet_")):
                offenders.append(str(f))
    assert offenders == []
