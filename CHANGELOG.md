# Changelog

A dated, newest-first log of this repository. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): one public package release (0.3.0) on top,
then the research history underneath it as **one entry per milestone git tag** (plus one untagged
research line, marked as such).

This is a research lab, so each entry records what was done **and the verdict** — including null,
negative and incomplete results — in the repo's own decision vocabulary (`reference_only`, `rejected`,
`no_evidence_of_improvement`, `data_insufficient`, `market_comparator_only`,
`exploratory_underpowered`; defined in [docs/GLOSSARY.md](docs/GLOSSARY.md)). Known defects are listed
in [docs/ERRATA.md](docs/ERRATA.md) and cross-referenced below as E1–E7.

Everything here is paper-only research. The trading module is a dormant, triple-gated paper/demo
scaffold: never armed, never given credentials, no order ever placed. Every result is a
forecast-quality metric, never P&L. Nothing in this file is betting or financial advice.

**How to read this file**

- **Dates** are the git committer date of the tagged commit
  (`git log -1 --format=%cs refs/tags/<tag>`), in the author's local time (UTC−4). A few completion
  reports carry a UTC date one day later than their tag.
- **Tags are lightweight, and 13 of the 26 tag names are also branch names.** Write
  `refs/tags/<name>` (for example `git show refs/tags/evaluation-reset-event-expansion`) to avoid git's
  "refname is ambiguous" warning.
- **Test counts inside the linked historical reports are point-in-time and stale.** The only current
  figure is in the 0.3.0 entry.
- **"Pre-specified"** means written into the repo before the results were computed. That ordering is
  self-attested by the repo's own commits; nothing was registered externally.
- **"Internal audit"** means an audit run by the lab's own AI agent under the governance contract in
  [program.md](program.md). No third party has reviewed this work.
- **Model names collide across research lines.** Pre-match shadow models M1–M5 (B1, market, fixed
  blends) are unrelated to in-play models M0–M6. The same unfitted remaining-time Poisson reference
  (hand-set constants, nothing estimated from data) appears as M2, `m2_frozen`, W2, R2/R0, T0 and e2.
  See the glossary.
- **Abbreviations.** RPS = ranked probability score (lower is better). dRPS = paired difference in RPS,
  candidate minus reference, so negative favours the candidate. LOCO / LOGO = leave-one-competition-out
  / leave-one-group-out. 1X2 and W/D/L both mean the three-way win/draw/loss outcome. Intervals in
  square brackets are 95% bootstrap confidence intervals, with the match as the resampled unit. More
  in the glossary.
- A null is reported as "no evidence of improvement at this sample size", not as "no effect".

---

## 0.3.0 - 2026-09-20 - Public consolidation

The research ran from 2026-06-20 to 2026-06-29. This release consolidates it into one branch and
prepares it for public reading. No new modelling result was produced on this date.

### Changed

- All 27 pre-existing branches (26 research lines plus the original `master`) merged into `main`
  non-destructively. The original branches and all 26 milestone tags are preserved.
- Root tidy: AI-workflow scaffolding moved to [docs/ai-workflow/](docs/ai-workflow/README.md); stale
  status files moved to [docs/history/](docs/history/VERSION.md) with SUPERSEDED / historical banners;
  the setup script moved to `scripts/` and lost its automatic `git init/add/commit` block. Nothing under
  `notes/research/` or `data/reference/` was moved or renamed.
- Package metadata: version 0.3.0; description now says what the package is (forecasting research,
  paper-only); `pyarrow` added, never-imported dependencies dropped; `src/wcdrawlab.egg-info`
  untracked; `.gitignore` extended.
- Documentation overhaul: README, [glossary](docs/GLOSSARY.md), [errata](docs/ERRATA.md),
  [data sources](docs/DATA_SOURCES.md), the original v0.1 how-to preserved as
  [docs/TOOLKIT_USAGE.md](docs/TOOLKIT_USAGE.md), and index pages for
  [notes/research/](notes/research/README.md), [data/reference/](data/reference/README.md) and
  [scripts/](scripts/README.md). Stale notes received banners rather than edits.

### Added

- `CONTRIBUTING.md`, `CITATION.cff`, and a GitHub Actions test workflow
  ([.github/workflows/tests.yml](.github/workflows/tests.yml)).
- Two static SVG figures ([docs/img/](docs/img/README.md)) and the standard-library-only script that
  draws them, `scripts/make_readme_figures.py`. The script re-draws numbers already committed in the
  repo; it fits, selects and re-scores nothing.

### Fixed

- **ERRATA E1 — prequential dtype bug.** `scripts/prequential_2026.py` built the candidate's test row
  as an all-object-dtype frame, so every V8 feature was zero-filled and V8 emitted a near-constant
  forecast. The recorded "V8 worse than B1 on 2026" result, and its draw-calibration figure, were
  artifacts. Corrected on the same 33 matches: V8 RPS 0.173 / log-loss 0.948 / draw-cal 0.175 vs B1
  0.174 / 0.958 / 0.178 — tied. B1's figures were never affected. V8 stays shadow-only for the valid
  reason (no significant dev-fold improvement).
- **ERRATA E2 — odds snapshot key mismatch.** The budget-guarded fetcher wrote payloads under
  `"events"`; the freezer read only `"data"`. All 47 durable-collector snapshots (47 of 500 credits)
  were silently ignored. The freezer now accepts both keys. The historical prediction ledger is
  unchanged, so the 2026 benchmark's market comparator remains an early line, not a closing line (see
  the [2026-06-29 entry](#prospective-score-harvest-benchmark-v1)).
- **Portable event-lake guard.** The guard matched the author's directory *names*, so on any other
  clone a lake root inside the repo was silently accepted. It now checks path containment against the
  actual checkout root.
- **Hermetic supervisor test.** One test read a machine-specific collector heartbeat at an absolute
  path. It now runs under `tmp_path`, with a negative control showing the interlock still fails closed
  when no heartbeat exists.
- **`pytest.ini` `testpaths = tests`.** Three research scripts matched the test globs and one imports
  `duckdb` at module scope, so a clean install aborted at collection and ran zero tests.
- **`wcdrawlab predict-live` crash.** `run_live_prediction_refresh()` ended with a block copied from the
  after-match path that referenced undefined names, so the command raised `NameError` *after* writing its
  outputs. The test module imported the function but never called it. Fixed, with a regression test.
- **Crash under pandas 3 (found by the first CI run).** Under copy-on-write `to_numpy()` can return a
  read-only view; `live.py` repaired invalid market rows in place and raised "assignment destination is
  read-only". Python 3.13 resolves pandas 3, Python 3.10 cannot, so the 3.10 job passed while both 3.13
  jobs failed. Fixed with an explicit copy; the suite passes on pandas 2.3 and 3.0.
- **Vacuous passes → skips.** Two corpus-coverage tests passed via a bare `return` when the corpus was
  absent. They now skip with a reason.
- `safe_config` no longer defaults to a fixed path on the author's machine (repo root by default,
  `WCLAB_MAIN_ROOT` to override).
- **Licence.** `LICENSE` was a truncated stub. It is now the full MIT text and covers code only;
  third-party data is not covered ([docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)).
- Five leftover chat-assistant citation tokens removed from two docs (cosmetic).

### Verified

- Test suite under fresh-clone conditions (no gitignored data), Python 3.13, Windows:
  **817 passed, 51 skipped, 0 failed** (868 collected). The 51 skips are integration tests that need
  gitignored datasets or the author's external event lake; see
  [docs/TESTING_AND_DATA_DEPENDENCIES.md](docs/TESTING_AND_DATA_DEPENDENCIES.md).

### Deliberately not changed

- `configs/approved_models.yaml` still quotes the stale E1 numbers. The file is governance-protected
  and was left untouched; the errata is the correction of record.
- The collector's own score path was never patched (E3). The standalone score harvester is the only
  working scoring path.
- E4–E7 (early unconfirmed claims, a missing decision ledger, two vocabularies for one outcome, stale
  manifests and machine-specific paths) are documented, not repaired. See
  [docs/ERRATA.md](docs/ERRATA.md).

---

## Research milestones, 2026-06-20 to 2026-06-29

166 commits, 26 milestone tags. The 2026 World Cup **group stage only**; knockout rounds were never
collected or scored. No model other than B1 (ternary Elo) was ever approved for runtime, and no
research candidate was promoted in any line.

### At a glance

| Date (2026) | Tag | Line | Verdict in one line |
|---|---|---|---|
| 06-29 | [`prospective-score-harvest-benchmark-v1`](#prospective-score-harvest-benchmark-v1) | Prospective | Null: no model separable from an early-line market, n=34 |
| 06-29 | [`hierarchical-domain-transfer-v1`](#hierarchical-domain-transfer-v1-no-tag) (no tag) | In-play | Incomplete / null; transfer untested |
| 06-28 | [`international-event-lake-restoration-v1`](#international-event-lake-restoration-v1) | In-play / data | 10 of 10 `reference_only`; power still low |
| 06-27 | [`evidence-power-consolidation-v1`](#evidence-power-consolidation-v1) | Evidence audit | Methodological; explains the nulls |
| 06-27 | [`residual-goal-intensity-v1`](#residual-goal-intensity-v1) | In-play | Negative: 0 candidates |
| 06-27 | [`event-process-intelligence-v1`](#event-process-intelligence-v1) | In-play | Negative: 0 candidates |
| 06-26 | [`dynamic-inplay-intelligence-v1`](#dynamic-inplay-intelligence-v1) | In-play | 0 candidates promoted |
| 06-26 | [`research-truth-full-corpus-xg-fusion-incomplete`](#research-truth-full-corpus-xg-fusion-incomplete) | Data | INCOMPLETE (tag says so) |
| 06-26 | [`player-impact-xg-fusion-v1`](#player-impact-xg-fusion-v1) | In-play | Later downgraded to incomplete |
| 06-26 | [`deep-research-inplay-foundation-v1`](#deep-research-inplay-foundation-v1) | In-play | Null vs the Poisson reference |
| 06-26 | [`api-football-historical-corpus-v1`](#api-football-historical-corpus-v1) | Data | 900/900 reconciled; no model trained |
| 06-26 | [`paid-source-activation-v1`](#paid-source-activation-v1) | Data | `accepted_for_limited_historical_research` |
| 06-26 | [`structured-event-procurement-readiness-v1`](#structured-event-procurement-readiness-v1) | Data | Decision document; no vendor chosen |
| 06-26 | [`commentary-low-confidence-signals-v1`](#commentary-low-confidence-signals-v1) | Commentary NLP | Flagged fallback, not silver labels |
| 06-26 | [`commentary-precision-weak-supervision-v2`](#commentary-precision-weak-supervision-v2) | Commentary NLP | Negative: 0 of 12 classes qualified |
| 06-23 | [`soccernet-real-alignment-v1`](#soccernet-real-alignment-v1) | Commentary NLP | `ready_for_historical_weak_supervision_only` |
| 06-23 | [`commentary-intelligence-research-v1`](#commentary-intelligence-research-v1) | Commentary NLP | No source live-eligible |
| 06-23 | [`shadow-offline-hardening-v1`](#shadow-offline-hardening-v1) | Prospective | Readiness only |
| 06-22 | [`v1-5-prospective-readiness`](#v1-5-prospective-readiness) | Prospective | Readiness only; no model claim |
| 06-22 | [`evaluation-reset-event-expansion`](#evaluation-reset-event-expansion) | In-play | Selection-on-test caught; tuned models not selected |
| 06-21 | [`tier-4-research-sprint-1`](#tier-4-research-sprint-1) | In-play | No model fit for a live shadow test |
| 06-21 | [`event-replay-2022-validated`](#event-replay-2022-validated) | In-play / data | Own-goal bug fixed; 48/48 reconcile |
| 06-21 | [`shadow-session-20260621-closed`](#shadow-session-20260621-closed) | Prospective | Descriptive only, n=1 |
| 06-21 | [`data-readiness-gate-1`](#data-readiness-gate-1) | Data | Readiness only |
| 06-21 | [`approved-b1-runtime`](#approved-b1-runtime) | Pre-match | B1 approved: nothing robustly beat plain Elo |
| 06-20 | [`tier-1-baseline-recorded`](#tier-1-baseline-recorded) | Foundations | Record only |
| 06-20 | [`tier-1-complete`](#tier-1-complete) | Foundations | Foundation complete; two leaks caught |

### 2026-06-29

#### `prospective-score-harvest-benchmark-v1`

Root-caused the scheduled collector's silently empty scorecard, recovered the scores with a
standalone, idempotent, append-only harvester, and ran the fixture-level benchmark of the frozen
pre-match shadow models: B1 (`M1_B1`), the no-vig bookmaker consensus (`M2_market`, a read-only
comparator) and three fixed-weight B1/market blends (`M3_75_25`, `M4_50_50`, `M5_25_75`; weights never
tuned).

- **Verdict — null (Tier C, the lab's own "exploratory" label for 20–49 fixtures).** 35 fixtures had
  frozen pre-kickoff predictions (680 immutable first-write-wins ledger rows); 34 were scored and 1
  excluded (`no_common_market_snapshot`); 35/35 results verified final.

| Model | RPS [95% CI] | Log-loss | Draw-Brier |
|---|---|---|---|
| `M1_B1` | 0.1304 [0.0891, 0.1771] | 0.7754 | 0.1833 |
| `M2_market` (early line) | 0.1360 [0.0982, 0.1770] | 0.7740 | 0.1765 |
| `M3_75_25` | 0.1304 [0.0909, 0.1762] | 0.7712 | 0.1812 |
| `M4_50_50` | 0.1314 [0.0937, 0.1742] | 0.7697 | 0.1793 |
| `M5_25_75` | 0.1333 [0.0945, 0.1756] | 0.7707 | 0.1778 |

n=34 fixtures; lower is better on every metric; 5000-resample match-level bootstrap.

- B1 is nominally better on RPS; the market is nominally better on log-loss and draw-Brier. Neither
  difference is distinguishable from noise: paired RPS delta market − B1 = +0.0057
  [−0.0118, +0.0226].
- **Zero of the 24 reported paired deltas (21 distinct comparisons) has a 95% CI excluding zero.**
  Ledger: B1 `reference_only`, market `market_comparator_only`, all three blends
  `no_evidence_of_improvement`. Nothing promoted.
- **Caveat — the market comparator is an early line, not a closing line.** For 31 of 34 fixtures the
  primary snapshot is a 2026-06-21 "baseline" snapshot, a median of about 98 hours before kickoff (the
  other three: 2 final-pre-kickoff, 1 T-90). The cause is E2. The null says nothing about B1 against a
  closing line.
- The one-snapshot-per-fixture rule was pre-specified and outcome-independent. It was written after
  the matches were played but, by the note's own statement, before any model-vs-outcome metric was
  computed. That ordering is self-attested: rule, script and results share one commit.
- The bug: the collector's score step returned rc=0 every 5 minutes while resolving 0 of 680
  predictions to a finished result, because the results file was never refreshed. A 14-candidate
  failure matrix is in `data/reference/prospective_score_harvest_failure_matrix.json`. The internal
  audit marked "snapshot parsing" as a false cause and so missed E2. The collector itself was never
  patched (E3).

Reports:
[completion](notes/research/PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md) ·
[scorecard](notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md) ·
[market benchmark](notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md) ·
[root-cause audit](notes/research/prospective_score_harvest_root_cause_audit.md) ·
[snapshot rule](notes/research/prospective_score_harvest_preregistration.md)

#### `hierarchical-domain-transfer-v1` (no tag)

Listed for completeness: the last research line has a completion report but never received a
milestone tag. It tried a club→international transfer ladder for in-play W/D/L.

- **Verdict — incomplete / null.** No model beat the T0 reference. The run had 0 club training rows,
  so the transfer ladder collapsed to the international-only model and cross-domain lift is
  **untested**, not refuted.
- The decision ledger the report cites was cleared during an unfinished repair and never regenerated
  (E5). Treat the numbers in the report as unverified.

Report: [completion](notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md)

### 2026-06-28

#### `international-event-lake-restoration-v1`

Restored the StatsBomb Open Data international event lake from 58 to 258 hash-verified objects (58
copied locally, 200 re-retrieved from the official source), then reran the locked model families on
the 231 model-eligible matches (27 exclusions).

- **Verdict — nothing beat the reference: all 10 model records `reference_only`.** The completion
  report's headline reads `data_insufficient` / "Reference: None"; that is a packaging default, not an
  adjudication (E6). The per-model ledger is authoritative.
- Several candidates had a lower point LOCO RPS than the reference e2, but only one (e9) was favoured
  by the match-level bootstrap (0.13358 vs 0.14034, CI excluding zero). e9 still **failed the locked
  multi-rule gate**: log-loss was worse (0.8226 vs 0.7463) and forward-chain RPS was not better. It
  stays `reference_only` and is not a positive result.
- Power re-estimate on 231 matches: power to detect a 0.005 absolute RPS gain is only 0.28; 80% power
  first appears at the ~1,200-match grid point.
- The lake lives on the author's disk and is not redistributed.

Reports:
[completion](notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md) ·
[decision ledger](data/reference/international_event_lake_model_decision_ledger.json) ·
[power analysis](data/reference/international_event_lake_power_analysis.md)

### 2026-06-27

#### `evidence-power-consolidation-v1`

An internal audit of evidence lineage and statistical power, using local artifacts only.

- **Verdict — methodological; no model result.**
- Traced the 58-match evaluation cohort to missing data, not to a rule: 258 bridged matches, 200 with
  no event file on disk, 58 evaluable. An earlier cache audit that claimed 258 cached files is marked
  `contradicted` in the lab's own evidence registry.
- An internal from-scratch recompute of the unfitted reference reproduced the reported RPS exactly
  (0.15263 forward-chain, 0.14906 LOCO). No fitted candidate was recomputed this way.
- The match, not the snapshot, is the independent unit: inflating snapshots 1×/2×/4×/8× on the same
  58 matches left power flat.
- This report's own 58-match power figures used an optimistic noise template and are superseded by
  the 231-match analysis in the entry above.

Reports:
[completion](notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md) ·
[58-match audit](notes/research/residual_58_match_audit.md) ·
[minimum evidence requirements](data/reference/minimum_evidence_requirements.json)

#### `residual-goal-intensity-v1`

Treated the remaining-time Poisson as a reference goal intensity and tried to learn residual
corrections on top of it (58 matches, 5 tournaments, no 2026 data).

- **Verdict — negative, 0 candidates.** The reference R0 had the best pooled forward-chain RPS
  (0.15263). Ledger: 7 `reference_only`, 6 `rejected`, 3 `data_insufficient`.
- At 58 matches this is "no evidence of improvement at this sample size", not evidence of no effect.

Reports:
[completion](notes/research/RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md) ·
[decision ledger](data/reference/residual_goal_intensity_decision_ledger.csv)

#### `event-process-intelligence-v1`

Built a canonical event-process engine (possession, territory, transitions, pressure, set pieces,
chance quality) with a StatsBomb Open Data adapter, and evaluated W/D/L, next-goal and near-term
scoring model families on it. A fourth family, discipline, was blocked by its positive-event threshold
(`data_insufficient`).

- **Verdict — negative, 0 candidates.** On the 58-match cohort every e3–e9 model was worse than the
  reference e2 (LOCO RPS 0.1496). Ledger: 20 `reference_only`, 2 `data_insufficient`.
- Same sample-size caveat as above. For the 231-match rerun see 2026-06-28.

Reports:
[completion](notes/research/EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md) ·
[decision ledger](data/reference/event_process_model_decision_ledger.csv)

### 2026-06-26

#### `dynamic-inplay-intelligence-v1`

The full-corpus rerun: a dynamic in-play phase with temporal player priors and xG state on 627
API-Football internationals (3,135 forward-chained snapshots).

- **Verdict — 0 candidates promoted.** P1–P5, X1 and X3 `rejected`; R0, R1, R2 and X2
  `reference_only`.
- A mis-scoring that had falsely flagged the baseline R1 as a candidate was caught and corrected
  during finalization, one commit before the tag.
- The xG candidates were scored on a different 258-match population, so their raw RPS is not
  comparable with the reference.
- Also in this range: an internal audit caught an over-reported backfill (2,000/2,000 claimed, 1,940
  raw-backed in the canonical root). The gate was changed to measure actual raw-backed coverage.

Reports:
[completion](notes/research/DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md) ·
[decision ledger](data/reference/model_decision_ledger.csv) ·
[operations log](notes/research/RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md)

#### `research-truth-full-corpus-xg-fusion-incomplete`

A "truth registry" sprint that rescanned the actual raw files instead of trusting earlier summaries.

- **Verdict — INCOMPLETE, and tagged as such.** Completion was withheld because hard gates were
  objectively false at the time: player-history corpus 60 of 2,000 fixtures (3%), StatsBomb event
  cache 23%, xG snapshot join 0 rows.
- The registry downgraded the previous sprint's player-impact negative to `incomplete_or_partial`
  (needs rerun).
- The corpus was completed later the same day under `dynamic-inplay-intelligence-v1`. No "complete"
  tag was ever issued for this sprint, and the tagged commit's subject line ("complete corpus…")
  contradicts its own INCOMPLETE body.

Reports:
[completion](notes/research/RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md) ·
[truth registry](notes/research/research_truth_registry_report.md) ·
[claim verification ledger](notes/research/research_claim_verification_ledger.md)

#### `player-impact-xg-fusion-v1`

First attempt at player-impact, substitution-delta and xG-fusion features for in-play W/D/L.

- **Verdict — reported as "rejected" at the time, later downgraded to incomplete.** The sprint's
  P1–P4 table is identical to the previous sprint's W1–W4 table because the job script mapped P1–P4
  onto inherited predictors, and only 60 of 2,000 planned player-history fixtures had been pulled.
  xG fusion was not evaluated (the join was not wired).
- Do not cite this sprint's numbers. The valid rerun is `dynamic-inplay-intelligence-v1`, which
  promoted nothing.

Report: [completion](notes/research/PLAYER_IMPACT_XG_FUSION_COMPLETION.md)

#### `deep-research-inplay-foundation-v1`

In-play baselines on the API-Football corpus: 627 internationals, leave-one-competition-out, plus a
club→international transfer check. The corpus grew by a predeclared 220 fixtures (1,120/1,120
regulation scores reconciled).

- **Verdict — null.** Team-state and lineup-continuity models did not improve on the remaining-time
  Poisson reference (all RPS 0.1500). Club→international transfer: `transfer_neutral`.

Report: [completion](notes/research/DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md)

#### `api-football-historical-corpus-v1`

Committed a fixture manifest built from metadata only (before the corpus backfill retrieved events or
lineups), backfilled 900 fixtures (627 international + 273 club) and reconciled event-derived scores.

- **Verdict — data gate passed; no model trained.** Event-derived regulation scores matched the
  provider's full-time score on 900/900 audited fixtures, after fixing a recurrence of the own-goal
  inversion bug (pilot: 12/120 mismatches → 120/120).
- This is a same-provider consistency check. It is not claimed for the later 2,000-fixture
  player-history pull.
- The sending-off model class had 123 of the 150 positive events required, so it was marked not
  ready.

Reports:
[completion](notes/research/API_FOOTBALL_HISTORICAL_CORPUS_COMPLETION.md) ·
[reconciliation remediation](notes/research/api_football_reconciliation_remediation.md) ·
[sampling protocol](notes/research/api_football_corpus_sampling_protocol.md)

#### `paid-source-activation-v1`

Ran the already-paid API-Football Pro plan through the acceptance protocol on real samples (a
27-request sampled audit and a 120-match pilot).

- **Verdict — `accepted_for_limited_historical_research`.** Lineups, benches, player IDs, positions
  and timestamped events are available. Statistics are team-level, with no per-shot coordinates. xG
  was present in the sampled Euro 2024 fixture and absent in the sampled World Cup 2022 fixture.
- Pilot score reconciliation was only 90% (12 of 120 mismatched). The pilot report attributed the
  mismatches to extra-time, shootout and VAR boundaries. That was wrong: all 12 contained an own goal,
  and the cause was the own-goal inversion bug, fixed in the next milestone.

Reports:
[completion](notes/research/PAID_SOURCE_ACTIVATION_COMPLETION.md) ·
[coverage audit](notes/research/api_football_empirical_coverage_audit.md)

#### `structured-event-procurement-readiness-v1`

Desk research on five licensed event-data providers (public pages only; nothing purchased, nobody
contacted), plus a provider-neutral adapter framework and a fail-closed acceptance protocol exercised
on a mock provider.

- **Verdict — a decision document, not a result.** Rights and historical depth, not coverage, are the
  binding unknowns for every vendor. No single provider is recommended. (The earlier 2026-06-22
  provider package had named a lowest-cost vendor; this later matrix recommends none.)

Reports:
[completion](notes/research/STRUCTURED_EVENT_PROCUREMENT_READINESS_COMPLETION.md) ·
[decision matrix](notes/research/structured_event_provider_decision_matrix.md)

#### `commentary-low-confidence-signals-v1`

Follow-up to the V2 gate below: packaged corner, foul and yellow-card emissions as explicitly flagged
low-confidence historical records.

- **Verdict — a flagged fallback, not silver labels** (`usable_only_with_low_confidence_flag`). 2,710
  records: corner 1,267, foul 1,242, yellow card 201.
- The records are built in-sample and anchored to labelled events, so the held-out precision figures
  do not describe them. They are kept locally only; the repo tracks the manifest, data card and build
  script. No outcome model was trained.

Reports:
[build report](notes/research/commentary_low_confidence_signals_report.md) ·
[data card](notes/research/commentary_low_confidence_signals_data_card.md)

#### `commentary-precision-weak-supervision-v2`

A precision-first ladder (rules with negation, TF-IDF + logistic regression, hybrid, train-selected
abstention) on 383,591 SoccerNet-Echoes ASR segments from 254 English-translated **European club**
games, 6 leave-one-competition-out folds. The approval thresholds were committed to git before the
model code and the results.

- **Verdict — negative: 0 of 12 event classes qualified** under the gate (≥50 emissions, Wilson 95%
  lower bound on precision ≥0.80, timing and fold stability). The silver-label dataset was released
  empty; downstream verdict `insufficient_quality_or_coverage`.
- Closest: corner precision 0.786 (Wilson LB 0.768, n=2,129) and foul 0.788 (LB 0.768).
- Abstention raised goal precision from 0.15 to 0.67 only by cutting emitted labels from 9,860 to 76.
- This is club football, not the World Cup. No outcome model was trained and no predictive value is
  claimed. The repo tracks no commentary text and no SoccerNet label files.

Reports:
[completion](notes/research/COMMENTARY_PRECISION_V2_COMPLETION.md) ·
[thresholds](notes/research/COMMENTARY_PRECISION_PREREGISTRATION.md) ·
[failure analysis](notes/research/commentary_precision_failure_analysis.md)

### 2026-06-23

#### `soccernet-real-alignment-v1`

Exact game-path join of SoccerNet-Echoes ASR commentary to SoccerNet action labels, with a
keyword-plus-time aligner evaluated leave-one-competition-out on 254 English-translated club games.

- **Verdict — `ready_for_historical_weak_supervision_only`**, later overtaken by the V2 gate above
  (0 classes qualified).
- Goal recall was about 0.63–0.88 across folds, but goal precision was only about 0.16 (La Liga
  fold). English keyword rules fail on untranslated Spanish ASR: goal recall 0.8846 → 0.0535 on the
  La Liga fold (60 vs 70 test games; the two ASR variants do not cover an identical game set).
- The report's "Stable across folds → generalizes" line did not hold up: fold stability was one of the
  gates that failed in the later V2 analysis.

Reports:
[completion](notes/research/SOCCERNET_REAL_ALIGNMENT_COMPLETION.md) ·
[evaluation](notes/research/soccernet_real_alignment_evaluation.md)

#### `commentary-intelligence-research-v1`

Commentary source and rights audit, a canonical commentary record contract, and a fail-closed
live-eligibility gate. The tooling was tested on synthetic data only.

- **Verdict — no source is live-eligible.** None of the 8 assessed commentary sources passed the gate
  (no publication timestamps). Only SoccerNet-Echoes (CC BY 4.0) was usable, and only historically.

Reports:
[completion](notes/research/COMMENTARY_INTELLIGENCE_RESEARCH_COMPLETION.md) ·
[live-readiness gate](notes/research/commentary_live_readiness_gate.md)

#### `shadow-offline-hardening-v1`

An offline sprint run beside the live collector: a model-identity namespace (separating pre-match
`M2` = market from in-play `M2` = Poisson), 2022 replay regression tests, simulator checks, a
context-feature contract, and a deterministic scorecard with the Tier A/B/C sample-size gate.

- **Verdict — readiness only.** 48/48 cached 2022 group matches reconcile exactly; 16 knockout matches
  are `not_cached`. The prospective pool at the time had 0 finalized eligible matches (Tier A,
  informational).
- Also in this range, untagged commit `dc73318`: the scheduled 2026 shadow collector went live. The
  defects later documented as E2 (odds key mismatch) and E3 (score step never refreshed results)
  entered with that commit. E3 was found on 2026-06-29; E2 only during the 2026-09-20 public-release
  review.

Reports:
[completion](notes/research/OFFLINE_HARDENING_COMPLETION_REPORT.md) ·
[collector activation](notes/research/PROSPECTIVE_COLLECTION_ACTIVATION_REPORT.md)

### 2026-06-22

#### `v1-5-prospective-readiness`

The prospective operations plane: an immutable first-write-wins ledger, a frozen in-play predictor
with a leakage guard, a read-only quota-aware API-Football adapter, scheduler materials (not
installed at this tag), and the v2 re-freeze of the prospective in-play model from `m2fit_temp` to
plain M2.

- **Verdict — readiness only; no model claim.** Dry-run verified; clean pool of 28 not-started
  fixtures.
- **No frozen in-play model was ever scored prospectively** (the queue stayed pending). The in-play
  freeze is governance machinery, not an evaluated result. The v1 freeze manifest is kept as an
  immutable record.
- The provider package named a lowest-cost vendor from public pricing pages. Nothing was purchased,
  and the later 2026-06-26 decision matrix names no vendor.

Reports:
[completion](notes/research/V1_5_PROSPECTIVE_READINESS_COMPLETION.md) ·
[prospective protocol](notes/research/final_2026_prospective_protocol.md) ·
[freeze manifest v2](notes/research/final_holdout_freeze_manifest_v2.json)

#### `evaluation-reset-event-expansion`

Expanded in-play work to several competitions, then audited its own evaluation (the "evaluation
reset").

- **Verdict — a self-correction plus several nulls.**
- **Selection on test, caught.** Model parameters were always fit on training data only, but the
  "best" in-play model (M2fit_temp) had been crowned after repeatedly viewing 2026 results. Every
  such claim was relabelled `invalid_due_to_model_selection_on_test_set`.
- Nested LOCO rerun on 302 StatsBomb men's internationals (6 tournaments, 5,738 rows, no 2026 data):
  M2fit_temp and the xG variants were never selected; plain M2 was chosen in 4/6 folds and M5 in 2/6.
  Nested RPS 0.1487 vs always-M2 0.1474. Nested vs M1: dRPS −0.0042, CI [−0.0083, +0.0002] — not
  significant.
- Six xG feature families fixed before testing, 302 matches: all non-significant (all-xG RPS 0.1531
  vs 0.1528).
- Earlier in the same range, on 151 group matches from 5 tournaments (LOCO), the unfitted M2 was
  ahead of the fitted M1 on 5/5 held-out competitions: RPS 0.127 vs 0.142, dRPS −0.0145
  [−0.021, −0.008]. **This was not confirmed at significance** on the larger, overlapping 302-match
  set. Market-anchored M6 vs Elo-anchored M2: no significant difference (dRPS −0.0004
  [−0.008, +0.007]).
- What survived: a score-and-time-aware in-play update does better than a static pre-match forecast.
  On 30 finished 2026 matches (519 rows), pre-specified M1 vs static M0: RPS 0.1478 vs 0.1897. The
  repo labels this "exploratory, NOT pristine"; the magnitude is indicative only.
- Provenance caveat recorded in the multi-competition note: 20 of the 151 matches (10 AFCON, 10 Asian
  Cup) were fetched with a second free API-Football account that the provider then suspended
  mid-fetch. The note states no further free accounts would be created; later corpus work used a
  single paid plan.

Reports:
[completion](notes/research/evaluation_reset_event_expansion_completion.md) ·
[reconciliation](notes/research/inplay_evaluation_reconciliation.md) ·
[nested evaluation](notes/research/inplay_nested_evaluation.md) ·
[status registry](notes/research/inplay_result_status_registry.yaml) ·
[multi-competition results](notes/research/inplay_multicompetition_results.md)

### 2026-06-21

#### `tier-4-research-sprint-1`

First in-play sprint on the 2022 replay: a state dataset (48 matches, 858 decision rows), baselines
M0–M5, leave-one-group-out with a match-level bootstrap.

- **Verdict — no model suitable for a live shadow test.** Only the M5 ensemble was ahead of the
  time+score baseline M1 with match-level significance (dRPS CI [−0.023, −0.004]; one tournament, 48
  matches); M2 had the best point RPS but its CI included zero.
- Goal-within-5-minutes hazard did not beat the base rate (Brier 0.1148 vs 0.1126). Next-goal-team
  modestly did (log-loss 1.032 vs 1.084; no significance test).

Report: [completion](notes/research/tier_4_sprint_1_completion.md)

#### `event-replay-2022-validated`

Fixed the own-goal inversion bug found by replay checks. (In this tag name "validated" means only
that the replay reconciles with the provider's final scores.)

- **Verdict — release gate PASS, research-ready only.** 48/48 cached 2022 group matches reconcile
  exactly (previously 47/48).
- API-Football's `team` field on an own goal is already the beneficiary. Fixture 855767
  (Canada 1–2 Morocco) had been derived as 0–3. The fix is a versioned, provider-aware
  event-semantics layer that fails closed for unknown providers.
- The same bug resurfaced in a second module five days later (see
  `api-football-historical-corpus-v1`).

Reports:
[release gate](notes/research/event_replay_2022_release_gate.md) ·
[remediation](notes/research/event_replay_2022_remediation.md)

#### `shadow-session-20260621-closed`

Closed the first live shadow session: 5 hours, 7 of 30 odds credits, 372 strictly pre-kickoff
prediction rows for the frozen pre-match models M1–M5.

- **Verdict — descriptive only, n=1.** Exactly one predicted match finished inside the session. That
  match is one of the 34 fixtures in the later prospective benchmark, not extra evidence.
- The session's data-quality audit found the own-goal bug and blocked the 2022 replay for training
  until it was fixed (next entry up).
- Also in this range — a 20-experiment autoresearch cycle (one cycle, one session): every variant was
  rejected under the pre-set 0.002 threshold and `candidate.py` was left unchanged.
- Also in this range — a research-only Poisson / Dixon-Coles scoreline layer. It did not improve 1X2
  (dev composite 0.3582 / 0.3566 vs B1 0.3553; lower is better). Its value is the extra outputs
  (scoreline and totals probabilities), not sharper 1X2.
- Also in this range — the 2022 World Cup retrospective market study (48 group matches, real
  pre-kickoff no-vig odds about 94 minutes before kickoff). The market alone had the best point RPS /
  log-loss (0.2244 / 1.0366 vs B1 0.2435 / 1.1217), but its CI vs B1 includes zero (dRPS −0.0191
  [−0.046, +0.005]). Of three predeclared fixed blends, 75/25 B1/market was significant on RPS (CI
  [−0.013, −0.0005]) and log-loss. The note calls this "suggestive": one tournament, no multiplicity
  correction, no weight selected, nothing promoted. The 2026 prospective benchmark (n=34, against an
  early-line market; see E2) found no separation.

Reports:
[closure](notes/research/shadow_session_20260621_closure.md) ·
[scorecard](notes/research/shadow_session_20260621_scorecard.md) ·
[2022 market study](notes/research/market_shadow_evaluation_2022.md) ·
[autoresearch report](notes/research/OVERNIGHT_FINAL_REPORT.md) ·
[scoreline layer](notes/research/cycle_2_scoreline_inplay.md)

#### `data-readiness-gate-1`

A read-only source-readiness audit, live data contracts (a raw provenance envelope plus 17 normalized
schemas), an event reconciliation policy and ingestion scaffolding.

- **Verdict — readiness only; no model touched.** The Odds API, football-data.org and Open-Meteo
  responded. The API-Football key was rejected on both auth paths at this point.
- No timestamp-valid odds exist before 2020-06, so a market model cannot be backtested on the dev
  folds. That path is blocked, not failed.

Reports:
[gate report](notes/research/data_enrichment_gate_1.md) ·
[source readiness audit](notes/research/source_readiness_audit.md)

#### `approved-b1-runtime`

The Tier-2 baseline gate (B0–B7), a model-state reconciliation audit, the approved-model registry,
runtime routing through B1, and a registry-bound check in the paper-trade RiskGate.

- **Verdict — B1 (ternary Elo, no fitted parameters) approved as the only runtime model, because
  nothing robustly beat it, not because it is strong.** Paired bootstrap on 144 pooled dev matches
  (folds 2010/2014/2018), 2000 resamples: B7 vs B1 dRPS +0.0011, 95% CI [−0.0059, +0.0077]. Only B0
  (frequency prior) and B2 (FIFA-only) differed significantly, and they were worse.
- The Poisson (B4) and Dixon-Coles (B5) baselines were not distinguishable from B1 on the same test:
  dRPS +0.0006 [−0.0050, +0.0061] and +0.0008 [−0.0048, +0.0066].
- Scope: this is about the pooled dev folds. On the single-read 2022 gate B1 ranked 5th of 9 by
  composite.
- **Release-gate contamination, caught.** The V8 candidate's architecture and 0.85 blend weight had
  been chosen with sweeps that touched the 2022 gate. Selection was re-established on the dev folds
  only, with 2022 read once. V8 and the market-anchored blend stayed experimental, with no runtime
  authority.
- "Fail-closed" describes the forecaster path, not the whole trading path: the RiskGate's
  approved-model check applies only when a trade intent carries a `model_id`, which is an optional
  field. The trading scaffold is dormant and triple-gated, and was never armed or given credentials.
- Erratum: the 2026 prequential "V8 worse than B1" figures quoted in this milestone's notes are a bug
  artifact (E1). Corrected, the two are tied.

Reports:
[baseline gate](notes/research/tier_2_baseline_gate.md) ·
[approved model registry](notes/research/approved_model_registry.md) ·
[runtime governance](notes/research/runtime_model_governance.md) ·
[reconciliation audit](notes/research/model_state_reconciliation.md) ·
[existing-work audit](notes/research/tier_2_existing_work_audit.md)

### 2026-06-20

#### `tier-1-baseline-recorded`

A documentation-only tag that records the Tier 1 baseline commit, the `.env` / secret-hygiene checks
and the list of data deliberately excluded from git.

- **Verdict — record only.**

Report: [baseline commit note](notes/research/tier_1_baseline_commit.md)

#### `tier-1-complete`

The first git commit: the pre-git package plus Tier 1 — a 369-match World Cup group-stage table
(1998–2026; the table itself is gitignored), a strict-before Elo timeline, a content-hashed provenance
registry, leakage / quality / simulator tests, and an official FIFA 2026 Article-13 tiebreak engine.

- **Verdict — foundation complete, with two leaks caught.** Cross-tournament group-state accumulation
  and a simultaneous-final-matchday leak were found and fixed. The first evaluator score computed on
  the corrupted table (composite 0.4253) was later declared invalid in the reconciliation audit.
- The tiebreak engine (head-to-head first, recursive, 12 groups, best eight thirds) changed
  advancement probabilities for a handful of teams (9 teams moved by more than 0.01; max 0.107; mean
  change 0.0064). The rule order came from FIFA.com plus press coverage, not an archived regulations
  PDF.
- The data layer is leakage-tested: a test suite plus one read-only review by the lab's own AI agent
  (the note's "independent review" is that internal review). It is not a guarantee.
- Erratum: this tier's notes repeat an early retrospective claim of an advantage over the bookmaker
  market. It had no confidence intervals, was later reclassified as auxiliary and was not confirmed
  prospectively (E4).

Reports:
[completion](notes/research/tier_1_completion.md) ·
[remediation](notes/research/tier_1_remediation.md) ·
[reconciliation audit](notes/research/model_state_reconciliation.md)

---

## Pre-git package history (historical)

Condensed from the changelog that shipped with the original v0.1.x package, before the repository was
under git. The original carried **no dates**, so none are given, and the entries keep the order in
which that file listed them. Its test counts were stale and are omitted. The package metadata read
0.2.0 from the first git commit until 0.3.0; the original changelog never recorded a 0.2.0 entry, and
none is reconstructed here.

These entries describe a generic draw-forecasting toolkit. None of it is an evaluated result. The
how-to for this toolkit is preserved in [docs/TOOLKIT_USAGE.md](docs/TOOLKIT_USAGE.md); see also
[docs/history/VERSION.md](docs/history/VERSION.md) and
[docs/history/BUILD_VALIDATION.md](docs/history/BUILD_VALIDATION.md), both bannered as superseded or
historical.

### Probability documentation + risk release (unversioned)

- Added the documentation suite under `docs/` and `src/wcdrawlab/risk.py`.
- Added uncertainty columns to every prediction: standard deviations, probability standard errors,
  Beta-approximation intervals, entropy / confidence / risk-band reporting.
- Added theoretical draw-bet expected-value and standard-deviation columns to the market scan. These
  are arithmetic on supplied odds, not a tested strategy and not betting advice.

### 0.1.3 - Live after-game update workflow

- Added `src/wcdrawlab/live.py` (event-driven after-match result ingestion) and the
  `wcdrawlab predict-live` and `wcdrawlab update-after-match` commands, which insert final scores and
  recompute standings, advancement probabilities and risk columns.
- Added [docs/PREDICTION_TARGETS_AND_UPDATE_CADENCE.md](docs/PREDICTION_TARGETS_AND_UPDATE_CADENCE.md),
  [docs/AFTER_GAME_UPDATE_WORKFLOW.md](docs/AFTER_GAME_UPDATE_WORKFLOW.md) and
  `examples/run_after_match_update.py`.
- Note from the original: the live model used a conservative default blend when no trained
  historical model was supplied.

### Final handoff package

- Added the AI-agent handoff entry point and first-session prompt (now under
  [docs/ai-workflow/](docs/ai-workflow/README.md)) and
  [docs/ACCOUNT_AND_API_SETUP.md](docs/ACCOUNT_AND_API_SETUP.md) with `.env` handling rules.
- Added placeholder directories for processed research data, research outputs and pending data
  requests.
