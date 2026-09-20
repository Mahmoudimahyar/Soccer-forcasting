# World Cup Forecasting Lab

**A probabilistic football-forecasting research lab, evaluated prospectively on the 2026 World Cup — built to find out what actually works, and to say so plainly when the answer is "nothing yet".**

[![tests](https://github.com/Mahmoudimahyar/Soccer-forcasting/actions/workflows/tests.yml/badge.svg)](https://github.com/Mahmoudimahyar/Soccer-forcasting/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![mode](https://img.shields.io/badge/mode-paper--only%20research-lightgrey)

Pre-match win/draw/loss models, in-play models, a tournament simulator, a data-engineering plane, and a
live shadow experiment that froze predictions *before kickoff* during the 2026 World Cup group stage and
scored them afterwards against the bookmaker consensus.

The headline finding is a **null result, reported as one**: on 34 prospectively scored fixtures, an
Elo model with no fitted parameters, the bookmaker consensus and every blend of the two were statistically
indistinguishable. Most of the other research lines ended the same way — and the lab's own power analysis
explains why. What this repository demonstrates is not a winning model. It is **how to run forecasting
research so that you can believe the answer**: frozen evaluators, immutable prediction ledgers, leakage
tests, outcome-independent scoring rules, machine-readable decision ledgers, and a record of every error
the project caught in itself.

> [!IMPORTANT]
> **Research-only and paper-only.** No bet or order was ever placed, no profitability is claimed or shown,
> and nothing here is betting or financial advice. Every reported number is a forecast-quality metric
> (RPS, log-loss, Brier, calibration) — never P&L.

| | |
|---|---|
| **Status** | Research window 2026-06-20 → 2026-06-29; consolidated and published 2026-09-20. **Group stage only** — knockout rounds were never collected or scored. |
| **Approved model** | One: **B1**, a ternary-Elo model with no fitted parameters. Everything else is research/shadow. |
| **Tests** | **817 passed, 51 skipped, 0 failed** on a fresh clone (Python 3.13). The skips are integration tests that need datasets this repo does not redistribute. |
| **Size** | ~18.5K lines in `src/` (153 modules), ~32.7K in `scripts/`, ~8.4K in `tests/` (82 modules) · 46 schemas · 88 machine-readable ledgers · ~295 research notes · 26 milestone tags |

---

## The headline result

During the 2026 World Cup group stage a scheduled collector froze pre-kickoff predictions into an
immutable, first-write-wins ledger (680 rows, 35 fixtures). After the matches, an independent harvester
scored exactly **one pre-specified snapshot per fixture** against verified final results.

| model | RPS ↓ [95% CI] | log-loss ↓ | draw-Brier ↓ |
|---|---|---|---|
| **B1** — ternary Elo (approved) | 0.1304 [0.0891, 0.1771] | 0.7754 | 0.1833 |
| **M2_market** — no-vig bookmaker consensus | 0.1360 [0.0982, 0.1770] | 0.7740 | 0.1765 |
| M3 — 75% B1 / 25% market | 0.1304 | 0.7712 | 0.1812 |
| M4 — 50% / 50% | 0.1314 | 0.7697 | 0.1793 |
| M5 — 25% B1 / 75% market | 0.1333 | 0.7707 | 0.1778 |

<sub>34 fixtures scored, 1 excluded with a recorded reason · 5,000-resample match-level bootstrap · blend weights were fixed in advance, never tuned.</sub>

![Forest plot: every paired RPS difference has a 95% interval crossing zero](docs/img/prospective_paired_deltas.svg)

**Zero of the 24 reported paired differences has a 95% interval that excludes zero.** Elo is nominally
ahead on RPS; the market is nominally ahead on log-loss and draw-Brier. In the repository's own words:
*"no evidence that B1 or any blend beats the market (or vice-versa)."* Nothing was promoted.

Three caveats a careful reader should hold onto:

1. **The "market" here is an early line, not a closing line.** For 31 of the 34 fixtures the scored
   snapshot is an early "baseline" one; across all 34 the median lead time was ~98 hours before kickoff. A bug ([ERRATA E2](docs/ERRATA.md)) silently
   discarded the 47 near-kickoff odds snapshots the collector paid for. The null stands; the comparison is
   weaker than "model versus closing market" and is labelled that way everywhere.
2. **The sample is exploratory.** 34 fixtures sits in the lab's own tier C (20–49); its bar for a
   confirmatory claim is 50+.
3. **The scoring rule was pre-specified, and that is self-attested.** The one-snapshot-per-fixture rule
   depends only on timestamps and coverage, never on outcomes, and was written down before any
   model-versus-outcome metric was computed — but the rule, the script and the results share one commit,
   so the ordering cannot be proven from git.

Read more: [scorecard](notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md) ·
[market benchmark](notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md) ·
[pre-specification](notes/research/prospective_score_harvest_preregistration.md) ·
[decision ledger](data/reference/prospective_model_decision_ledger.json)

---

## What was learned

Null and negative results are listed as prominently as the positives, because they are most of the results.

| Research line | Question | Result | n | Verdict |
|---|---|---|---|---|
| **Prospective 2026** | Do frozen Elo / blends differ from the bookmaker consensus, out of sample? | No model distinguishable from another | 34 fixtures | **null** (exploratory) |
| **Pre-match baselines** | Does anything beat plain Elo on freely available data? | No. Best ensemble vs Elo: ΔRPS +0.0011 [−0.0059, +0.0077] | 144 dev matches | **null** → Elo approved |
| 2022 retrospective market study | Does the market add information to Elo? | 75/25 Elo/market blend better on RPS [−0.013, −0.0005]; market alone not significant | 48 matches | **suggestive**, single tournament, nothing promoted |
| Autoresearch loop | Can a bounded agent loop improve the candidate model? | 20 experiments, every variant under the pre-set 0.002 threshold | dev folds | **null** |
| Squad value, FIFA ranking, weighted Elo | Do they add to Elo? | Squad features made CV log-loss worse (0.834 vs 0.813) | 128 matches | **negative** |
| **In-play vs static** | Does updating on score and time beat a pre-match forecast? | Yes: RPS 0.1478 vs 0.1897 | 30 matches (2026) | **positive**, magnitude indicative only |
| In-play Poisson vs time+score baseline | Does an unfitted remaining-time Poisson beat a fitted baseline? | ΔRPS −0.0145 [−0.021, −0.008] on 151 matches; **not confirmed** on a larger overlapping set: −0.0042 [−0.0083, +0.0002] | 151 → 302 | **modest positive, unconfirmed** |
| xG features (in-play) | Do six pre-specified xG families help? | None significant (ΔRPS +0.0002 [−0.001, +0.002]) | 302 matches | **null** |
| Player, lineup and dynamic state | Do they beat the Poisson reference? | 0 candidates promoted | 627 matches | **null** |
| Event-process and residual goal intensity | Do rich event features beat the reference? | Nothing cleared the locked multi-rule gate | 58 → 231 matches | **reference_only** |
| Hierarchical club → international transfer | Does club data transfer? | Run had 0 club training rows; lift **untested** | — | **incomplete** |
| Commentary NLP (club football) | Can commentary produce high-precision event labels? | 0 of 12 classes passed the precision gate; closest, corners, 0.786 (Wilson LB 0.768) | 254 games | **negative** |

Each line has a completion report, and most have a machine-readable decision ledger:
**[research index →](notes/research/README.md)** · **[ledgers →](data/reference/README.md)**

### Why the nulls are nulls

The independent unit in this problem is the **match**, not the snapshot: inflating the in-play sample 1×,
2×, 4× and 8× on the same matches left statistical power flat. On the 231 matches available, the power to
detect a 0.005 improvement in RPS is about 0.28; 80% power first appears near 1,200 matches. So the honest
reading of most rows above is *"no evidence of improvement at this sample size"* — not *"no effect"*.

![Power curve: match-clustered power against number of matches](docs/img/power_curve.svg)

---

## Why you might trust this

**Mechanisms built in from the start**

- **A fixed evaluator.** Time-ordered folds (develop on 2010/2014/2018, read the 2022 gate once, 2026
  matchday 1 locked), a composite objective, a forbidden-column leakage guard — and promotion hard-coded to
  `False`, so research code cannot approve itself. ([`program.md`](program.md),
  [`runner.py`](src/wcdrawlab/research/runner.py))
- **One approved model, enforced in code.** A registry pins B1 as the only runtime model; the forecaster
  raises rather than fall back to a shadow model. ([`approved_models.yaml`](configs/approved_models.yaml))
- **Immutable, first-write-wins ledgers.** Predictions cannot be rewritten or back-filled after kickoff;
  score rows are keyed on `prediction_id + result_hash + scorer_version`, so re-runs add nothing and a
  corrected result is *appended*, never overwritten.
- **Leakage and integrity tests.** Around 118 of the tests are named for leakage, causality, pre-kickoff
  timing, immutability, idempotence, determinism or fail-closed behaviour —
  e.g. [`test_research_leakage.py`](tests/test_research_leakage.py),
  [`test_shadow_integrity.py`](tests/test_shadow_integrity.py),
  [`test_runtime_governance.py`](tests/test_runtime_governance.py),
  [`test_final_holdout.py`](tests/test_final_holdout.py).
- **Decision ledgers, not prose.** Every research line ends in a machine-readable verdict using a fixed
  vocabulary (`reference_only`, `rejected`, `data_insufficient`, …).

**Errors the project caught in itself**

1. **Selection on the test set.** The "best" in-play model had been crowned after repeatedly looking at
   2026 results. The affected claims were downgraded in a machine-readable status registry (the "best
   model" claim to `invalid_due_to_model_selection_on_test_set`, three more to exploratory); a nested
   cross-validation rerun on 302 matches never selected it; the frozen model was re-frozen to the plain
   reference, with the first freeze kept as an immutable record.
   ([reconciliation](notes/research/inplay_evaluation_reconciliation.md) ·
   [nested evaluation](notes/research/inplay_nested_evaluation.md))
2. **Release-gate contamination.** A blend weight had been chosen with a sweep that touched the 2022 gate;
   selection was redone on development folds only.
3. **Two data-leakage bugs** in the first modelling table; the score computed on the corrupted table was
   declared invalid rather than kept.
4. **An own-goal inversion bug** found by replaying the 2022 World Cup: Canada 1–2 Morocco had been derived
   as 0–3. Fixed with a provider-aware event-semantics layer that fails closed (48/48 matches now reconcile).
5. **Over-reported coverage**, twice: a backfill that claimed 2,000/2,000 while 1,940 were raw-backed, and
   a cache that claimed 258 files with about 60 on disk. The lab's own evidence registry marks the latter
   `contradicted`; one sprint's git tag is literally `…-incomplete`.
6. **A scorer that silently scored nothing** (exit code 0, empty output) — root-caused with a 14-candidate
   failure matrix and replaced by an independent, idempotent harvester.
7. **Two more bugs found while preparing this release**, including one that invalidated a recorded model
   comparison. Both are fixed and written up in **[docs/ERRATA.md](docs/ERRATA.md)**.

---

## Architecture

```mermaid
flowchart LR
  subgraph DP["Data plane"]
    SRC["Open datasets and keyed APIs"]
    ING["Read-only provider adapters"]
    RAW["Immutable raw store with provenance"]
    TAB["Leakage-tested tables and event lake"]
  end
  subgraph RS["Research sandbox"]
    CAND["Candidate and research models"]
    EVAL["Fixed evaluator, frozen folds"]
    LEDG["Research notes and decision ledgers"]
  end
  HUM["Human review"]
  subgraph RT["Guarded runtime plane"]
    REG["Approved-model registry"]
    FC["Runtime forecaster: B1 only"]
    RISK["Deterministic risk gate"]
    PAPER["Paper mode"]
  end
  subgraph PO["Prospective shadow evaluation 2026"]
    COL["Scheduled bounded collector"]
    BUD["Odds budget guard"]
    FRZ["Frozen prediction ledger"]
    RES["Verified final results"]
    HARV["Idempotent score harvester"]
    BENCH["Benchmark vs market"]
  end
  SRC --> ING --> RAW --> TAB
  TAB --> CAND --> EVAL --> LEDG
  LEDG --> HUM --> REG
  REG --> FC --> RISK --> PAPER
  COL --> BUD --> FRZ
  TAB --> FRZ
  FRZ --> HARV
  RES --> HARV --> BENCH --> LEDG
```

| Package | What it does |
|---|---|
| [`wcdrawlab`](src/wcdrawlab) (core) | Ingestion and team-name normalisation, time-safe joins, walk-forward Elo, evaluation metrics, uncertainty reporting, CLI |
| [`models`](src/wcdrawlab/models) · [`simulation`](src/wcdrawlab/simulation) | Ternary Elo (B1), Poisson / Dixon-Coles, and a group-stage simulator implementing the FIFA 2026 tiebreak order |
| [`research`](src/wcdrawlab/research) | The fixed evaluator and the single agent-editable candidate; in-play models; event-process, residual-intensity, transfer and commentary research planes |
| [`operations`](src/wcdrawlab/operations) · [`providers`](src/wcdrawlab/providers) · [`ingestion`](src/wcdrawlab/ingestion) | Read-only, quota-aware adapters; content-addressed raw store; immutable ledger; persistent odds-budget guard |
| [`runtime`](src/wcdrawlab/runtime) | Approved-model registry and a forecaster that fails closed on unknown or shadow models |
| [`trading`](src/wcdrawlab/trading) | A dormant, paper-mode execution scaffold — see below |

**About the trading package.** It is a triple-gated paper/demo scaffold that was **never armed and never
given credentials**; no order was ever placed. The production order path raises unless three independent
switches are set, and the collector refuses to run at all unless `KALSHI_ENABLE_LIVE_TRADING=false` and
`TRADING_MODE=paper`. It is left in the repository, labelled, rather than quietly removed.

---

## Quickstart

```bash
git clone https://github.com/Mahmoudimahyar/Soccer-forcasting.git && cd Soccer-forcasting
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e .
pytest -q                                              # 817 passed, 51 skipped
python examples/run_demo.py                            # synthetic end-to-end demo, no keys or data needed
```

- **[QUICKSTART.md](QUICKSTART.md)** — API keys, data bootstrap, and how the prospective collector and
  score harvester were run (and can be replayed).
- **[docs/TOOLKIT_USAGE.md](docs/TOOLKIT_USAGE.md)** — the forecasting toolkit and CLI: backtests, truth
  tables, the simulator, uncertainty columns.
- **[docs/README.md](docs/README.md)** — index of all documentation. **[docs/GLOSSARY.md](docs/GLOSSARY.md)** — every model name and metric.

**What you can and cannot reproduce.** The code, tests, schemas, manifests and decision ledgers are all
here. The datasets are not: raw provider payloads and derived tables are deliberately untracked for
licensing reasons, so reproducing a result end to end needs your own API keys and downloads
([data sources](docs/DATA_SOURCES.md)).

## Repository map

```
src/wcdrawlab/      library: models, evaluator, in-play, operations, runtime governance
scripts/            entry points, dataset builders, audits, research job queues, schedulers   → scripts/README.md
tests/              82 modules; leakage, immutability, governance and pipeline tests
configs/ schemas/   model registry, research config, frozen-model manifests; 46 data contracts
data/reference/     88 machine-readable ledgers, manifests and audits (no raw data)           → data/reference/README.md
notes/research/     the complete research record, including superseded claims                 → notes/research/README.md
docs/               protocols, runbooks, policies, glossary, errata                           → docs/README.md
data_requests/      governed requests for any new data source
```

## A short glossary

| Name | Meaning |
|---|---|
| **B1** (also `M1_B1`) | Ternary-Elo model, draw parameter r = 0.4, nothing fitted. The only approved model. |
| **M2_market** | No-vig bookmaker consensus. A read-only comparator — never a feature, target or signal. |
| **M3 / M4 / M5** | Fixed 75/25, 50/50 and 25/75 blends of B1 and the market. |
| **In-play M2** | A *different* model: remaining-time Poisson with hand-set constants (`m2_frozen` is its frozen copy). Later lines use closely related Poisson references under other names — W2, R0/R2, T0, e2 — that drop the Elo term. |
| **V8** | The autoresearch candidate (logit blended with Elo). Shadow-only. |
| **RPS** | Ranked probability score for ordered win/draw/loss forecasts. Lower is better. |
| **Tier A–D** | The lab's own sample-size labels: C = 20–49 fixtures ("exploratory"), D = 50+ ("confirmatory"). |
| **LOCO** | Leave-one-competition-out cross-validation. |

Full version: [docs/GLOSSARY.md](docs/GLOSSARY.md).

## How this was built

This project was **directed by a human and executed largely by an AI coding agent** (Claude Code) working
under a written contract: a fixed evaluator it could not edit, a single file it was allowed to change in
the autonomous loop, protected trading/provider/credential paths, and a rule that any new data source must
be requested in writing first. The owner set the research questions, the safety constraints and the
promotion rules, and made every decision about paid data and approvals; the agent wrote most of the code,
ran the experiments and wrote the notes. That is why the history is about 170 commits, almost all within ten days, with unusually
long commit messages, and why the notes include the agent's own operating state.

The "audits" and "independent reviews" referred to in the notes are **internal, adversarial agent audits —
not third-party review.** They did catch real errors (above), which is the point of running them. Details:
[docs/ai-workflow/](docs/ai-workflow/README.md).

## Limitations

- **Small samples everywhere**: 48 matches per World Cup fold, 34 prospective fixtures, roughly 9–13 draws
  per evaluation set. Differences between serious models sit inside the noise.
- **Group stage only.** No knockout-round forecasts, extra time or shoot-outs were evaluated.
- **The prospective market comparator is an early line** ([E2](docs/ERRATA.md)).
- **B1's approval means "nothing beat it with significance on free data"** — not that it is strong in
  absolute terms. On the single-read 2022 gate it ranked 5th of 9 by composite score.
- **No in-play model was ever scored prospectively**; the in-play freeze is governance machinery.
- **Several research-line pipelines are single-machine orchestration records** with hard-coded local
  paths. The tests, the toolkit and the prospective harvester are portable.

## Data sources and attribution

Open data from StatsBomb, SoccerNet, martj42 and the Fjelstul World Cup Database, plus keyed APIs
(football-data.org, API-Football, The Odds API) and the keyless Open-Meteo. **No raw third-party data is redistributed
here** — only identifiers, hashes, aggregate counts and the lab's own ledgers. Event data comes from
[StatsBomb Open Data](https://github.com/statsbomb/open-data) (non-commercial research use, credited per
their user agreement); commentary from SoccerNet-Echoes (CC BY 4.0). Licences, terms and the
required attribution lines are in **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)**. The MIT licence covers
the code only.

## Licence and citation

[MIT](LICENSE) © 2026 [@Mahmoudimahyar](https://github.com/Mahmoudimahyar). If this is useful in your own
work, see [CITATION.cff](CITATION.cff). Corrections are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)
and [docs/ERRATA.md](docs/ERRATA.md).
