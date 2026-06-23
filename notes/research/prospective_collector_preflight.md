# Prospective Collector Preflight (Section 2, 2026-06-23)

Verified BEFORE activating live collection. Shadow/research only; B1 sole runtime; no trading.

## Environment / plumbing
- Repository root resolves correctly (`scripts/windows/shadow_collector_cycle.py` → parents[2]).
- Interpreter: `sys.executable` (project venv used by the runner if `.venv\Scripts\python.exe` exists).
- `.env` loads via dotenv; `_live_env.load_keys()` logs **names only** (15 keys) — no values printed.
- State/output locations exist and are correct:
  - raw odds: `data/raw/odds/live_2026/` · normalized: `data/processed/odds_live_2026/`
  - predictions (immutable): `outputs/research/live_2026_shadow_predictions.csv`
  - budget state: `outputs/live_shadow/odds_budget.json`
  - heartbeat/state: `outputs/live_shadow/collector_heartbeat.json` / `collector_state.json`
  - scheduler logs: `outputs/live_shadow/scheduler_logs/`

## Safety checks (all pass)
- **No live-trading path reachable:** runtime/trading do not import the operations plane; the cycle
  HALTs (exit 3) unless `KALSHI_ENABLE_LIVE_TRADING==false` and `TRADING_MODE==paper` (both verified).
- **No duplicate / no overwrite:** odds raw snapshots are content-addressed first-write-wins; shadow
  predictions merge with `drop_duplicates(keep="first")` → a prediction is never overwritten post-kickoff.
- **Budget fail-closed:** `OddsBudget` enforces ≤500 credits + ≥10-min spacing across restarts; baseline
  snapshots additionally gated to ≥120-min gaps. Verified by `tests/test_odds_budget.py`.
- **Dry-run did no spend/writes:** `fetch_odds_live_2026.py` (no `--execute`) and
  `shadow_collector_cycle.py --dry-run` both planned only.

## Tests
- `python -m pytest -q` → **203 passed** (incl. 3 new odds-budget tests; prior 200).

## Section-7A integrity (on current predictions)
`shadow_integrity.run_all` → **all_ok = true**: no duplicate snapshots, snapshots pre-kickoff,
probabilities sum to 1, no-vig sums to 1, **blend weights frozen**.

## Verified initial execution
- One real **baseline** Odds API capture: **29 WC events, 1 credit (1/500)**; immutable raw + normalized
  no-vig written.
- `freeze` produced immutable **M1–M5** predictions for 28 upcoming matches (104 approved M1 + 296 shadow).
- Scheduler runner executed one full cycle: exit 0, heartbeat written, freeze/score rc=0.

Preflight PASSED → collector activated (Section 3 scheduler installed).
