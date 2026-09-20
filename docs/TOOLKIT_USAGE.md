# Toolkit usage (the v0.1 how-to)

> **What this page is.** The repository started (v0.1, June 2026) as a small runnable toolkit for testing
> ideas about World Cup group-stage draws: data normalisers, time-ordered joins, baseline models, a
> walk-forward backtest, a group-stage simulator and a command-line interface. That toolkit still ships. On
> 2026-09-20 the eleven offline subcommands were re-run against the seed and example files: all of them
> work except `predict-live`, which has a known defect (see
> [section 11](#11-after-game-updates-and-elo-updates)). The one network command, `fetch-public`, was not
> re-run. This page preserves the toolkit's how-to, which used to be the root README, with the stale
> details corrected.
>
> **What this page is not.** It is not the project overview or the results (see the
> [root README](../README.md)), and it is not the guide to the 2026 prospective evaluation pipeline (see
> [`QUICKSTART.md`](../QUICKSTART.md)).
>
> **Not betting advice.** Some toolkit outputs use betting vocabulary (odds, "edges", Kelly fractions)
> because the v0.1 design imagined a market comparison. The project never evaluated profitability and claims
> none. Every result reported anywhere in this repository is a forecast-quality metric (RPS, log-loss,
> Brier, calibration), never profit and loss. Nothing here is betting or financial advice.

Terms such as RPS, B1 and "no-vig" are defined in [`GLOSSARY.md`](GLOSSARY.md).

## Contents

1. [Install](#1-install)
2. [Run the tests](#2-run-the-tests)
3. [Run the synthetic demo](#3-run-the-synthetic-demo)
4. [Run the included partial 2026 seed snapshot](#4-run-the-included-partial-2026-seed-snapshot)
5. [Fetch public data](#5-fetch-public-data)
6. [Build historical truth tables](#6-build-historical-truth-tables)
7. [Real data files to add or replace](#7-real-data-files-to-add-or-replace)
8. [Run a real backtest](#8-run-a-real-backtest)
9. [Evaluation metrics](#9-evaluation-metrics)
10. [Prediction risk and uncertainty columns](#10-prediction-risk-and-uncertainty-columns)
11. [After-game updates and Elo updates](#11-after-game-updates-and-elo-updates)
12. [CLI reference (all 12 subcommands)](#12-cli-reference-all-12-subcommands)
13. [Example scripts](#13-example-scripts)
14. [Directory notes](#14-directory-notes)
15. [Important limitation of the seed data](#15-important-limitation-of-the-seed-data)

Commands are shown in bash syntax. In PowerShell, put multi-line commands on one line (or replace the
trailing `\` with a backtick).

---

## 1. Install

```bash
git clone https://github.com/Mahmoudimahyar/Soccer-forcasting.git
cd Soccer-forcasting            # or whatever folder name you cloned into
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                # installs the package and the `wcdrawlab` command
```

Python 3.10 or newer is required (3.13 is what the test suite was last run on).

`pip install -e .` matters. The package lives under `src/`, so without it the `wcdrawlab` command does not
exist and `python -m wcdrawlab.cli` cannot find the package. The test suite and most scripts add `src/` to
the import path themselves, which is why they work either way.

`wcdrawlab <subcommand>` and `python -m wcdrawlab.cli <subcommand>` are equivalent once the package is
installed. This page uses both forms.

## 2. Run the tests

```bash
pytest -q
```

Expected on a fresh clone (verified 2026-09-20, Python 3.13, Windows): **817 passed, 51 skipped, 0 failed**.

The 51 skips are integration tests that need gitignored datasets or the author's external event lake. They
are skipped with an explicit reason by `tests/conftest.py`, not hidden; `pytest -q -rs` prints each reason.
See [`TESTING_AND_DATA_DEPENDENCIES.md`](TESTING_AND_DATA_DEPENDENCIES.md).

## 3. Run the synthetic demo

```bash
python examples/run_demo.py
```

This builds a 16-team synthetic tournament in memory, fits the baseline and scoreline models, applies the
draw calibrator, and runs the group simulator. It prints to the terminal and writes no files. Because the
data are synthetic, the printed metrics say nothing about real football; the demo only shows that the parts
connect.

## 4. Run the included partial 2026 seed snapshot

The seed snapshot exists so the full real-data path runs immediately after install. The match rows were
assembled by hand from press reports (the `data_source` and `notes` columns say which). The ratings and
odds in `data/seed/` are **demo placeholders**, and the odds were generated from the placeholder ratings.

Treat this as a smoke test. The backtest below trains on 8 played matches and tests on 10, so the metrics
it prints are not results.

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

`outputs/` is gitignored, so these runs leave the working tree clean.

## 5. Fetch public data

```bash
python examples/fetch_public_data.py
```

This downloads the configured public sources into `data/raw/` (gitignored) and rewrites
`data/source_registry.json`. The registry file is tracked in git; regenerating it writes the same three
entries.

Equivalent CLI:

```bash
python -m wcdrawlab.cli sources --output data/source_registry.json
python -m wcdrawlab.cli fetch-public
```

Current registry entries:

| Name | Upstream | Saved to |
|---|---|---|
| `international_results` | General men's international results from `martj42/international_results` | `data/raw/international_results.csv` |
| `jf_worldcup_matches` | Structured World Cup match data from `jfjelstul/worldcup` | `data/raw/jf_worldcup_matches.csv` |
| `jf_worldcup_tournaments` | Tournament metadata from `jfjelstul/worldcup` | `data/raw/jf_worldcup_tournaments.csv` |

Upstream datasets can change paths or columns. The normalisers fail loudly and name the columns they could
not infer. These datasets belong to their authors and are not redistributed here; see
[`DATA_SOURCES.md`](DATA_SOURCES.md) and [`DATA_SOURCE_GOVERNANCE.md`](DATA_SOURCE_GOVERNANCE.md).

## 6. Build historical truth tables

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

These tables are where draw folklore gets checked against data. The v0.1 design rule was: do **not**
hard-code claims such as "matchday 3 always has more draws", "a group cannot have more than two draws",
"books systematically underprice draws", or "two previous draws make the next one less likely". Encode them
as features and test whether they improve out-of-sample probability quality.

## 7. Real data files to add or replace

Create or replace these under `data/raw/` (gitignored):

```text
matches.csv
ratings_elo.csv
ratings_fifa.csv
odds.csv
venues.csv      # optional
squads.csv      # optional
```

Schemas for the first four are in [`schemas/matches.yaml`](../schemas/matches.yaml),
[`schemas/ratings.yaml`](../schemas/ratings.yaml) and [`schemas/odds.yaml`](../schemas/odds.yaml).

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

Time-ordering rules:

```text
rating_date        <= kickoff_utc
release_date       <= kickoff_utc
odds snapshot_time <= kickoff_utc
```

No future data, no post-kickoff odds, no post-match rankings. The joins are backward-looking as-of joins
that enforce this ordering, and the test suite includes leakage checks. Neither can detect a wrong
timestamp, so it is still your job to supply honest ones. See
[`DATA_CONTRACTS_AND_LEAKAGE.md`](DATA_CONTRACTS_AND_LEAKAGE.md).

## 8. Run a real backtest

```bash
python -m wcdrawlab.cli backtest \
  --matches data/raw/matches.csv \
  --elo data/raw/ratings_elo.csv \
  --fifa data/raw/ratings_fifa.csv \
  --odds data/raw/odds.csv \
  --test-start 2018-06-14 \
  --output outputs/backtest_2018
```

`--elo`, `--fifa` and `--odds` are optional. The command trains on played matches before `--test-start`,
predicts the played matches from that date on, prints a metrics table sorted by RPS, and writes
`metrics.csv` and `predictions.csv` to the output folder. If odds were supplied it also writes `edges.csv`
(see the caveat in section 9).

Six toolkit models are compared: a historical prior, ternary Elo, Gaussian-draw Elo, a multinomial logit,
the Poisson scoreline model, and the scoreline model plus the draw calibrator. The `ternary_elo` row is the
same model family (ternary Elo, draw parameter r = 0.4) that the lab later approved as **B1**.

This walk-forward CLI is the v0.1 toolkit path. The research results in the root README came from a
separate fixed evaluator and research scripts with their own protocols; see
[`BACKTEST_PROTOCOL_2018_2022_2026.md`](BACKTEST_PROTOCOL_2018_2022_2026.md) and
[`AUTORESEARCH_GOVERNANCE.md`](AUTORESEARCH_GOVERNANCE.md).

## 9. Evaluation metrics

**Primary (what the lab actually used, throughout):**

- log loss
- ranked probability score (RPS)
- Brier score for the draw probability
- draw calibration error

Lower is better for all four.

**Betting-specific metrics: historical design intent, never evaluated.** The v0.1 README also listed a
second group:

- no-vig model-minus-market probability difference (called "edge" in the code and in `edges.csv`)
- fair odds
- closing-line value
- ROI by bucket
- drawdown
- fractional Kelly exposure

These were intentions written before any research was run. The toolkit can compute some of the quantities
mechanically (fair odds, the model-minus-market difference, a Kelly fraction in `examples/run_demo.py`). But
no ROI, closing-line-value, drawdown or staking analysis appears anywhere in this repository's results. A
non-zero number in `edges.csv` is a difference between two probability estimates, not evidence of an
advantage. The project never evaluated profitability and claims none.

### Historical design-time pass/fail rules

The v0.1 README suggested that a module "survives" only if it improves at least one of:

```text
ΔRPS >= 0.002
ΔLogLoss >= 0.005
Draw calibration error improvement >= 0.02
Positive CLV in historical backtest
Positive ROI after vig under realistic odds timing
```

Read this as a record of early intent, not as the rule the research followed. What was actually used is a
written gate: a fixed evaluator with a composite objective (weights 0.40 RPS, 0.25 log-loss, 0.20
draw-Brier, 0.15 draw-calibration error), a pre-set promotion threshold of 0.002
(`minimum_relative_improvement` in [`configs/research.yaml`](../configs/research.yaml)), and paired-bootstrap
confidence intervals. The last two conditions in the list (CLV and ROI) were never evaluated.

## 10. Prediction risk and uncertainty columns

Every prediction row reports uncertainty, not just probabilities.

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

The key distinction is explained in [`RISK_AND_UNCERTAINTY.md`](RISK_AND_UNCERTAINTY.md):
`outcome_sd_draw = sqrt(p_draw * (1 - p_draw))` is the natural one-match volatility, while `prob_se_draw` is
an *approximate* standard error of the probability estimate, based on an assumed effective sample size
(in `backtest`, the training-set size clamped to 30–400; in the live commands, `--risk-n-eff`, default 120).
It is a heuristic, not a calibrated interval.

When odds are supplied, `edges.csv` and `draw_edges.csv` also carry a boolean `bet_draw` flag and four
hypothetical per-unit columns:

```text
draw_bet_ev_per_unit
draw_bet_var_per_unit
draw_bet_sd_per_unit
draw_bet_sharpe_like
```

`bet_draw` is a mechanical threshold on the model-minus-market difference, not a recommendation. The four
columns are arithmetic on the model's own draw probability and the quoted odds. They assume the model
probability is correct. No evaluation in this repository supports that assumption.

The 2026 prospective benchmark scored 34 fixtures (the lab's own "exploratory" sample-size tier) against an
early-line market comparator, not a closing line (see [`ERRATA.md`](ERRATA.md) E2). It gave no evidence at
that sample size that any model differs from the no-vig market: none of the paired 95% intervals excludes
zero. The v0.1 live blend described in section 11 has no out-of-sample record at all. The columns are kept
for transparency about what the v0.1 code does, not as a signal.

## 11. After-game updates and Elo updates

The toolkit can re-predict all remaining group matches after each completed game. Before games:

```bash
wcdrawlab predict-live --output outputs/live
```

With no arguments this reads the seed files in `data/seed/` and writes `features_current.csv`,
`predictions_remaining.csv`, `advancement_probabilities.csv`, `prediction_targets.json` and (if odds are
present) `draw_edges.csv` into `outputs/live/`.

> [!NOTE]
> **Fixed 2026-09-20.** Until this release `predict-live` wrote those files and then exited with
> `NameError: name 'updated_elo' is not defined` — a leftover block at the end of
> `run_live_prediction_refresh()` in `src/wcdrawlab/live.py`. The test suite imported that function but
> never called it, so nothing caught it. It is fixed and now covered by
> `tests/test_live_update.py::test_run_live_prediction_refresh_writes_outputs_and_returns`.

Be clear about which model this is. The probabilities come from a v0.1 fallback blend with hand-set weights
(0.45 ternary Elo, 0.20 Gaussian-draw Elo, 0.35 no-vig market; when a match has no odds the market term
becomes a uniform placeholder at weight 0.10 and the weights are renormalised). A draw adjustment from the
simulated group state follows, capped at 0.10 in either direction. The code itself calls this a "safe live
fallback".

It is **not** the governed runtime forecaster (`src/wcdrawlab/runtime/`, which serves only the approved
model B1 and fails closed for anything else), and it is not one of the models scored in the 2026
prospective benchmark. Only the CLI, one example script and the unit tests call it; no evaluation script
does, so it has no out-of-sample record.

> [!WARNING]
> **The old instructions modify tracked files.** `data/live/current_matches.csv` and
> `data/live/current_elo.csv` are **tracked in git** (committed as byte-identical copies of the seed files).
> The v0.1 README told you to `cp data/seed/... data/live/current_matches.csv` and then run
> `update-after-match` against those paths. The copy overwrites tracked files, and every
> `update-after-match` or `update-elo` run then edits them, so `git status` shows changes you did not mean
> to make. The same is true of the **default** values of `--current-matches` and `--current-elo`, and of
> `examples/run_after_match_update.py`. Use a scratch folder under `outputs/` instead, as below. If you
> already modified the tracked files, `git restore data/live/` puts them back.

Initialise a scratch state once:

```bash
mkdir -p outputs/live_state
cp data/seed/worldcup_2026_seed_matches.csv outputs/live_state/current_matches.csv
cp data/seed/seed_ratings_2026.csv          outputs/live_state/current_elo.csv
```

Then after each final score:

```bash
wcdrawlab update-after-match \
  --matches outputs/live_state/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --current-matches outputs/live_state/current_matches.csv \
  --current-elo outputs/live_state/current_elo.csv \
  --output outputs/live
```

This inserts the result, appends post-match Elo rows to the current Elo table, writes
`outputs/live/update_log.csv` and `outputs/live/elo_update_log.csv`, and recomputes the remaining match
probabilities and advancement probabilities (`features_after_update.csv`, `predictions_remaining.csv`,
`advancement_probabilities.csv` and, if odds are present, `draw_edges.csv`).

Pass `--no-update-elo` to skip the Elo step. Elo options: `--elo-k` (default 60), `--elo-scale` (400),
`--elo-home-advantage` (0), `--no-elo-round-change`.

To update Elo only, without refreshing predictions:

```bash
wcdrawlab update-elo \
  --matches outputs/live_state/current_matches.csv \
  --elo outputs/live_state/current_elo.csv \
  --output outputs/live_state/current_elo.csv \
  --audit outputs/live/elo_update_log.csv \
  --match-id 2026_A_03 --goals-a 1 --goals-b 1
```

Background: [`PREDICTION_TARGETS_AND_UPDATE_CADENCE.md`](PREDICTION_TARGETS_AND_UPDATE_CADENCE.md),
[`AFTER_GAME_UPDATE_WORKFLOW.md`](AFTER_GAME_UPDATE_WORKFLOW.md) and
[`ELO_UPDATE_SYSTEM.md`](ELO_UPDATE_SYSTEM.md).

This manual workflow is the v0.1 toolkit. The 2026 prospective evaluation did **not** use it; it used the
scheduled collector and harvester described in [`QUICKSTART.md`](../QUICKSTART.md).

## 12. CLI reference (all 12 subcommands)

The list below was read from [`src/wcdrawlab/cli.py`](../src/wcdrawlab/cli.py). Run
`wcdrawlab <subcommand> --help` for every flag.

| Subcommand | What it does | Network? | Writes |
|---|---|---|---|
| `sources` | Write the public source registry to JSON | no | `data/source_registry.json` (tracked; same content) |
| `fetch-public` | Download the configured public datasets (`--names a,b`, `--overwrite`) | **yes** (GitHub raw files) | `data/raw/` (gitignored) |
| `truth-tables` | Build draw-rate truth tables from match data | no | `outputs/truth_tables/` |
| `backtest` | Walk-forward backtest from a matches file plus optional Elo, FIFA and odds files | no | `--output` folder |
| `seed-2026-features` | Build the feature table from the partial 2026 seed snapshot | no | `outputs/seed_2026_features.csv` |
| `predict-live` | Re-predict all remaining matches from the current match table. (A `NameError` on exit was fixed 2026-09-20; see section 11) | no | `outputs/live/` |
| `update-after-match` | Insert a final result, update Elo, then refresh standings, utilities and predictions | no | `--output` folder, plus `--current-matches` and `--current-elo` (**defaults are tracked files**, see section 11) |
| `update-elo` | Append post-match Elo rows for one completed match, without refreshing predictions | no | `--output` Elo table (**default is a tracked file**) and `--audit` log |
| `inplay` | Compute in-play win/draw/loss probabilities from pre-game expected goals and the current match state | no | nothing (prints) |
| `validate-source` | Check a URL against the scraping allowlist | no | nothing (prints or raises) |
| `trade-check` | Evaluate a sample order intent against the deterministic risk gate | no | nothing (prints) |
| `trade-submit` | Paper/demo-gated submission path; in the shipped configuration it never contacts an exchange | no, as shipped | nothing (prints JSON) |

The original README documented only the first seven. The last five are described below.

### `update-elo`

See section 11.

### `inplay`

```bash
wcdrawlab inplay --lambda-a 1.45 --lambda-b 0.95 --minute 67 --goals-a 0 --goals-b 1
```

You supply the pre-game expected goals for each team (`--lambda-a`, `--lambda-b`) and the match state
(minute, score, optional red cards and xG). The engine scales the remaining expected goals by time left,
applies fixed score-state and red-card adjustments, and sums a Poisson grid to get win/draw/loss for the
regulation result. It prints the probabilities, the remaining expected goals, an approximate draw standard
error with its interval, and the entropy. That standard error rests on an assumed effective sample size,
like the one in section 10. It is a heuristic, not a calibrated interval.

The adjustment constants are hand-set research parameters, not fitted values. The same engine sits under
the research reference model **in-play M2** (remaining-time Poisson; unfitted, with hand-set constants).
That is a different model from the pre-match shadow comparator `M2_market`; the colliding names are
untangled in [`GLOSSARY.md`](GLOSSARY.md). In-play results, including the many nulls, are summarised in the
[root README](../README.md).

### `validate-source`

```bash
wcdrawlab validate-source --url https://www.fifa.com/en/tournaments
```

Prints an approval line if the URL's domain is in
[`configs/scraping_allowlist.yaml`](../configs/scraping_allowlist.yaml); otherwise raises
`ScrapePolicyError`. It makes no network request. The allowlist is a project policy, not a legal
determination; see [`DATA_SOURCE_GOVERNANCE.md`](DATA_SOURCE_GOVERNANCE.md).

### `trade-check` and `trade-submit`

These two subcommands front a **dormant, triple-gated paper/demo execution scaffold**
(`src/wcdrawlab/trading/`). It was never armed, never given credentials, and no order was ever placed. It
is documented here because it exists in the code, not because the project used it.

```bash
wcdrawlab trade-check \
  --intent data/live/example_trade_intent.json \
  --quote  data/live/example_market_quote.json \
  --state  data/live/example_portfolio_state.json \
  --confidence-score 0.72
```

`trade-check` loads the policy from [`configs/trading.yaml`](../configs/trading.yaml) and runs a
deterministic risk gate over a local JSON order intent, a local market quote and a local portfolio state:
price and size limits, exposure and daily-loss caps, a minimum model-minus-market margin after uncertainty,
a confidence floor, spread and staleness limits, and a model-version check against a list supplied in the
portfolio-state JSON. It prints
`approved: True/False` with reasons. It sends nothing. With the shipped example files it prints
`approved: False` because the example timestamps are stale, which is the gate working as intended.

`trade-submit` runs the same gate first and then:

- If the gate rejects, it returns `"submitted": false` with the reasons.
- If `mode: paper` (the shipped value in `configs/trading.yaml`), it returns `"submitted": false,
  "approved": true, "mode": "paper"` and never constructs an exchange client.
- Only if someone changed the locked policy to `demo` or `live` would it construct the Kalshi client. The
  production order path then raises unless all three hold: `require_live` is set, the environment variable
  `KALSHI_ENABLE_LIVE_TRADING=true`, and an exact acknowledgement string is present in the environment. No
  credentials ship with the repository, and the project's own status notes record "Kalshi: credentials
  MISSING" (`notes/research/PROGRAM_CURRENT_TRUTH.md`).

Two honest limits on the safety language. First, `configs/trading.yaml` is a locked runtime policy that
research agents were forbidden to modify; this page does not describe how to arm the scaffold, and the
project never did. Second, the risk gate's registry-bound approved-model check applies only when an order
intent carries the optional `model_id` field. So "fail-closed" is accurate for the *forecaster* path (only
the approved model B1 can serve runtime forecasts), not a claim about the whole trading path.

The 2026 collector is separate from this module: it imports no trading code and hard-halts (exit code 3)
unless `KALSHI_ENABLE_LIVE_TRADING=false` and `TRADING_MODE=paper`. Design background:
[`LIVE_TRADING_ARCHITECTURE.md`](LIVE_TRADING_ARCHITECTURE.md) and
[`BETTING_RISK_POLICY.md`](BETTING_RISK_POLICY.md), both written at design time.

## 13. Example scripts

| Script | What it does | Writes | Needs `pip install -e .` |
|---|---|---|---|
| [`examples/run_demo.py`](../examples/run_demo.py) | Synthetic end-to-end demo | nothing | no |
| [`examples/run_seed_2026.py`](../examples/run_seed_2026.py) | Seed features plus smoke-test backtest | `outputs/` | no |
| [`examples/fetch_public_data.py`](../examples/fetch_public_data.py) | Downloads the three public datasets | `data/raw/`, `data/source_registry.json` | no |
| [`examples/build_truth_tables.py`](../examples/build_truth_tables.py) | Truth tables, 1998–2022 group stages | `outputs/truth_tables/` | no |
| [`examples/run_inplay_demo.py`](../examples/run_inplay_demo.py) | One in-play calculation | nothing | yes |
| [`examples/paper_trade_check.py`](../examples/paper_trade_check.py) | Runs the risk gate on the sample intent; sends no order | nothing | yes |
| [`examples/run_after_match_update.py`](../examples/run_after_match_update.py) | After-game update demo | `outputs/live_example/` **and the tracked `data/live/current_matches.csv`** | yes |

If you run the last one, `git restore data/live/current_matches.csv` afterwards.

## 14. Directory notes

The v0.1 README printed a full directory tree. The repository has since grown to about 150 modules, so that
tree is no longer accurate; start from the root README for the current layout. The parts this page uses are:

```text
src/wcdrawlab/
  cli.py                      the 12 subcommands above
  ingest.py                   public-source registry, downloaders, match normalisers, team-name aliases
  data.py  features.py        time-ordered joins and pre-match feature building
  ratings.py  elo.py          rating helpers and the after-match Elo update
  pipeline.py                 build_features() and the walk-forward backtest
  truth.py                    draw-rate truth tables
  evaluation.py               log loss, RPS, draw Brier, draw calibration
  risk.py                     the uncertainty columns in section 10
  market.py  calibration.py   no-vig conversion, probability-difference scan, draw calibrator
  models/                     baselines.py (prior, ternary Elo, Gaussian draw, logit), scoreline.py (Poisson / Dixon-Coles-style)
  simulation/                 standings, official 2026 tiebreak engine, group simulator, draw-utility calculator
  live.py                     predict-live and update-after-match
  inplay/engine.py            the in-play calculator
  scraping/policy.py          allowlist policy used by validate-source
  trading/                    the dormant paper/demo scaffold behind trade-check / trade-submit
  ablation.py                 ablation scaffold
configs/default.yaml          toolkit defaults
data/seed/                    partial 2026 seed snapshot (demo ratings and odds)
data/live/                    tracked sample state and example trade JSON (see the warning in section 11)
schemas/                      matches.yaml, ratings.yaml, odds.yaml and the later research schemas
examples/                     the seven scripts in section 13
tests/test_core.py            the original toolkit tests (the full suite now has 82 test modules)
```

Everything else under `src/wcdrawlab/` (`research/`, `runtime/`, `operations/`, `providers/`, `ingestion/`)
belongs to the later research lines and the prospective pipeline. Start from the
[root README](../README.md) and the [docs index](README.md) for those.

## 15. Important limitation of the seed data

The included 2026 seed data is a partial snapshot (29 matches, 18 of them with a score, source labels
dated 18 June 2026) assembled by hand for pipeline testing, with placeholder ratings and odds. Some rows
carry notes such as "score not included in snippet". Use it to check that the system runs, nothing more.

The lab's actual 2026 evaluation used separately collected, timestamped inputs. It is reported, with its
caveats and errata, in the [root README](../README.md), [`ERRATA.md`](ERRATA.md) and the `PROSPECTIVE_*`
reports indexed in [`notes/research/README.md`](../notes/research/README.md).
