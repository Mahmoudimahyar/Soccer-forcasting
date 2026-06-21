# Changelog

## Probability documentation + risk release

Added:

- full documentation suite under `docs/`
- `src/wcdrawlab/risk.py`
- risk and standard deviation columns for every prediction
- probability standard errors and Beta-approximation intervals
- entropy/confidence/risk-band reporting
- draw-bet expected value and standard deviation per unit staked
- tests for risk calculations

Updated:

- `README.md` now explains documentation and uncertainty outputs
- `pipeline.py` now adds uncertainty columns to `predictions.csv` and `edges.csv`
- `market.py` now adds draw-bet risk columns to edge scans

Validation:

- `pytest -q`: 12 passed
- `python examples/run_seed_2026.py`: runs and writes updated risk-aware outputs

## 0.1.3 — Live after-game update workflow

Added:
- `src/wcdrawlab/live.py` with event-driven after-match result ingestion.
- `wcdrawlab predict-live` command to refresh remaining-match predictions.
- `wcdrawlab update-after-match` command to insert final scores and recompute standings, advancement probabilities, draw utilities, risks, and draw edges.
- `docs/PREDICTION_TARGETS_AND_UPDATE_CADENCE.md` explaining exactly what the model predicts.
- `docs/AFTER_GAME_UPDATE_WORKFLOW.md` explaining how to update the system after each completed game.
- `examples/run_after_match_update.py` showing an end-to-end after-game update.
- Tests for live updates and prediction risk columns.

Notes:
- The live model uses a conservative deployable blend when no trained historical model is supplied.
- The intended production cadence is event-driven: update immediately after each final score, then refresh odds/lineups before the next match.

## Final handoff package

- Added `START_HERE_CLAUDE_CODE.md` as the repository handoff entry point.
- Added `docs/CLAUDE_CODE_MASTER_PROMPT.md` containing the full first-session Claude Code instruction set.
- Added `docs/ACCOUNT_AND_API_SETUP.md` with safe account/API setup and `.env` handling rules.
- Added placeholder directories for processed research data, research outputs, and pending data requests.
