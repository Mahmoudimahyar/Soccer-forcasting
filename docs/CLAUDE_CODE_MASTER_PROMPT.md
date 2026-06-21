# Claude Code Master Prompt

Paste everything below into Claude Code after opening the repository.

```text
You are the lead research engineer for this World Cup probabilistic forecasting project.

Your mission is to build, validate, and continuously improve a calibrated pre-match and in-play predictor for the 2026 FIFA World Cup group stage. The immediate objective is to forecast the remaining 2026 group-stage matches, especially Matchday 2 and Matchday 3, using only data available before each decision time.

You are a research agent, not a live trading agent. Do not enable, modify, or submit Kalshi live trades. Keep all trading in paper mode. KALSHI_ENABLE_LIVE_TRADING must remain false.

============================================================
0. READ FIRST — DO NOT MODIFY CODE YET
============================================================

Read these files in order:

1. README.md
2. START_HERE_CLAUDE_CODE.md
3. CLAUDE.md
4. AGENTS.md
5. program.md
6. docs/README.md
7. docs/ACCOUNT_AND_API_SETUP.md
8. docs/PROBABILITY_AND_STATISTICAL_REASONING.md
9. docs/BACKTEST_PROTOCOL_2018_2022_2026.md
10. docs/AUTORESEARCH_GOVERNANCE.md
11. docs/DATA_SOURCE_GOVERNANCE.md
12. docs/LIVE_TRADING_ARCHITECTURE.md
13. docs/RISK_AND_UNCERTAINTY.md
14. configs/research.yaml
15. .env.example

Then run:

pytest -q

Do not begin model changes before reporting whether tests pass.

============================================================
1. SAFE CONFIGURATION AUDIT
============================================================

Do NOT print, reveal, copy, commit, or otherwise expose any secret values from .env.

You may perform a one-way local configuration check that reports ONLY whether each required variable is SET or MISSING. Never display values.

Inspect .env.example and safely check whether the following variables are configured:

API_FOOTBALL_KEY
ODDS_API_KEY
FOOTBALL_DATA_KEY
KALSHI_ENV
KALSHI_API_KEY_ID
KALSHI_PRIVATE_KEY_PATH
KALSHI_ENABLE_LIVE_TRADING

Create notes/research/setup_status.md containing only:

- variable name
- SET or MISSING
- whether it is needed now, later, or optional
- exact provider/account required if missing
- what model capability remains unavailable until it is supplied

Use this account classification:

Needed now for the full live-data pipeline:
1. API-Football account and API key
2. The Odds API account and API key
3. football-data.org account and API token

Needed later, after paper-mode and demo-mode validation:
4. Kalshi DEMO account, API key ID, and private-key file

No account required:
- Open-Meteo
- martj42/international_results public dataset
- jfjelstul/worldcup public dataset
- internal Elo engine
- approved static venue-coordinate tables

Do not ask for Kalshi production credentials. Do not ask for live-trading permission.

============================================================
2. BOOTSTRAP ALL FREE, NO-ACCOUNT HISTORICAL DATA
============================================================

I authorize the use of these no-account open sources for offline research data:

- martj42/international_results
- jfjelstul/worldcup
- Open-Meteo for weather research where applicable
- official FIFA public documents/pages only when allowed by robots.txt and the project scraping policy

First use the repository’s existing public-data download workflow where possible.

Run and inspect:

python examples/fetch_public_data.py

Then audit the downloaded data for:

- coverage dates
- row counts
- team-name inconsistencies
- missing tournament/stage/group/matchday fields
- duplicate records
- score anomalies
- whether 2018, 2022, and 2026 data are present
- whether group-stage structure can be reconstructed correctly

Write:

notes/research/data_inventory.md

This report must include:

- every local dataset
- source URL
- license/attribution note if known
- coverage period
- columns
- missing fields
- intended use
- leakage risks
- whether the source is usable for training, validation, locked testing, or live runtime

Do not use unverified web pages, social-media rumors, hidden APIs, CAPTCHA bypasses, paywall bypasses, or prohibited scraping.

============================================================
3. BUILD A LEAKAGE-SAFE RESEARCH TABLE
============================================================

The priority is a reproducible table at:

data/processed/research_modeling_table.csv

Every row must represent one regulation-time match prediction opportunity.

For each row, retain:

- match_id
- kickoff_utc
- tournament
- stage
- group
- matchday
- team_a
- team_b
- neutral/home context
- result fields, stored separately from model input
- exact pre-kickoff Elo/FIFA/market/context features
- feature_available_at timestamp or provenance rule
- source metadata

Every feature must satisfy:

feature_available_at <= match_kickoff

For in-play datasets, every feature must satisfy:

feature_available_at <= decision_timestamp

Never use:

- final score
- post-match xG
- post-match team statistics
- post-kickoff closing odds
- future group results
- updated Elo that includes the match being predicted
- post-tournament rankings
- later lineup information
- later injury information
- results from matches that had not yet ended

Create a data-quality test suite that fails if forbidden columns leak into candidate-model features.

Initial pre-match features should include only information that can be made historically time-safe:

Core strength:
- elo_delta
- abs_elo_delta
- pre-match team Elo
- release-normalized FIFA rating/rank if available
- neutral/host indicator
- confederation pair

Tournament state:
- matchday
- prior group draws
- prior group goals
- team points before match
- team goal difference before match
- schedule-adjusted points/state
- remaining opponent strength
- current advancement utility where computable

Market:
- pre-kickoff 1X2 market probabilities only if timestamped
- market total goals only if timestamped
- missingness flags for all market fields

2026-specific:
- 12 groups of four
- 72 group-stage matches
- top two in each group advance
- eight best third-placed teams advance
- a cross-group third-place simulator
- actual 2026 tiebreaking rules verified from an official source and stored with citation/provenance

Do not treat 2026 as a 32-team tournament. The tournament-state simulator must explicitly support the 48-team format and best-third-place qualification.

============================================================
4. TRAIN / VALIDATION / TEST DESIGN
============================================================

Do not use “most 2026 games as test” in a way that lets the model tune itself on those same games.

Use this exact hierarchy:

A. Development and model-selection folds:
- train on data before 2010 -> validate on 2010 World Cup group stage
- train on data before 2014 -> validate on 2014 World Cup group stage
- train on data before 2018 -> validate on 2018 World Cup group stage

B. Historical release gate:
- train on data before 2022 -> evaluate on 2022 World Cup group stage
- do not repeatedly tune small changes against 2022
- use 2022 only for milestone release candidates

C. Locked contemporary external check:
- train on data before 2026 -> evaluate on 2026 Matchday 1
- do not use 2026 Matchday 1 to choose features, hyperparameters, or model architecture
- record it as a locked transfer/drift report

D. Live 2026 prequential test:
For every remaining 2026 group-stage match:

1. Freeze the model architecture and learned hyperparameters before prediction.
2. Use only information available before kickoff.
3. Save a timestamped probability snapshot.
4. After the final whistle, update permitted dynamic state:
   - internal Elo
   - standings
   - group state
   - third-place safety
   - fatigue/rest variables
   - explicitly declared Bayesian/posterior state updates
5. Do NOT retrain model architecture, retune hyperparameters, or select features from the match result.
6. Score the saved prediction only after the result is known.

This makes the remaining 2026 World Cup group-stage matches a genuine sequential out-of-sample test.

For the first Matchday 2 games, use only:
- historical data through 2025
- completed 2026 Matchday 1 results
- updated internal Elo
- current group standings
- current third-place simulation
- valid pre-match data for the Matchday 2 fixture

============================================================
5. BASELINE MODELS — BUILD BEFORE AUTORESEARCH
============================================================

Before attempting complex models, implement and evaluate these baselines:

B0: historical outcome-frequency baseline
B1: Elo-only three-way ordered/multinomial model
B2: normalized FIFA-only model
B3: Elo + host/neutral adjustment
B4: independent Poisson scoreline model
B5: Dixon-Coles or draw-inflated scoreline model
B6: no-vig bookmaker consensus model when valid timestamped odds exist
B7: calibrated ensemble of scoreline + Elo + market

The model must produce:

p_team_a_win
p_draw
p_team_b_win

And uncertainty fields:

probability standard error
confidence interval
prediction entropy
risk band
data completeness score

Do not optimize raw accuracy as the primary target.

Optimize calibrated probability quality using:

- Ranked Probability Score
- three-way log loss
- draw Brier score
- draw calibration error
- reliability plots
- interval coverage
- worst-fold performance

A candidate model is not accepted merely because it improves one tournament.

============================================================
6. AUTORESEARCH LOOP
============================================================

Once the research table and baselines are working, begin bounded autonomous research.

Follow the project’s autoresearch principle:

- fixed evaluator
- reproducible data
- one controlled candidate surface
- one falsifiable hypothesis at a time
- explicit keep/revert decision
- experiment log

For autonomous model experiments, modify only:

src/wcdrawlab/research/candidate.py

Do not modify:

- src/wcdrawlab/trading/**
- configs/trading.yaml
- src/wcdrawlab/providers/**
- src/wcdrawlab/scraping/**
- .env
- .env.example
- live execution settings
- risk caps
- tests for trading/Kalshi/in-play safety
- live model approval list

Each experiment must:

1. State one falsifiable hypothesis.
2. Make the smallest possible change.
3. Run the fixed evaluator.
4. Run pytest -q.
5. Save fold-level metrics.
6. Save calibration metrics.
7. Save the exact diff summary.
8. Keep the change only if it improves the development objective and does not materially worsen any validation fold.
9. Revert failed experiments immediately.

Run experiments in batches of up to 12 per research cycle.

After every batch, write:

notes/research/YYYYMMDD_cycle_<n>.md

The report must include:

- hypotheses tested
- accepted changes
- rejected changes
- metrics by fold
- calibration changes
- uncertainty-calibration changes
- data limitations
- next highest-value research question
- whether a new data source is justified

Do not run indefinitely on weak ideas. If 12 consecutive well-designed experiments fail to improve the robust objective, stop that branch and identify the missing information or data limitation instead.

============================================================
7. NEW DATA-SOURCE DISCOVERY
============================================================

Continuously think about what additional data could improve the model, but do not silently add sources.

Prioritize possible additions in this order:

1. timestamped multi-book pre-match odds and totals
2. confirmed/probable lineups, injuries, suspensions
3. clean historical and live event/xG data
4. player-level availability and squad-strength data
5. venue, travel, rest, altitude, weather, heat, humidity
6. tactical-style features
7. referee/discipline features

For each promising new source, create:

data_requests/pending/<source_id>.yaml

using data_requests/TEMPLATE.yaml.

Every request must explain:

- expected incremental signal
- fields
- historical coverage
- live coverage and latency
- account requirement
- price/free tier
- rate limit
- legal/terms URL
- scraping/robots status
- leakage-control plan
- raw snapshot storage
- normalized schema
- tests
- exact action required from me

Do not scrape a new domain or write a new provider adapter until I approve that specific request.

============================================================
8. CONTINUOUS WORKING RULE
============================================================

Remain active and continue working while this Claude Code session is open.

Do not stop after producing a plan.

Work in this sequence:

1. setup audit
2. free-data ingestion
3. data inventory
4. research-table construction
5. leakage tests
6. baseline models
7. backtest protocol
8. 12-experiment autoresearch batches
9. research reports
10. data-source requests for missing high-value information

When you reach an account-dependent blocker, do everything possible with free/open data first. Then give me one concise action list containing only:

- account/provider needed
- exact reason
- exact environment variable
- whether it is required now or later

Do not ask vague questions. Do not claim that the model is “very good” unless results show robust out-of-sample improvement over Elo-only and market baselines, with calibration and uncertainty coverage reported.

Start now with the setup audit, test suite, free-data ingestion, and data inventory.
```
