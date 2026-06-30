# QUICKSTART — Operating the World Cup Forecasting Lab

This guide takes a fresh clone to **two running background processes**, end to end. Everything here is
**research-only and paper-only** — no orders are ever placed, no model is changed by results, and market
odds are used only as a read-only benchmark.

> New here? Read this top to bottom once. The deep references are linked inline; you don't need them to start.

---

## 0. The two processes you can start

| Process | What it does | Cadence | Scheduled task |
|---|---|---|---|
| **Shadow Collector** | Captures odds snapshots, freezes immutable B1/M1–M5 1X2 predictions for upcoming 2026 fixtures, and scores finished matches. Budget-capped (500 Odds-API credits), paper-only. | every 5 min | `WorldCupShadowCollector` |
| **Prospective Score Harvester** (+ watchdog) | Refreshes verified-final results and scores the frozen predictions into a model-vs-market benchmark (append-only). Never calls the Odds API. | every 15 min | `WorldCupProspectiveScoreHarvester` (+ `...Watchdog`) |

Both are **bounded single-cycle** programs invoked by the OS scheduler — not daemons, not loops.

---

## 1. Prerequisites

- **Python 3.10+** (3.13 tested), **git**.
- **Windows 10/11** for the included scheduled-task installers (PowerShell). On Linux/macOS use cron — see
  [`docs/CRON_SETUP.md`](docs/CRON_SETUP.md); the Python entry points are identical.
- API accounts (free tiers are enough to start) — see [`docs/ACCOUNT_AND_API_SETUP.md`](docs/ACCOUNT_AND_API_SETUP.md).

---

## 2. Install

```bash
git clone <this-repo-url> wc-lab && cd wc-lab
python -m venv .venv
# Windows:  .venv\Scripts\activate        # macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
pytest -q          # sanity check (see note below)
```

> Note: a couple of pre-existing tests read **gitignored historical data** that isn't in a fresh clone and
> will error with `FileNotFoundError` until you run the data bootstrap (step 4). Everything else passes. To
> skip just those: `pytest -q --ignore=tests/test_event_semantics.py --ignore=tests/test_inplay_dataset.py`.

---

## 3. Secrets — create `.env`

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Fill in the keys you have. **Keep the safety flags exactly as shipped.**

| Key | Used by | Needed for |
|---|---|---|
| `ODDS_API_KEY` | Collector | Live odds snapshots (The Odds API) |
| `FOOTBALL_DATA_KEY` | Collector + Harvester | Final results (football-data.org) |
| `API_FOOTBALL_KEY` | Queue builder (optional) | Fixture list / Elo anchors (API-Football) |
| `KALSHI_ENABLE_LIVE_TRADING=false` | — | **Must stay `false`.** Hard safety flag. |
| `TRADING_MODE=paper` | — | **Must stay `paper`.** |

`.env` is gitignored — never commit it, never paste secrets into a chat. A safe audit prints only
`SET`/`MISSING`, never values.

---

## 4. Bootstrap the data (one-time)

Historical/raw datasets and the forecast targets are **gitignored** (reproducible, not shipped). Build them:

```bash
python scripts/build_research_table.py        # -> data/processed/forecast_targets_2026.csv (+ research table, elo_history)
python scripts/build_future_2026_queue.py     # -> data/reference/future_2026_prospective_queue.csv  (needs API_FOOTBALL_KEY)
```

`build_research_table.py` builds a leakage-safe table from open data (martj42 international results,
jfjelstul WC history, football-data.org 2026 structure). If a download step needs a key or source you don't
have yet, follow [`docs/DATA_SOURCE_GOVERNANCE.md`](docs/DATA_SOURCE_GOVERNANCE.md) and
[`docs/ACCOUNT_AND_API_SETUP.md`](docs/ACCOUNT_AND_API_SETUP.md). Confirm both CSVs exist before starting the collector.

---

## 5. Start the Shadow Collector

**Test one cycle first** (safe by default — no spend, no writes):
```bash
python scripts/windows/shadow_collector_cycle.py --dry-run
```
Then a real cycle (writes heartbeat/state, may spend 1 odds credit if a window is due):
```bash
python scripts/windows/shadow_collector_cycle.py
```

**Install the durable 5-min task (Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_shadow_collector_task.ps1
# optional params: -IntervalMinutes 5 -HardEndUtc "2026-07-05T00:00:00Z"
```
- Heartbeat/state/budget: `outputs/live_shadow/collector_heartbeat.json`, `collector_state.json`, `odds_budget.json`
- Frozen predictions: `outputs/research/live_2026_shadow_predictions.csv` (immutable, append-only)
- **Stop:** `powershell -File scripts\windows\uninstall_shadow_collector_task.ps1`
  (or `Disable-ScheduledTask -TaskName WorldCupShadowCollector`)

Full operating detail: [`docs/PROSPECTIVE_COLLECTION_RUNBOOK.md`](docs/PROSPECTIVE_COLLECTION_RUNBOOK.md),
[`docs/WINDOWS_SCHEDULER_SETUP.md`](docs/WINDOWS_SCHEDULER_SETUP.md).

---

## 6. Start the Prospective Score Harvester

**Run one cycle** (refresh final results if needed + score, append-only):
```bash
python scripts/run_prospective_score_harvester.py
```
Or run the pipeline phase-by-phase (handy for inspection):
```bash
python scripts/refresh_prospective_final_results.py        # verified-final results (no Odds API)
python scripts/audit_prospective_result_reconciliation.py  # reconciliation audit (must be all_ok)
python scripts/select_primary_prospective_snapshots.py     # one snapshot per fixture (preregistered rule)
python scripts/prospective_score_harvester_v1.py           # idempotent, append-only scoring
python scripts/prospective_benchmark_v1.py                 # B1 vs no-vig market vs blends + decision ledger
```

**Install the durable 15-min task + watchdog (Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_prospective_score_harvester_tasks.ps1
```
- Outputs: `outputs/live_shadow/scoring_v1/` (scorecards, metrics, integrity audit, heartbeat/state/log)
- Reports: `notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md`, `..._MARKET_BENCHMARK_V1.md`, `..._CALIBRATION_AND_RELIABILITY_V1.md`
- Decision ledger: `data/reference/prospective_model_decision_ledger.{json,csv}`
- **Stop:** `powershell -File scripts\windows\uninstall_prospective_score_harvester_tasks.ps1`

> **Split setup:** if your collector runs in a *different* checkout than the harvester, point the harvester
> at the collector's inputs with `PSH_COLLECTOR_ROOT`:
> `PSH_COLLECTOR_ROOT="C:/path/to/collector/checkout" python scripts/run_prospective_score_harvester.py`.
> In a single clone you don't need this — it defaults to the repo root.

Deep dive: [`docs/SCORE_HARVEST_GUIDE.md`](docs/SCORE_HARVEST_GUIDE.md).

---

## 7. Read the results

```bash
cat outputs/live_shadow/collector_heartbeat.json                 # collector alive?  status=ok
cat outputs/live_shadow/scoring_v1/scoring_integrity_audit.json  # harvester invariants (all_ok=true)
cat outputs/live_shadow/scoring_v1/model_metrics.csv             # RPS / log-loss / Brier / calibration per model
```
The committed reports under `notes/research/PROSPECTIVE_*` contain the human-readable benchmark.

---

## 8. Stop everything

```powershell
# Stop all lab background tasks at once (reversible):
Get-ScheduledTask | Where-Object { $_.TaskName -like 'WorldCup*' } | Disable-ScheduledTask
# Re-enable any later:
Enable-ScheduledTask -TaskName WorldCupShadowCollector
```
Disabling does not delete anything — state, ledgers, and outputs are preserved. To fully remove the tasks,
run the matching `uninstall_*` scripts.

---

## Safety — what this is and is NOT

- **Paper-only.** `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. No order/trade path is reachable
  from either process. The harvester never even imports a trading module.
- **Research-only.** No 2026 result is ever used to fit, calibrate, retrain, or select a model. Market odds
  are a read-only benchmark, never a feature or target.
- **B1** (ternary-Elo, r=0.4) is the only runtime-approved pre-match model; M1–M5 and `m2_frozen` are
  research/shadow. Nothing here promotes a model — see [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).
- Immutable, first-write-wins ledgers; frozen predictions are never rewritten or backfilled after kickoff.

## Repository map

```
scripts/                         entry points (collector cycle, builders, harvester pipeline)
scripts/windows/                 PowerShell wrappers + scheduled-task install/uninstall
scripts/prospective_harvest/     harvester internals (Phase 0 freeze, shared helpers)
src/wcdrawlab/                   library (ratings, evaluation, ingest, operations adapters)
data/                            processed/reference inputs (mostly gitignored; built in step 4)
outputs/                         runtime artifacts (gitignored): collector state, scoring_v1/
notes/research/                  reports, audits, decision ledgers, durable state files
docs/                            detailed runbooks, policies, account/API setup
tests/                           deterministic test suite
```
