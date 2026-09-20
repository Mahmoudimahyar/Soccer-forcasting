"""Phase 4 adapter test — SYNTHETIC SoccerNet-like segments only (no real/copyrighted text)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary.adapters import soccernet_echoes as SNE  # noqa: E402


def test_adapter_marks_historical_only_no_pub_time():
    segs = [{"start_time": 130, "end_time": 134, "text": "Synthetic: home team scores"},
            {"start_time": 200, "end_time": 205, "text": "Synthetic: yellow card shown"}]
    recs = SNE.to_records(segs, canonical_match_id="M1", language="en", retrieval_time_utc="2026-06-23T00:00:00+00:00")
    assert len(recs) == 2
    for r in recs:
        assert r.publication_time_utc_if_known is None          # broadcast time only
        assert r.causal_eligibility_status == "historical_weak_supervision_only"  # never live
        assert r.source_id == "soccernet_echoes" and r.rights_classification == "open_research_download_allowed"
        assert r.normalized_text.startswith("Synthetic:") and r.source_content_hash
