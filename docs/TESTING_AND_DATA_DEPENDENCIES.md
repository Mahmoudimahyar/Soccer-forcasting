# Testing & Data Dependencies

Two tiers:
1. **Unit tests** — fully synthetic; MUST pass in a clean worktree via `pytest -q`. Cover result semantics,
   causal dataset logic, the deep-research controller, etc.
2. **Integration tests** — require local **gitignored** datasets (e.g.
   `data/processed/inplay_state_2022_group_stage.parquet`). In a clean worktree these are **skipped with an
   explicit reason** by `tests/conftest.py` (they are NOT silently hidden — `pytest -rs` shows skip reasons).

## Commands
- Unit (clean worktree): `pytest -q`  -> all unit tests pass; integration tests reported as skipped.
- Integration (data present): `python scripts/run_data_integration_tests.py` (or `pytest -q tests/test_inplay_dataset.py -rs`).

The skip mechanism is non-invasive (a conftest collection hook keyed on required-data presence); it does NOT
suppress unrelated failures and does NOT modify the integration test files.
