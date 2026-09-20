"""Phase 3 SoccerNet mapping + taxonomy tests. Synthetic game IDs only; no real data, no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_mapping as M  # noqa: E402


def test_exact_match():
    r = M.map_games(["epl/2015-2016/g1"], ["epl/2015-2016/g1"])
    assert r["epl/2015-2016/g1"]["status"] == "exact" and r["epl/2015-2016/g1"]["confidence"] == 1.0


def test_normalized_match_alias_whitespace_case():
    r = M.map_games(["EPL/2015-2016/G1 "], ["epl/2015-2016/g1"])
    e = r["EPL/2015-2016/G1 "]
    assert e["status"] == "normalized" and e["label_id"] == "epl/2015-2016/g1" and e["confidence"] == 0.9


def test_ambiguous_and_collision():
    # two label ids normalizing to the same key -> ambiguous join + collision detected
    labels = ["epl/2015/g 1", "epl/2015/g_1"]
    assert M.detect_collisions(labels)
    r = M.map_games(["epl/2015/g1_x"], labels)  # different game -> missing (not ambiguous)
    assert r["epl/2015/g1_x"]["status"] == "missing"
    r2 = M.map_games(["EPL/2015/G 1"], labels)  # normalizes to same key as both labels -> ambiguous
    assert r2["EPL/2015/G 1"]["status"] == "ambiguous"


def test_date_season_mismatch_does_not_match():
    r = M.map_games(["epl/2015-2016/g1"], ["epl/2016-2017/g1"])
    assert r["epl/2015-2016/g1"]["status"] == "missing"


def test_override_path():
    ov = {"weird/echoes/id": {"echoes_game": "weird/echoes/id", "label_game": "epl/2015/g1",
                              "confidence": 1.0}}
    r = M.map_games(["weird/echoes/id"], ["epl/2015/g1"], overrides=ov)
    assert r["weird/echoes/id"]["status"] == "override" and r["weird/echoes/id"]["label_id"] == "epl/2015/g1"


def test_deterministic_mapping():
    a = M.map_games(["epl/2015/g1", "epl/2015/g2"], ["epl/2015/g1"])
    b = M.map_games(["epl/2015/g1", "epl/2015/g2"], ["epl/2015/g1"])
    assert a == b


def test_taxonomy_supported_and_unsupported():
    assert M.map_to_canonical_event("Goal")[0] == "goal"
    assert M.map_to_canonical_event("Yellow->red card")[0] == "second_yellow"
    assert M.map_to_canonical_event("Throw-in")[1] == "mapped_to_other"
    assert M.map_to_canonical_event("NotARealClass") == ("unknown", "unsupported_source_event", 0.0)
    # canonical classes with no SoccerNet-v2 source are explicitly unsupported
    assert "own_goal" in M.CANONICAL_UNSUPPORTED and "VAR_goal_cancelled" in M.CANONICAL_UNSUPPORTED


def test_normalize_is_stable():
    assert M.normalize_game_id("A/B C/D ") == M.normalize_game_id("a/b_c/d")
