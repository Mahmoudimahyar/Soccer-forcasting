# Model-State Reconciliation Audit (forensic) — 2026-06-21

Read-only audit. No model code, data builders, configs, providers, trading, risk, scraping,
`.env`, or Git history were modified. `git status` shows no tracked modifications (rebuilds only
regenerated gitignored artifacts). `pytest -q` → **61 passed**.

## The apparent inconsistency — resolved
There is **no contradiction**. Git was initialized *after* all cycle-1–6 work (including the V8
edits to `candidate.py`). So V8 is **baked into the first commit** `e78cde4` (`tier-1-complete`),
not a post-baseline change. Therefore both statements are simultaneously true:
- "V8 was written into candidate.py" — yes, during the pre-git exploratory phase.
- "candidate.py is unchanged since tier-1-complete" — yes, because `git diff tier-1-complete..HEAD
  -- candidate.py` is **empty** (V8 was already in the baseline commit).
- "B1 is the approved baseline" — a **governance conclusion** from the Tier-2 gate (no candidate
  beats B1 with significance), **not** a statement that candidate.py contains B1. candidate.py
  still contains V8.

## Git forensics (recorded)
```
git branch:        master (b60ccc6), * tier-2-pre-match (0cc9f2d = HEAD)
git tags:          tier-1-complete -> e78cde4 ; tier-1-baseline-recorded -> b60ccc6
git tag --contains HEAD: (none)   # HEAD is ahead of both tags
graph:  0cc9f2d (HEAD tier-2) -> b60ccc6 (master, tier-1-baseline-recorded) -> e78cde4 (tier-1-complete)
git log --follow -- candidate.py:   e78cde4   (ONE commit only; no pre-V8 history -> V8 pre-dates git)
git diff tier-1-complete..HEAD -- candidate.py:        (empty -> unchanged)
git diff tier-1-complete..HEAD -- configs/research.yaml:(empty -> unchanged)
git diff --name-status tier-1-complete..HEAD:  A notes/research/tier_1_baseline_commit.md,
   A notes/research/tier_2_{baseline_gate,data_readiness,existing_work_audit}.md, A scripts/tier2_baselines.py
git diff tier-1-complete..HEAD -- tests/:      (empty -> all tests already in baseline)
```
No amend / squash / force / rewrite. Linear history.

## Shared repo provenance (HEAD = 0cc9f2d)
- Code SHA-256 (16): candidate.py `bad84a7d` · build_research_table.py `4bee604f` ·
  runner.py `39ce5eb7` · evaluate_baselines.py `5b486448` · tier2_baselines.py `c4b36b8c` ·
  official_standings.py `efbcec26`.
- Research table: **content-reproducible** (sorted rows+cols identical across rebuilds; byte hash
  varies only by Python hash-seed row ordering — deterministic under fixed `PYTHONHASHSEED`).
- Raw snapshots (sha256-16 / retrieved): martj42 `64d75097` / 2026-06-20; jfjelstul matches
  `037f7187`; football-data 2026 `e78a688b`; Odds API 2026-live `07b61eec`; Odds API historical
  `a258da56`; Dato-Futbol FIFA `d4f4d8d3`; Transfermarkt `e865db6c`; Wikipedia 2026 `e73a1780`.
  (Full registry: `data/processed/source_provenance.json`.)

## Reconciliation table (materially different model states)
| State | Where | Model / features | Folds & protocol | RPS | LogLoss | drawBrier | drawCal | Bootstrap vs B1 | Status |
|---|---|---|---|---|---|---|---|---|---|
| **V8** (`candidate.py`, sha bad84a7d) | tracked, in e78cde4=HEAD | std logit (strength+group-state, C=0.5, scaler) **+0.85 ternary-Elo blend** | runner folds 2018/2022/2026-MD1; 2026-MD1 locked | 0.2095¹ | 1.0396¹ | 0.1969¹ | 0.1021¹ | n/a (is the candidate) | **experimental** (autoresearch surface; not runtime-approved) |
| **B1 Elo** | tracked `models/baselines.py` | ternary-Elo(r=0.4) on elo_delta | dev 2010/14/18 + gate 2022 (once) + 2026-MD1 locked | 0.1901² | 0.9391² | — | — | baseline | **APPROVED baseline** |
| B7_nomarket | tracked `tier2_baselines.py` | blend B1+B5+logit + train-only Platt draw cal | dev/gate/locked | 0.1911² | 0.9464² | — | — | dRPS **+0.0011 [−0.0059,+0.0077]** (tie) | experimental (not > B1) |
| B6 market / B7_market | tracked; odds only 2022 | no-vig consensus / market+ensemble | **2022 only** | 0.2244³ | 1.0366³ | — | 0.0916³ | not comparable (subset) | **unavailable** cross-fold (no pre-2020 odds) |
| Market-anchored 2026 forecast | tracked `market_anchored_forecast.py` | 0.6·market + 0.4·Elo (live odds) | live 2026 upcoming (prospective) | — | — | — | — | n/a (not backtested across folds) | **experimental forecast-aid** (current live generator) |
| Intl beat-market result | notes cycles 4–5 + aux dataset | market+Elo blend on Euro/Copa/NL 2021–25 | temporal CV (NOT WC folds) | — | — | — | — | beats market on aux set | **historical/auxiliary** (not a WC baseline) |
| Pre-fix evaluator run (composite 0.4253) | notes (early) | V8 on **buggy** cross-tournament group-state table | superseded | — | — | — | — | — | **OBSOLETE** |

¹ official evaluator (runner.py) summary mean over its 3 folds (reproduced exactly: composite 0.39841).
² Tier-2 DEV-mean (reproduced exactly). ³ 2022 gate single read (reproduced exactly).

## Reproducibility classification (each documented claim)
| Claim / artifact | Status |
|---|---|
| Research table builds from tracked code + approved snapshots | **reproduced** (content-identical; byte order hash-seed dependent) |
| Official evaluator composite ≈ 0.398 (V8) | **reproduced exactly** (0.3984059336783079) |
| Tier-2 B0–B7 dev/gate/locked metrics | **reproduced exactly** (B1 dev 0.3553; B7_nomarket 0.3590; gate/locked match) |
| Paired bootstrap (B7 vs B1 dRPS +0.0011, CI incl. 0; B0/B2 worse) | **reproduced exactly** (seeded rng) |
| Prequential 2026 — B1 (RPS 0.174, LL 0.958, drawCal 0.178) | **reproduced exactly** |
| Prequential 2026 — V8 (was RPS 0.221/LL 1.082/drawCal 0.022) | **reproduced within tolerance** (now 0.225/1.092/0.004; small drift from a 2026 source refresh; B1>V8 ordering unchanged) |
| Cycle 1–6 headline metrics (pre-git exploratory) | **historical**; superseded by the Tier-2 suite for any decision |
| Pre-fix evaluator composite 0.4253 | **invalid/obsolete** (computed on the corrupted group-state table) |
| Intl beat-market (cycles 4–5) | **valid but auxiliary** (different dataset, not WC folds) |

## The seven questions — plainly answered
1. **Did V8 exist in Git history?** Yes — it is the content of `candidate.py` committed at
   `e78cde4`. (Written pre-git, so its first and only commit already contains V8.)
2. **Was V8 reverted?** No. `candidate.py` still *is* V8 (`ELO_BLEND_WEIGHT=0.85`), byte-identical
   to its committed state and to HEAD. Never reverted.
3. **What exact model is currently used for forecasts?** The live 2026 headline forecast is produced
   by `market_anchored_forecast.py` = **0.6·market + 0.4·ternary-Elo** where live odds exist (else
   model fallback). The fixed evaluator (`runner.py`) uses `candidate.py` = **V8** for autoresearch
   scoring. **Neither is "B1" — this is the ambiguity the registry now resolves.**
4. **Is B1/Elo genuinely the approved baseline?** Yes, as the **selection baseline**: the Tier-2
   bootstrap shows no candidate beats B1 with significance. It is the bar any model must beat.
5. **Are earlier metrics reproducible?** Yes — B1, the B0–B7 suite, the official composite, and the
   prequential B1 numbers reproduce exactly; V8 prequential reproduces within tolerance.
6. **Which reports are historical only?** Cycle 1–6 notes, baseline_evaluation, forecast/market/
   prequential/beat-market notes are historical records of the pre-git exploratory phase. The
   authoritative numbers for decisions are the **Tier-2 suite** (`outputs/research/tier2/`) +
   `tier_2_baseline_gate.md`. The pre-fix evaluator run is obsolete.
7. **Enough evidence to begin Tier-2 data enrichment?** Yes — the baseline gate is reproducible,
   B1 is the approved baseline, and the bottleneck is data (pre-2020 odds, fresher strength,
   lineups/xG). Enrichment is justified, pending your explicit approval.

## Forecast ledger reconciliation
- `data/processed/forecast_ledger.csv` (sha256-16 `aa67b462`): **39 frozen pre-kickoff forecasts**
  (15 MD2 + 24 MD3), single snapshot `2026-06-20`, **unique match_id** (one immutable row per match,
  first-write-wins) with `model_*` (V8-era ensemble), `mkt_*` (market consensus), and `blend_*`
  (0.6·market+0.4·Elo) columns. Point-in-time integrity intact.
- **Scorable now: 0/39** — the ledger's matches are not present in the frozen finished-results cache
  (`results_2026_footballdata.csv`, 33 finished = MD1 + early MD2 retrieved 2026-06-20). Scoring
  these requires a results refresh, which is **deliberately not performed** (no new data acquisition
  under this audit). The ledger is a valid forward record awaiting completion.
- The ledger stores the **market-anchored blend** (experimental forecast-aid), not B1; this is
  consistent with the registry's no-ambiguity statement.

See `notes/research/approved_model_registry.md` for the governance decision.
