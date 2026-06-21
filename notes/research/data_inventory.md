# Data Inventory — World Cup Forecasting Lab

Audit date: 2026-06-20. Sources audited via `scripts/audit_public_data.py` (read-only).
All counts below are measured directly from the downloaded files, not assumed.

---

## 1. martj42/international_results  (`data/raw/international_results.csv`)

- **Source URL:** https://raw.githubusercontent.com/martj42/international_results/master/results.csv
- **License/attribution:** martj42/international_results, released **CC0** (public domain) per
  the upstream repo. Attribution retained here as good practice. No account required.
- **Coverage:** 49,477 rows, **1872-11-30 → 2026-06-27** (future rows are scheduled fixtures
  with empty scores). 200 distinct competitions.
- **Columns:** `date, home_team, away_team, home_score, away_score, tournament, city, country, neutral`.
- **World Cup coverage:** 1,036 rows tagged `tournament == "FIFA World Cup"`.
  Group+knockout: 64 matches each for 2010/2014/2018/2022; **72 for 2026** (48-team group
  stage = 72 group matches; no knockouts yet).
- **2026 result freshness:** scores present **through 2026-06-18** (28 matches: all 24 of
  Matchday 1 + the first 4 of Matchday 2). Matches dated 2026-06-19 onward have NaN scores.
  ⚠️ Upstream snapshot lags the calendar by ~2 days (today is 2026-06-20).
- **Quality findings:** 0 exact duplicate rows; 2 near-dupes on `(date, home, away)`; 44 rows
  with null scores (scheduled/abandoned); all dates parse. Team names use martj42 spelling
  (e.g., `South Korea`, `Czech Republic`, `Curaçao`, `Bosnia and Herzegovina`) — must be
  canonicalized (see §6).
- **Missing fields:** **no group, stage, or matchday labels** for any tournament; no kickoff
  time-of-day (date only); no ratings; no odds.
- **Intended use:** (a) build the internal time-safe **Elo** from the full 1872→ history;
  (b) supply **actual 2026 results** (the only free source with 2026 scores).
- **Leakage risks:** date-only timestamps mean within-day ordering is ambiguous — handled by
  treating Elo as "as of start of match day" and never using same-match result. Future
  scheduled rows (NaN scores) must be excluded from training/Elo.
- **Usability:** Training ✅ · Validation ✅ · Locked 2026 test ✅ (results only) · Live runtime ⚠️
  (lags real time; needs a faster live source — API-Football — for same-day updates).

## 2. jfjelstul/worldcup — matches  (`data/raw/jf_worldcup_matches.csv`)

- **Source URL:** https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/matches.csv
- **License/attribution:** jfjelstul/worldcup, **MIT License**. No account required.
- **Coverage:** 1,248 rows, Men's + Women's World Cups **1930 → 2022**. Men's group stages:
  48 group matches each for 1998, 2002, 2006, 2010, 2014, 2018, **2022**. (Women's tournaments
  also present — filter to Men's via `tournament_name` containing "Men's".)
- **Columns (37):** includes `tournament_id, tournament_name, stage_name, group_name,
  group_stage, knockout_stage, match_date, home_team_name, away_team_name, home_team_score,
  away_team_score, result, home_team_win, away_team_win, draw, penalty_shootout, ...`.
- **Why this dataset is essential:** it is the **only free source with official group labels**,
  and it covers **2010, 2014, 2018, AND 2022** — exactly the development + release-gate folds.
- **Missing fields:** **no 2026** (last tournament is 2022); no ratings; no odds; `match_time`
  present but unreliable for older tournaments.
- **Quality findings:** `group_name` includes `"not applicable"` for knockout rows (filter on
  `group_stage == 1`). Team names use jfjelstul spelling — canonicalize against martj42.
- **Intended use:** authoritative **group/stage/matchday structure and regulation-time results**
  for 2010–2022 folds.
- **Leakage risks:** none structural; it is historical. Must still derive features time-safely.
- **Usability:** Training ✅ · Validation ✅ (2010/2014/2018) · Release gate ✅ (2022) ·
  Locked 2026 ❌ (not covered) · Live ❌.

## 3. jfjelstul/worldcup — tournaments  (`data/raw/jf_worldcup_tournaments.csv`)

- **Source URL:** https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/tournaments.csv
- **License:** MIT. **Coverage:** 30 tournaments 1930–2022 with `year, host_country,
  count_teams, group_stage, start_date, end_date, winner, host_won`.
- **Intended use:** host-country lookup (for host/neutral feature on historical folds),
  tournament metadata. **Leakage:** `winner`/`host_won` are post-tournament — never use as features.
- **Usability:** metadata join only.

## 4. Seed 2026 snapshot  (`data/seed/worldcup_2026_seed_matches.csv`)

- **Source/provenance:** assembled in-repo from public news snippets (Reuters / SBNation /
  Guardian, "Jun 18 2026"), labeled per row in `data_source`. **Not betting-grade.**
- **Coverage:** 29 of 72 group matches, groups **A–L** with official **group + matchday**
  labels. Several scores intentionally blank (e.g., Australia–Turkey, Sweden–Tunisia,
  Uzbekistan–Colombia) where the snippet lacked the score.
- **Intended use:** the **anchor for 2026 group/matchday labels** (martj42 has none). The full
  12×4 group structure is reconstructed by clustering the 72 martj42 fixtures into round-robin
  components and labeling them A–L using these seed anchors (see §7).
- **Leakage risks:** low for structure (group assignment is pre-tournament); scores must come
  from martj42, not from this partial/stale snapshot.
- **Usability:** 2026 structure ✅ (anchor) · results ⚠️ (use martj42 instead).

## 5. Seed demo ratings & odds  (`data/seed/seed_ratings_2026.csv`, `sample_odds_2026.csv`)

- **seed_ratings_2026.csv:** 42 teams, single `rating_date = 2026-06-10`, column `elo`,
  `source = seed_demo`. **These are approximate demo Elo values, NOT FIFA points and NOT a
  real Elo history.** Use only for the live-demo path; the backtest computes its own Elo.
- **sample_odds_2026.csv:** 29 rows, `book = seed_demo_not_real_odds`. **Synthetic, not real
  market odds.** Cannot be used for B6 / CLV. Mirrored under `data/live/`.
- **Usability:** demo/pipeline-smoke only. ❌ for training, validation, or any edge scan.

## 6. Team-name reconciliation

`src/wcdrawlab/ingest.py::TEAM_ALIASES` already maps several variants (USA→United States,
Czech Republic→Czechia, South Korea→Korea Republic, Bosnia and Herzegovina→Bosnia,
Curaçao→Curacao, DR Congo→Congo DR, Türkiye→Turkey). The research-table builder applies
`canonical_team_name` to **all** sources so jfjelstul, martj42, and the seed agree.
Spot-check confirmed the 2026 squads (48 teams) all canonicalize consistently.

## 7. 2026 group-stage reconstructability — CONFIRMED

The 72 martj42 2026 fixtures form 12 disjoint round-robin components of 4 teams (6 matches
each). Each component is labeled A–L using the seed file's explicit group assignments as
anchors; the 2–3 teams missing from a seed group are recovered from the component's other
fixtures (e.g., Group E = Germany, Curaçao, Ecuador, Ivory Coast from the Germany–Curaçao,
Ivory Coast–Ecuador, Ecuador–Curaçao, Germany–Ivory Coast pairings). Matchday (1/2/3) is the
chronological round within each group. This reconstruction is reproducible from data + the
seed anchors and is verified by the builder/tests in the next phase.

## 8. Gaps requiring a new data source (data requests to follow)

| Gap | Impact | Free option? | Account/env |
|---|---|---|---|
| Timestamped multi-book pre-match odds + totals | Enables B6, market features, CLV | The Odds API free tier | `ODDS_API_KEY` |
| FIFA ranking history (points/rank, release-dated) | Enables B2 + release-normalized rank feature | Limited; needs sanctioned source | (data request) |
| Live same-day results / lineups / events / xG | Faster live updates, in-play, availability features | API-Football (paid tiers) | `API_FOOTBALL_KEY` |

## 8b. Live sources INTEGRATED (2026-06-20, keys supplied)

- **The Odds API** (`ODDS_API_KEY`): sport `soccer_fifa_world_cup`, 40 events, up to 48 books,
  h2h+totals. Raw: `data/raw/odds/odds_fifa_world_cup_2026-06-20.json`. Normalized no-vig
  consensus: `data/processed/market_features_2026.csv` (39/39 upcoming matched). **B6 live**
  for 2026 (prospective only; no free historical odds → not in backtest folds).
- **football-data.org** (`FOOTBALL_DATA_KEY`): authoritative 2026 groups/matchday + freshest
  results (33 finished). `data/processed/results_2026_footballdata.csv`. Now the 2026 source in
  the build; **validated 12/12 groups vs the reconstruction**. Elo supplemented with 4 fresher results.
- **API-Football** (`API_FOOTBALL_KEY`): BLOCKED — key rejected by the adapter's direct host
  (RapidAPI-style key). Not on the critical path. See `data_requests/pending/api_football.yaml`.
- **The Odds API HISTORICAL** (paid 20K plan, from 2026-06-20): pulled pre-kickoff no-vig
  consensus for all 48 **2022** WC group matches (`data/processed/market_features_2022.csv`,
  32-35 books). History starts 2020-06 so **2018 is unavailable** (only 2022 is backtestable).
  Backtest: market beats all models; drove cycle-3 fix. `scripts/fetch_historical_odds_2022.py`.
- See `notes/research/live_integration_2026.md` and `20260620_cycle_3.md` for the write-ups.

## 9. Source eligibility summary

| Dataset | Train | Validate (2010/14/18) | Release gate (2022) | Locked (2026 MD1) | Live runtime |
|---|---|---|---|---|---|
| martj42 results | ✅ | ✅ | ✅ | ✅ (results) | ⚠️ lag |
| jfjelstul matches | ✅ | ✅ | ✅ | ❌ | ❌ |
| jfjelstul tournaments | meta | meta | meta | ❌ | ❌ |
| seed 2026 matches | ❌ | ❌ | ❌ | structure anchor | demo |
| seed ratings/odds | ❌ | ❌ | ❌ | ❌ | demo only |
