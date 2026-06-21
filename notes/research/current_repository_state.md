# Current Repository State (Tier-1 intake) — 2026-06-20

Snapshot before continuing Tier-1 work. Commands run: `git status`, `pytest -q`,
`find data -maxdepth 3 -type f`, `find outputs -maxdepth 3 -type f`, safe env audit.

## Version control
- **Not a git repository** (`git status` → fatal). No commits, no uncommitted-change list.
  "Tag the exact data/model version" is satisfied via a manifest (`VERSION.md`) instead of a git tag.

## Tests
- `pytest -q` → **45 passed** (27 original + 18 added this session: leakage + table-quality).
- Leakage suite: `tests/test_research_leakage.py`, `tests/test_research_table_quality.py`.
- **Gap:** no explicit deterministic test for the 2026 best-third simulator (added in this Tier-1 pass).

## Completed datasets (data/processed/)
- `research_modeling_table.csv` — canonical leakage-safe table, **369 played WC group matches 1998–2026**
  (1998–2022 jfjelstul + 2026 football-data.org; 24 MD1 + 9 MD2 played for 2026).
- `forecast_targets_2026.csv` — 39 upcoming 2026 group matches (pre-match features, no result).
- `elo_history.csv` — time-safe Elo trajectory from 49,482 martj42 internationals (+FD 2026 supplement).
- `groups_2026.csv` — reconstructed/authoritative 12 groups of 4 (validated 12/12 vs football-data).
- `fifa_rankings.csv` — open FIFA ranking history (1992–2024) normalized.
- `market_features_2026.csv` — live 2026 no-vig consensus (The Odds API, 39 matches).
- `market_features_2022.csv` — 2022 WC pre-kickoff no-vig consensus (historical odds).
- `intl_market_dataset.csv` / `intl_odds_sharp.csv` / `intl_market_sharp.csv` — 341 international
  matches 2021–2025 with consensus + closing + Pinnacle odds + Elo + outcome (beat-market test set).
- `squad_features_tm.csv` — Transfermarkt starting-XI value/age/league features (128 tournament games).
- `forecast_ledger.csv` — frozen pre-kickoff forecasts (model/market/blend) for prospective scoring.
- Raw (data/raw/): martj42 international_results, jfjelstul matches/tournaments, FIFA (Dato-Futbol),
  football-data 2026 JSON, odds snapshot JSON, Transfermarkt duckdb (206MB).

## Completed historical folds (fixed evaluator + baselines)
- Dev folds (2010/2014/2018), release gate (2022), locked transfer (2026 MD1) — all run.
- Baselines B0–B7 evaluated: `outputs/research/baselines/` (B6 market now real; B2 FIFA real).

## Existing baseline + model results
- Fixed evaluator: `outputs/research/fold_metrics.csv`, `latest_result.json` (summary composite ≈ 0.398).
- **Active accepted model:** `src/wcdrawlab/research/candidate.py` — standardized logit on
  strength + group-state, **blended 0.85 with ternary-Elo** (cycles 1 & 3). Now Elo-grade.
- **Validated headline finding:** market + ~0.4·Elo blend beats the no-vig market AND Pinnacle's
  closing line by ~4–7% RPS out-of-sample (cycles 4–5). Negative results documented: FIFA rank,
  squad value/age/league, Elo importance-weighting (all redundant/no gain).

## Existing 2026 predictions
- `outputs/research/forecasts/forecast_2026_market_anchored.csv` — headline market+Elo blend (39 matches).
- `forecast_2026_md2_md3.csv`, `advancement_2026.csv`, `advancement_2026_market.csv`.
- `prequential_2026.csv` (out-of-sample scorecard on finished matches), `prospective_scorecard.csv`.

## Known leakage safeguards
- `feature_available_at <= kickoff`: Elo via `elo_before(strict <date)`; market snapshot ≤ kickoff;
  group state pre-match only.
- Group keys scoped by **(tournament, year)** via `group_uid` (fixed a cross-tournament accumulation bug).
- Final-matchday simultaneity: group aggregates use **strictly-earlier kickoff date** (fixed a leak).
- Fixed evaluator strips forbidden columns (goals/outcome/xg/closing-odds) before the candidate sees data.
- Enforced by 18 leakage/quality tests.

## Open data gaps
- No timestamped **historical** odds before 2020 (The Odds API history starts 2020-06 → 2018 unavailable).
- No free historical **international xG / lineups** (Understat=leagues only; FBref scrape-restricted;
  API-Football key is RapidAPI-type, rejected by the in-repo adapter). TM lineups cover Copa/AFCON/Asian
  Cup but NOT WC/Euro.
- 2026 FIFA tiebreak: simulator uses a **simplified** order (overall GD before head-to-head) — see
  `data/reference/tiebreak_rules_2026.yaml` (official rules stored; H2H not yet implemented).
- Provenance envelope (raw_payload_hash, retrieved_at_utc per record) not historically attached to
  all raw pulls (addressed by `provenance_policy.md` + `source_provenance.json` going forward).

## Current blockers
- **API-Football**: supplied key is RapidAPI-type, rejected by the direct-host adapter (a protected file).
  Needs a direct `dashboard.api-football.com` key. Not on Tier-1 critical path.
- **Kalshi demo** keys MISSING — later/demo only; `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`.

## Active tier
ACTIVE TIER = 1 (data, provenance, leakage foundation). This pass adds: provenance registry +
policy, in-play event schema, official 2026 tiebreak rules with citation, deterministic 2026
simulator test. Then Tier-1 completion report and stop.
