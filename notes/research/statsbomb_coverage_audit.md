# StatsBomb Open Data Coverage Audit (Phase 3, 2026-06-22)

Full catalogue: `data/reference/statsbomb_competition_catalog.csv` (80 competition-seasons). Data provided
by StatsBomb (open data, non-commercial research). Whenever event data exists, StatsBomb ships full
event detail — so shots+xG, cards, subs, lineups, and player IDs are all available; 360 freeze-frames
are a separate flag.

## Headline counts
- **Men's senior international: 12 competition-seasons, 333 matches.**
- **Modern (domain-shift low, season ≥2014): 6 tournaments, 314 matches** — the PRIMARY international
  in-play dataset:
  | comp_id | season_id | competition | season | matches | 360 |
  |---|---|---|---|---|---|
  | 43 | 3 | FIFA World Cup | 2018 | 64 | no |
  | 55 | 43 | UEFA Euro | 2020 | 51 | yes |
  | 43 | 106 | FIFA World Cup | 2022 | 64 | yes |
  | 1267 | 107 | African Cup of Nations | 2023 | 52 | yes |
  | 223 | 282 | Copa America | 2024 | 32 | no |
  | 55 | 282 | UEFA Euro | 2024 | 51 | yes |
- Older men's World Cups (1958–1990): 8 comp-seasons but only ~26 matches total, **domain-shift HIGH**
  (different football era) → catalogued, EXCLUDED from the primary dataset (historical_reference only).
- Club: 63 comp-seasons (big-5 leagues 2015/16 are 377–380 matches each, La Liga has the Messi seasons).
- Women's / youth international: 5 → EXCLUDED from the men's-international transfer target (domain-shift
  high); retained in catalogue for player-state research.

## Selection rules applied (per sprint)
1. **Prioritise men's senior international** → primary `international_only` dataset = the 6 modern
   tournaments above (314 matches).
2. **Club only as a separate auxiliary domain** → never merged with international.
3. **Never mix club and international silently** → distinct datasets; `competition_type` is a mandatory
   row feature in every table.
4. **Club→international transfer is a hypothesis to TEST** (Phase 5), not assumed.
5. **Competition type preserved as a model feature.**
6. **Competition-level holdouts** for all evaluation.

## Download plan (minimal fields, cache/resume, append-only gitignored, provenance)
- **International (primary):** download events + lineups for the 6 modern tournaments (314 matches).
  Extract only what the in-play state needs (goals, cards, subs, shots+xG, lineup availability).
- **Club auxiliary (bounded sample):** download a capped sample from ONE big league (La Liga 2015/16,
  comp 11 / season 27) to test transfer — capped (logged, not silent) because full leagues are 380
  matches each and the auxiliary only needs enough to estimate a transfer direction.
- Old WCs, women's, youth, remaining clubs: catalogued, not downloaded this sprint (low value / high
  domain-shift / volume); feasible later from the same approved repo.

## Suitability summary
- `suit_intl_inplay_transfer = high` only for men's senior international (12). All else `low`.
- `suit_player_state = high` wherever events exist (lineups + player IDs present).
- `domain_shift_risk`: low for modern men's international; high for club / women's / youth / pre-2000 WCs.

This audit + the catalogue satisfy Phase 3. Phase 4 builds the multi-competition in-play datasets from
these selections.
