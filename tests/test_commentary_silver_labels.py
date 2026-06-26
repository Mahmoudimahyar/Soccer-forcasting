"""Phase 4 silver-label release tests. Synthetic emissions only; no real data, no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_soccernet_silver_label_release as R  # noqa: E402


def _em(cls="corner"):
    return {"match_id": "epl/2015-2016/m1", "commentary_record_id": "epl/2015-2016/m1#h1#100.0",
            "content_hash": "abc123", "competition": "epl", "season": "2015-2016",
            "event_class": cls, "confidence": 0.93, "event_time_s": 101.0, "alignment_delta_s": -1.0}


def test_record_has_no_raw_text_and_full_provenance():
    r = R.to_silver_record(_em(), source_hash="H")
    R.assert_no_raw_text([r])
    assert not (R.FORBIDDEN & set(r.keys()))
    assert r["commentary_content_hash"] == "abc123" and r["source_hash"] == "H"
    assert r["parser_model_version"] == "precision_v2" and r["source_rights_classification"]


def test_raw_text_injection_is_caught():
    r = R.to_silver_record(_em(), source_hash="H")
    r["text"] = "GOAL! he scores"  # simulate a leak
    try:
        R.assert_no_raw_text([r])
        raised = False
    except AssertionError:
        raised = True
    assert raised


def test_only_approved_classes_enter():
    recs = [R.to_silver_record(_em("corner")), R.to_silver_record(_em("goal"))]
    kept = R.filter_approved(recs, ["corner"])
    assert {r["event_class"] for r in kept} == {"corner"}


def test_all_records_historical_non_live():
    recs = [R.to_silver_record(_em())]
    R.assert_all_historical_non_live(recs)
    r = recs[0]
    assert r["causal_status"] == "historical_weak_supervision_only"
    assert r["live_eligibility"] is False and r["trading_eligibility"] is False


def test_deterministic_record():
    assert R.to_silver_record(_em(), "H") == R.to_silver_record(_em(), "H")


def test_silver_not_imported_by_runtime_or_trading():
    offenders = []
    for sub in ("runtime", "trading"):
        d = ROOT / "src" / "wcdrawlab" / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            if any(k in txt for k in ("silver_label", "precision_models", "research.commentary", "soccernet_")):
                offenders.append(str(f))
    assert offenders == [], f"silver/precision imported by runtime/trading: {offenders}"
