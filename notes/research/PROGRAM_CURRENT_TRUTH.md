# Program Current Truth (consolidated, 2026-06-21)

Single reconciled snapshot of what actually exists. Supersedes scattered prior notes for orientation.

## Runtime-approved (production)
- **B1 / ternary-Elo (r=0.4)** is the SOLE approved pre-match 1X2 model (`configs/approved_models.yaml`,
  `approved_model_registry.md`, tag `approved-b1-runtime`). Registry-bound risk gate; paper-only.

## Research-only / experimental (NOT runtime)
- Pre-match: V8 candidate (`candidate.py`, unchanged), scoreline (Poisson/Dixon-Coles), market blends
  M2–M5. None beat B1 with significance; none promoted.
- In-play: M0–M5 (`research/inplay_models/`), in-play engine, replay (`inplay_replay.py`,
  `event_semantics.py`). Research-only.

## Datasets that exist (gitignored; reproducible from tracked builders)
- `research_modeling_table.csv` (369 WC group matches 1998–2026).
- `elo_history.csv`, `fifa_rankings.csv`, market_features_2022/2026, intl odds 2020–26.
- `data/raw/api_football_2022_worldcup/` (48 group fixtures' events, validated 48/48).
- `inplay_state_2022_group_stage.parquet` (858 decision rows).
- Live-2026 shadow predictions + closed supervisor session.

## Datasets MISSING (the binding constraints)
- Multi-competition historical event data (only 2022 WC events on hand).
- xG / shots / corners / **lineups / on-pitch player IDs / positions** (absent from the API-Football
  free-tier events).
- Timestamp-valid pre-2020 WC odds (no clean source exists).
- Sufficient red-card / next-event positives (sparse on 2022).

## Providers — what actually works
- **football-data.org**: WORKS (auth; 2026 results/standings authoritative; ~10 req/min free).
- **The Odds API**: WORKS (~13,090 credits remaining; live + 2020-06→ historical odds).
- **Open-Meteo**: WORKS (keyless).
- **API-Football (direct, api-sports.io)**: AUTH WORKS; key is 32-hex direct format; **free plan =
  seasons 2022–2024 only (NO 2026)**, 100 req/day, 10 req/min.
- Kalshi: credentials MISSING; live trading false (paper).

## APIs blocked / limited
- API-Football 2026 live (free-tier season gate) → needs paid Pro for live lineups/events.
- Historical pre-2020 odds → no legal/open source.
- StatsBomb/Opta/Sportradar event+xG → need sign-off / paid.

## Reproducible results
- B1 baseline + B0–B7 (tier-2 gate); official composite; 2022 market shadow; 2022 replay 48/48;
  in-play LOGO (M2 best W/D/L, M5 beats M1 significantly, M3 fails vs base rate). All re-runnable.

## Obsolete / superseded
- Pre-fix evaluator run (0.4253) — corrupted table; obsolete. Buggy own-goal inversion — fixed
  (`event-replay-2022-validated`).

## Exact next dependency chain
Multi-competition event volume + xG/lineups (Phase C/D player & in-play planes) → gated on approving a
data source (`tier4_event_xg_feed.yaml`, `statsbomb_open_data.yaml`, or API-Football Pro / quota
authorization). Until then, only foundation/registry/collector-design work is unblocked.
