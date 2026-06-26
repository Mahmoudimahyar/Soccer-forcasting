"""Guard against done-list over-reporting: completion must be measured by ACTUAL raw-backed coverage across
registered roots. Regression test for the 2026-06-26 audit finding (60 done ids unbacked in canonical)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import corpus_coverage as CC  # noqa: E402
from wcdrawlab.research import data_roots as DR  # noqa: E402

def _done():
    p = DR.get_root("api_football_player_history") / "progress.json"
    return [str(x) for x in json.loads(p.read_text(encoding="utf-8"))["done"]] if p.exists() else []

def test_done_corpus_is_fully_raw_backed():
    done = _done()
    if not done:
        return  # nothing acquired in this checkout
    cov = CC.coverage(done)
    assert cov["missing_ids"] == [], f"{len(cov['missing_ids'])} done ids lack events+lineups raw"
    assert cov["coverage_rate"] == 1.0

def test_canonical_root_is_self_contained():
    done = _done()
    if not done:
        return
    cov = CC.coverage(done)
    assert cov["per_root_full_events_and_lineups"]["canonical"] >= len(done)

def test_coverage_flags_unbacked_id():
    cov = CC.coverage(["000000000"])  # synthetic id with no raw anywhere
    assert "000000000" in cov["missing_ids"]
    assert cov["coverage_rate"] == 0.0
