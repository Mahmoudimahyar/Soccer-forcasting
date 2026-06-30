# World Cup Draw Model Lab

A runnable Python project for testing World Cup group-stage draw-prediction ideas with real-data hooks, strict time-safety, draw-specific calibration, market residuals, and a 2026-style group-state simulator.

This is a **testing lab**, not a black-box betting bot. Every idea must survive backtesting and calibration checks before it is trusted.

## ▶ Operating the live processes — start here

To clone and run the two background processes (the **Shadow Collector** and the **Prospective Score
Harvester**), follow **[`QUICKSTART.md`](QUICKSTART.md)** — env setup, secrets, one-time data bootstrap,
starting/stopping each process, and reading results, end to end. Harvester deep dive:
[`docs/SCORE_HARVEST_GUIDE.md`](docs/SCORE_HARVEST_GUIDE.md). Everything is **paper-only and research-only**.

## What is now built

- public-data downloader/registry for open datasets
- flexible World Cup match normalizer
- partial 2026 seed snapshot with source labels
- time-safe Elo/FIFA/odds joins
- historical truth-table generator
- Elo/FIFA/market baselines
- ternary-Elo and Gaussian draw baselines
- independent Poisson scoreline model with Dixon-Coles-style low-score correction and diagonal inflation option
- draw-only calibration layer
- no-vig market conversion and edge scan
- group-stage simulator with best-third-place qualification support
- mutual draw utility / must-win pressure calculator
- low-block, schedule-adjusted group-state, and travel/fatigue feature modules
- walk-forward backtest CLI
- ablation scaffold

## Philosophy

Do **not** hard-code these claims:

- “Matchday 3 always has more draws.”
- “A group cannot have more than two draws.”
- “Books systematically underprice draws.”
- “Two previous draws means the next match is less likely to draw.”

Encode them as features and test whether they improve out-of-sample probability quality.


## Claude Code setup

For the final Claude Code handoff, start here:

```text
START_HERE_CLAUDE_CODE.md
docs/CLAUDE_CODE_MASTER_PROMPT.md
docs/ACCOUNT_AND_API_SETUP.md
```

The master prompt defines the safe `.env` audit, free-data bootstrap, leakage-safe
2018/2022/2026 protocol, bounded autoresearch loop, data-request workflow, and the
separation between research and live trading.

## Documentation

The reasoning and statistical design are documented in `docs/`:

```text
docs/README.md
docs/PROBABILITY_AND_STATISTICAL_REASONING.md
docs/MODEL_ARCHITECTURE.md
docs/RISK_AND_UNCERTAINTY.md
docs/DATA_CONTRACTS_AND_LEAKAGE.md
docs/ABLATION_AND_TESTING_PLAN.md
docs/BETTING_RISK_POLICY.md
docs/MODEL_CARD.md
```

Start with `docs/PROBABILITY_AND_STATISTICAL_REASONING.md` and `docs/RISK_AND_UNCERTAINTY.md`.

## Prediction risk / standard deviation outputs

Every prediction row now reports uncertainty, not just probabilities.

Outcome randomness columns:

```text
outcome_var_a, outcome_sd_a
outcome_var_draw, outcome_sd_draw
outcome_var_b, outcome_sd_b
```

Probability-estimate uncertainty columns:

```text
prob_se_a, prob_ci_low_a, prob_ci_high_a
prob_se_draw, prob_ci_low_draw, prob_ci_high_draw
prob_se_b, prob_ci_low_b, prob_ci_high_b
```

Overall uncertainty columns:

```text
prediction_entropy
confidence_score
max_outcome_prob
risk_band
```

For draw edge scans, `edges.csv` also reports bet-risk columns:

```text
draw_bet_ev_per_unit
draw_bet_var_per_unit
draw_bet_sd_per_unit
draw_bet_sharpe_like
```

The key distinction is explained in `docs/RISK_AND_UNCERTAINTY.md`: `outcome_sd_draw = sqrt(p_draw * (1-p_draw))` is the natural one-match volatility, while `prob_se_draw` is an approximate standard error of the probability estimate.

## Install

```bash
cd worldcup_draw_model_lab
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Run tests

```bash
pytest -q
```

## Run the synthetic demo

```bash
python examples/run_demo.py
```

## Run the included partial 2026 seed snapshot

The seed snapshot exists so the full real-data path runs immediately. It is **not betting-grade**. The match rows are source-labeled and the ratings/odds are demo placeholders unless replaced.

```bash
python examples/run_seed_2026.py
```

or through the CLI:

```bash
python -m wcdrawlab.cli seed-2026-features --output outputs/seed_2026_features.csv
python -m wcdrawlab.cli backtest \
  --matches data/seed/worldcup_2026_seed_matches.csv \
  --elo data/seed/seed_ratings_2026.csv \
  --odds data/seed/sample_odds_2026.csv \
  --test-start 2026-06-16 \
  --output outputs/seed_backtest
```

## Fetch public data

```bash
python examples/fetch_public_data.py
```

This writes `data/source_registry.json` and attempts to download configured public sources into `data/raw/`.

Equivalent CLI:

```bash
python -m wcdrawlab.cli sources --output data/source_registry.json
python -m wcdrawlab.cli fetch-public
```

Current registry entries:

- `international_results`: general international results from martj42/international_results.
- `jf_worldcup_matches`: structured World Cup match data from jfjelstul/worldcup.
- `jf_worldcup_tournaments`: tournament metadata from jfjelstul/worldcup.

Upstream datasets can change paths/columns. The normalizers fail loudly and tell you which columns could not be inferred.

## Build historical truth tables

After fetching the structured World Cup match data:

```bash
python examples/build_truth_tables.py
```

or:

```bash
python -m wcdrawlab.cli truth-tables \
  --matches data/raw/jf_worldcup_matches.csv \
  --format jf-worldcup \
  --group-stage-only \
  --year-min 1998 \
  --year-max 2022 \
  --output outputs/truth_tables
```

Outputs:

```text
draw_rate_by_tournament.csv
draw_rate_by_matchday.csv
draws_per_group.csv
draws_per_group_distribution.csv
conditional_by_prior_group_draws.csv
binomial_p_024.csv
binomial_p_247.csv
```

These tables are where the folklore gets killed. Do not trust chatbot draw-rate claims until these are computed from your selected dataset.

## Real data files to add or replace

Create or replace these under `data/raw/`:

```text
matches.csv
ratings_elo.csv
ratings_fifa.csv
odds.csv
venues.csv
squads.csv  # optional
```

Schemas are in `schemas/*.yaml`.

Minimum `matches.csv`:

```csv
match_id,kickoff_utc,tournament,stage,group,matchday,team_a,team_b,goals_a,goals_b,venue,neutral
```

Minimum `ratings_elo.csv`:

```csv
team,rating_date,elo
```

Minimum `ratings_fifa.csv`:

```csv
team,release_date,fifa_rank,fifa_points
```

Minimum `odds.csv`:

```csv
match_id,snapshot_time,book,odds_a,odds_draw,odds_b
```

Rules:

```text
rating_date <= kickoff_utc
release_date <= kickoff_utc
odds_snapshot_time <= kickoff_utc
```

No future data. No post-kickoff odds. No post-match rankings.

## Run a real backtest

```bash
python -m wcdrawlab.cli backtest \
  --matches data/raw/matches.csv \
  --elo data/raw/ratings_elo.csv \
  --fifa data/raw/ratings_fifa.csv \
  --odds data/raw/odds.csv \
  --test-start 2018-06-14 \
  --output outputs/backtest_2018
```

## Evaluation metrics

Primary:

- log loss
- Ranked Probability Score
- Brier score for draw probability
- draw calibration error

Betting-specific:

- no-vig edge
- fair odds
- closing-line value
- ROI by edge bucket
- drawdown
- fractional Kelly exposure

## Suggested pass/fail rules

A module survives only if it improves at least one of:

```text
ΔRPS >= 0.002
ΔLogLoss >= 0.005
Draw calibration error improvement >= 0.02
Positive CLV in historical backtest
Positive ROI after vig under realistic odds timing
```

## Directory structure

```text
worldcup_draw_model_lab/
  README.md
  docs/
    PROBABILITY_AND_STATISTICAL_REASONING.md
    MODEL_ARCHITECTURE.md
    RISK_AND_UNCERTAINTY.md
    DATA_CONTRACTS_AND_LEAKAGE.md
    ABLATION_AND_TESTING_PLAN.md
    BETTING_RISK_POLICY.md
    MODEL_CARD.md
  requirements.txt
  pyproject.toml
  configs/default.yaml
  data/seed/
    worldcup_2026_seed_matches.csv
    seed_ratings_2026.csv
    sample_odds_2026.csv
  schemas/*.yaml
  src/wcdrawlab/
    cli.py
    ingest.py
    pipeline.py
    truth.py
    data.py
    features.py
    ratings.py
    evaluation.py
    risk.py
    market.py
    calibration.py
    models/
      baselines.py
      scoreline.py
    simulation/
      standings.py
      group_simulator.py
      utility.py
    ablation.py
  examples/
    fetch_public_data.py
    build_truth_tables.py
    run_seed_2026.py
    run_demo.py
  tests/test_core.py
```

## Important limitation

The included 2026 seed data is a partial snapshot assembled for pipeline testing. Use it to verify the system, not to place bets. Replace seed ratings/odds/results with live, timestamped sources before running any edge scan.


## Live after-game updates

The model is designed to update **after each completed game**. Use:

```bash
wcdrawlab predict-live --matches data/live/current_matches.csv --output outputs/live
```

before games, and after every final score:

```bash
wcdrawlab update-after-match \
  --matches data/live/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --current-matches data/live/current_matches.csv \
  --output outputs/live
```

See `docs/PREDICTION_TARGETS_AND_UPDATE_CADENCE.md` and `docs/AFTER_GAME_UPDATE_WORKFLOW.md` for the complete explanation.


### Live Elo updates

The after-game workflow now updates Elo after every completed match. Initialize once:

```bash
mkdir -p data/live
cp data/seed/worldcup_2026_seed_matches.csv data/live/current_matches.csv
cp data/seed/seed_ratings_2026.csv data/live/current_elo.csv
```

Then after each final score:

```bash
wcdrawlab update-after-match \
  --matches data/live/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --current-matches data/live/current_matches.csv \
  --current-elo data/live/current_elo.csv \
  --output outputs/live
```

This inserts the result, appends updated Elo rows, writes `outputs/live/elo_update_log.csv`, and recomputes remaining match probabilities. See `docs/ELO_UPDATE_SYSTEM.md`.
