"""Phase 6 derived weak-supervision dataset tests. Synthetic only; proves rights-safety + isolation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_soccernet_weak_supervision_dataset as B  # noqa: E402


def _data():
    events = {"epl/2014-2015/m1": [{"half": 1, "t_s": 100.0, "canonical": "goal"},
                                   {"half": 1, "t_s": 200.0, "canonical": "yellow_card"}]}
    segs = {"epl/2014-2015/m1": [
        {"half": 1, "t_s": 104.0, "norm": "what a goal he scores", "content_hash": "abc123"},
        {"half": 1, "t_s": 203.0, "norm": "he is booked a yellow card", "content_hash": "def456"}]}
    return events, segs


def test_records_contain_no_raw_text():
    events, segs = _data()
    recs = B.emit_records(events, segs, ["epl/2014-2015/m1"], source_hash="HASH")
    B.assert_no_raw_text(recs)  # raises if any forbidden field present
    for r in recs:
        assert not (B.FORBIDDEN & set(r.keys()))


def test_hashes_and_provenance_present():
    events, segs = _data()
    recs = B.emit_records(events, segs, ["epl/2014-2015/m1"], source_hash="HASH")
    assert recs
    for r in recs:
        assert r["commentary_content_hash"] and r["source_hash"] == "HASH"
        assert r["rights_classification"] and r["parser_version"] == "soccernet_ws_v1"


def test_unknown_pub_time_forces_non_live():
    events, segs = _data()
    recs = B.emit_records(events, segs, ["epl/2014-2015/m1"], source_hash="H")
    for r in recs:
        assert r["causal_eligibility"] == "historical_weak_supervision_only"
        assert "no_publication_time" in r["source_timing_status"]


def test_deterministic_rebuild():
    events, segs = _data()
    a = B.emit_records(events, segs, ["epl/2014-2015/m1"], source_hash="H")
    b = B.emit_records(events, segs, ["epl/2014-2015/m1"], source_hash="H")
    assert a == b


def test_soccernet_modules_not_imported_by_runtime_or_trading():
    offenders = []
    for sub in ("runtime", "trading"):
        d = ROOT / "src" / "wcdrawlab" / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            if "soccernet_" in txt or "research.commentary" in txt:
                offenders.append(str(f))
    assert offenders == [], f"soccernet/commentary imported by runtime/trading: {offenders}"
