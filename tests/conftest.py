from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

# Integration tests require local gitignored datasets that are absent in a clean worktree. Map each
# data-dependent test module to a required data path; if absent, skip the module with an explicit reason and
# a documented separate command (see docs/TESTING_AND_DATA_DEPENDENCIES.md). Unit tests are unaffected.
# Module-level data deps (skip the whole module if absent).
DATA_DEPENDENT_MODULES = {
    "test_inplay_dataset": ROOT / "data/processed/inplay_state_2022_group_stage.parquet",
}
# Test-level data deps (skip only that test function if absent).
DATA_DEPENDENT_TESTS = {
    "test_fixture_855767_reconciles": ROOT / "data/raw/api_football_2022_worldcup/events_855767.json",
}


@pytest.fixture
def seed_root() -> Path:
    return ROOT


def _missing(req):
    return req is not None and not req.exists() and not req.with_suffix(".csv").exists()


def pytest_collection_modifyitems(config, items):
    for item in items:
        mod = item.module.__name__.split(".")[-1] if item.module else ""
        req = DATA_DEPENDENT_MODULES.get(mod) or DATA_DEPENDENT_TESTS.get(item.name)
        if _missing(req):
            item.add_marker(pytest.mark.skip(
                reason=f"integration test: requires gitignored data '{req.name}' (absent in clean worktree). "
                       f"Run with data via: python scripts/run_data_integration_tests.py"))
