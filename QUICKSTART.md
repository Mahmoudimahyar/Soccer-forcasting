# QUICKSTART — Operating the World Cup Forecasting Lab

> [!IMPORTANT]
> **Status — read first (2026-09-20).** The 2026 collection window has **closed**. The collector's default
> hard end is 2026-07-05, and only the **group stage** was collected; knockout rounds were never collected
> or scored. The steps below document how the prospective evaluation was run and how to replay the
> pipeline. They will not collect anything new today: a collector cycle now just records
> `stopped_hard_end` and exits.
>
> - **Committed results:**
>   [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md),
>   [`PROSPECTIVE_MARKET_BENCHMARK_V1.md`](notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md) and
>   [`PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md`](notes/research/PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md)
>   in `notes/research/` (with the other `PROSPECTIVE_*` files there), plus the decision ledger
>   `data/reference/prospective_model_decision_ledger.{json,csv}`.
> - **Two collector defects** are documented in [`docs/ERRATA.md`](docs/ERRATA.md). **E2:** the prediction
>   freezer ignored every odds snapshot the scheduled collector captured, so the benchmark's market is an
>   early line, not a closing line (fixed 2026-09-20; the historical ledger is unchanged). **E3:** the
>   collector's built-in score step never scored anything and was never patched; the independent harvester
>   is the only working scoring path.
> - **What a fresh clone cannot do:** regenerate the benchmark numbers. The prediction ledger, odds
>   snapshots and results are runtime artifacts (gitignored, not shipped). The tracked public record is the
>   reports above, the decision ledger, and
>   `data/reference/prospective_frozen_input_manifest.{json,csv}` (hashes and per-row timestamps).

This guide takes a fresh clone to **two scheduled background processes**, end to end, as they were run
during the 2026 group stage. Everything here is **research-only and paper-only** — no orders are ever
placed, no model is changed by results, and market odds are used only as a read-only benchmark. Nothing
here is betting or financial advice.

> New here? Read this top to bottom once. The deep references are linked inline; you don't need them to start.
> For the project overview and results, see [`README.md`](README.md). For the older v0.1 toolkit CLI
> (backtests, truth tables, after-game updates), see [`docs/TOOLKIT_USAGE.md`](docs/TOOLKIT_USAGE.md).

---

## 0. The two processes you can start

| Process | What it does | Cadence | Scheduled task |
|---|---|---|---|
| **Shadow Collector** | Captures odds snapshots and freezes immutable 1X2 predictions from the pre-match shadow set M1–M5 (M1 is B1, `M2_market` is the no-vig market, M3–M5 are fixed blends) for upcoming 2026 fixtures. It also has a built-in score step, but that step never worked (see E3 above). Budget-capped (500 Odds API credits), paper-only. | every 5 min | `WorldCupShadowCollector` |
| **Prospective Score Harvester** (+ watchdog) | Refreshes verified-final results and scores the frozen predictions into a model-vs-market benchmark (append-only). Never calls the Odds API. | every 15 min | `WorldCupProspectiveScoreHarvester` (+ `...Watchdog`) |

Both are **bounded single-cycle** programs invoked by the OS scheduler — not daemons, not loops.

---

## 1. Prerequisites

- **Python 3.10+** (3.13 tested), **git**.
- **Windows 10/11** for the included scheduled-task installers (PowerShell). On Linux/macOS use cron — see
  [`docs/CRON_SETUP.md`](docs/CRON_SETUP.md); the Python entry points are identical. (The Windows path is
  the one that was actually run in 2026.)
- API accounts — see [`docs/ACCOUNT_AND_API_SETUP.md`](docs/ACCOUNT_AND_API_SETUP.md). The collector caps
  its total Odds API spend at 500 credits, and the football-data.org calls were written for that
  provider's free tier. The optional API-Football queue refresh in step 4 was run on a paid plan: the
  lab's own audit records that the free tier was limited to the 2022–2024 seasons
  ([`live_provider_truth_audit.md`](notes/research/live_provider_truth_audit.md)).

---

## 2. Install

```bash
git clone https://github.com/Mahmoudimahyar/Soccer-forcasting.git wc-lab && cd wc-lab
python -m venv .venv
# Windows:  .venv\Scripts\activate        # macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
pip install -e .   # installs the package and the `wcdrawlab` CLI
pytest -q          # sanity check (see note below)
```

> Note: on a fresh clone expect **817 passed, 51 skipped, 0 failed** (verified 2026-09-20, Python 3.13,
> Windows). The skips are integration tests that need gitignored datasets or the author's external event
> lake; `tests/conftest.py` skips them with an explicit reason (`pytest -q -rs` shows each one). See
> [`docs/TESTING_AND_DATA_DEPENDENCIES.md`](docs/TESTING_AND_DATA_DEPENDENCIES.md).

---

## 3. Secrets — create `.env`

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Fill in the keys you have. **Keep the safety flags exactly as shipped.**

| Key | Used by | Needed for |
|---|---|---|
| `ODDS_API_KEY` | Collector | Live odds snapshots (The Odds API) |
| `FOOTBALL_DATA_KEY` | Harvester (result refresh); `scripts/fetch_footballdata_2026.py` | Final results and 2026 group structure (football-data.org) |
| `API_FOOTBALL_KEY` | Queue builder (optional) | 2026 fixture list (API-Football; paid plan for the 2026 season) |
| `KALSHI_ENABLE_LIVE_TRADING=false` | — | **Must stay `false`.** Hard safety flag. |
| `TRADING_MODE=paper` | — | **Must stay `paper`.** |

`.env` is gitignored — never commit it, never paste secrets into a chat. A safe audit prints only
`SET`/`MISSING`, never values.

---

## 4. Bootstrap the data (one-time)

Historical/raw datasets and the forecast targets are **gitignored** (reproducible, not shipped). Build them:

```bash
python -m wcdrawlab.cli fetch-public          # open CSVs -> data/raw/ (network, no key needed)
python scripts/fetch_footballdata_2026.py     # optional: 2026 group structure + results (needs FOOTBALL_DATA_KEY)
python scripts/build_research_table.py        # -> data/processed/forecast_targets_2026.csv (+ research table, elo_history)
```

`build_research_table.py` builds a leakage-tested table from open data: martj42 international results and
the jfjelstul World Cup history, both downloaded by the first command. It stops with `FileNotFoundError` if
`data/raw/international_results.csv` or `data/raw/jf_worldcup_matches.csv` is missing. For the 2026 group
structure it uses the football-data.org file from the optional second command when that file exists, and
otherwise reconstructs the groups from the fixture list and the seed snapshot.

Two cautions. Upstream files change, so a table rebuilt today will not be byte-identical to the one used in
June 2026. And `forecast_targets_2026.csv` holds only fixtures that have no score yet, so a rebuild after
the tournament should leave it with few or no rows. For source terms and keys, see
[`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md),
[`docs/DATA_SOURCE_GOVERNANCE.md`](docs/DATA_SOURCE_GOVERNANCE.md) and
[`docs/ACCOUNT_AND_API_SETUP.md`](docs/ACCOUNT_AND_API_SETUP.md).

The second input, `data/reference/future_2026_prospective_queue.csv`, is **already tracked in git** (the
queue as built during the tournament), so a fresh clone has it. The build step below only *refreshes* it:

```bash
python scripts/build_future_2026_queue.py     # refreshes data/reference/future_2026_prospective_queue.csv  (needs API_FOOTBALL_KEY; 1 API call)
```

> [!WARNING]
> Skip the refresh unless you know you want it. It needs `data/processed/elo_history.csv` from the previous
> command and spends one API-Football call. Only not-started fixtures are marked `eligible`, so refreshing
> after the tournament overwrites the committed historical queue (72 fixtures, 28 of them `eligible` when
> it was built) with one in which no fixture is eligible.
> `git restore data/reference/future_2026_prospective_queue.csv` undoes it.

Confirm both CSVs exist before starting the collector.

---

## 5. Start the Shadow Collector

**Test one cycle first** (no odds spend and no prediction writes; it only updates the heartbeat/state files
under `outputs/live_shadow/`):
```bash
python scripts/windows/shadow_collector_cycle.py --dry-run
```
Then a real cycle (writes heartbeat/state, may spend 1 odds credit if a window is due):
```bash
python scripts/windows/shadow_collector_cycle.py
```

Each cycle checks the safety flags first: it halts with exit code 3 unless
`KALSHI_ENABLE_LIVE_TRADING=false` and `TRADING_MODE=paper` are both set. An unset variable counts as
unsafe, so the cycle also halts when `.env` is missing. With the flags set, and past the hard end (default
`2026-07-05T00:00:00Z`), both commands print `stopped: past hard-end`, write `stopped_hard_end` to the
heartbeat/state files, and do nothing else.

**Install the durable 5-min task (Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_shadow_collector_task.ps1
# optional params: -IntervalMinutes 5 -HardEndUtc "2026-07-05T00:00:00Z"
```
The installer sizes the task's repetition window as `HardEndUtc` minus the current time. With the default
hard end now in the past that window is negative, so installing the task today serves no purpose. The
command is kept as a record of how the collector was scheduled in June 2026.

- Heartbeat/state/budget: `outputs/live_shadow/collector_heartbeat.json`, `collector_state.json`, `odds_budget.json`
- Frozen predictions: `outputs/research/live_2026_shadow_predictions.csv` (immutable, append-only)
- **Stop:** `powershell -File scripts\windows\uninstall_shadow_collector_task.ps1`
  (or `Disable-ScheduledTask -TaskName WorldCupShadowCollector`)

Full operating detail: [`docs/PROSPECTIVE_COLLECTION_RUNBOOK.md`](docs/PROSPECTIVE_COLLECTION_RUNBOOK.md),
[`docs/WINDOWS_SCHEDULER_SETUP.md`](docs/WINDOWS_SCHEDULER_SETUP.md).

---

## 6. Start the Prospective Score Harvester

The harvester reads the collector's prediction ledger
(`outputs/research/live_2026_shadow_predictions.csv`). That file is a gitignored runtime artifact, so the
harvester cannot run in a clone where the collector never ran: the runner fails with `FileNotFoundError`
on the missing ledger.

**Run one cycle** (refresh final results if needed + score, append-only):
```bash
python scripts/run_prospective_score_harvester.py
```
Or run the pipeline phase-by-phase (handy for inspection):
```bash
python scripts/refresh_prospective_final_results.py        # verified-final results (no Odds API)
python scripts/audit_prospective_result_reconciliation.py  # reconciliation audit (must be all_ok)
python scripts/select_primary_prospective_snapshots.py     # one snapshot per fixture (pre-specified, outcome-independent rule)
python scripts/prospective_score_harvester_v1.py           # idempotent, append-only scoring
python scripts/prospective_benchmark_v1.py                 # B1 vs no-vig market vs blends + decision ledger
```

The snapshot-selection rule is written down in
[`notes/research/prospective_score_harvest_preregistration.md`](notes/research/prospective_score_harvest_preregistration.md).
It was locked on 2026-06-29, after the matches were played but, per the file's own statement, before any
model-vs-outcome metric was computed. That ordering is self-attested (in-repo), not externally registered.

> [!WARNING]
> `prospective_benchmark_v1.py` **rewrites tracked files**: the three reports listed below and the decision
> ledger. A rewrite would also drop the early-line caveat banners that were added to those reports on
> 2026-09-20. After a replay, check `git status` and `git diff` before committing anything.

**Install the durable 15-min task + watchdog (Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_prospective_score_harvester_tasks.ps1
```
- Outputs: `outputs/live_shadow/scoring_v1/` (scorecards, metrics, integrity audit, heartbeat/state/log)
- Reports (all in `notes/research/`):
  [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md),
  [`PROSPECTIVE_MARKET_BENCHMARK_V1.md`](notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md),
  [`PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md`](notes/research/PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md)
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
The committed human-readable benchmark is in the three `notes/research/PROSPECTIVE_*_V1.md` reports named
in step 6, with the completion report
[`PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md`](notes/research/PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md).

In short: on 34 scored group fixtures (the lab's own "exploratory" sample-size tier) there is no
evidence at this sample size that B1 or any blend differs from the no-vig market, in either direction.
None of the paired 95% bootstrap intervals excludes zero. That market was an early line rather than a
closing line ([ERRATA E2](docs/ERRATA.md)). Nothing was promoted. The [`README.md`](README.md) has the
numbers and caveats.

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

- **Paper-only.** `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. Neither process imports any
  trading code, and the collector halts (exit code 3) unless those two flags are set as shipped. The
  repository does contain a dormant, triple-gated paper/demo execution scaffold
  (`src/wcdrawlab/trading/`). It was never armed, never given credentials, and no order was ever placed.
  All results are forecast-quality metrics, never profit and loss. See
  [`docs/TOOLKIT_USAGE.md`](docs/TOOLKIT_USAGE.md#trade-check-and-trade-submit).
- **Research-only.** Neither process uses a 2026 result to fit, calibrate, retrain, or select a model, and
  market odds are a read-only benchmark here, never a feature or target. This statement is about these two
  processes. Elsewhere in the research, an in-play model choice that had been made after looking at 2026
  results was caught by the lab and relabelled `invalid_due_to_model_selection_on_test_set`; the
  [`README.md`](README.md) describes it.
- **B1** (ternary-Elo, r=0.4) is the only runtime-approved pre-match model. M1–M5 (the pre-match shadow
  set: B1, the no-vig market `M2_market`, and three fixed B1/market blends) and `m2_frozen` (the frozen
  in-play M2; never scored prospectively, and a different model from `M2_market`) are research/shadow
  only. Nothing here promotes a model — see
  [`configs/approved_models.yaml`](configs/approved_models.yaml) (the registry),
  [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) and, for the colliding model names,
  [`docs/GLOSSARY.md`](docs/GLOSSARY.md). One caution: `approved_models.yaml` is governance-protected and
  still quotes a stale V8-vs-B1 figure; [`docs/ERRATA.md`](docs/ERRATA.md) E1 has the correction.
- Immutable, first-write-wins ledgers; frozen predictions are never rewritten or backfilled after kickoff.
  The cost of that rule is visible in ERRATA E2: the odds snapshots the freezer missed were not back-filled.

## Repository map

```text
scripts/                         entry points (collector cycle, builders, harvester pipeline)
scripts/windows/                 PowerShell wrappers + scheduled-task install/uninstall
scripts/prospective_harvest/     harvester internals (Phase 0 freeze, shared helpers)
src/wcdrawlab/                   library (ratings, evaluation, ingest, operations adapters)
data/                            processed/reference inputs (processed/raw gitignored and built in step 4; data/reference tracked)
outputs/                         runtime artifacts (gitignored): collector state, scoring_v1/
notes/research/                  reports, audits, decision ledgers, durable state files
docs/                            detailed runbooks, policies, account/API setup
tests/                           deterministic test suite
```
