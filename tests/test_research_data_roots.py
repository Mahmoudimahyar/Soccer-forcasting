"""Tests for the canonical data-root registry. Prove all jobs resolve the same roots + fail closed."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR  # noqa: E402


def test_statsbomb_root_is_single_canonical():
    # every job must resolve the SAME StatsBomb root through the registry (no path fragmentation)
    assert DR.get_root("statsbomb_raw").name == "statsbomb_open"
    assert (DR.get_root("statsbomb_raw") / "events").parent == DR.get_root("statsbomb_raw")


def test_player_history_canonical_root():
    assert DR.get_root("api_football_player_history").as_posix().endswith("data/raw/api_football_player_history")


def test_unknown_root_fails_closed():
    try:
        DR.get_root("does_not_exist"); raised = False
    except KeyError:
        raised = True
    assert raised


def test_collector_checkout_is_forbidden():
    # the active collector checkout must be declared forbidden and never resolvable as a data source
    assert any("worldcup_draw_model_lab_FINAL" in f for f in DR.forbidden_roots())


def test_all_roots_resolve():
    for name in DR._load()["roots"]:
        DR.get_root(name)  # raises if it resolves into the collector checkout


def test_raw_roots_are_gitignored_flagged():
    cfg = DR._load()
    for name, r in cfg["roots"].items():
        if "raw" in name or name.startswith("api_football") or name.startswith("statsbomb"):
            assert r.get("gitignored") is True
