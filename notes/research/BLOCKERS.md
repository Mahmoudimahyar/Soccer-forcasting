# Research Blockers

## B-1: API-Football — AUTH RESOLVED 2026-06-21 (coverage caveat remains)
- **Status:** **AUTH RESOLVED.** The key now authenticates on the direct host (HTTP 200,
  `errors:[]`, valid Free plan, 100 req/day). It is a 32-char hex **direct API-Sports** key — the
  earlier rejection no longer reproduces (key was corrected). Full detail:
  `notes/research/api_football_diagnostic.md`. **No auth action needed.**
- **Remaining caveat (coverage, not auth):** the **Free** plan is limited (older seasons / subset of
  leagues, 100/day) and may **not** cover the live 2026 World Cup. One low-cost `GET /fixtures?
  league=<WC>&season=2026` check is needed to confirm 2026 coverage (not run — only one diagnostic
  request was authorized).
- **Impact if free tier lacks 2026:** confirmed lineups/injuries/events for 2026 would need a paid
  tier or another licensed feed. **Not on B1's critical path** (results/standings via football-data.org).
- **Next action:** run the single coverage check; if 2026 is excluded, decide on a paid tier.

## B-2: No pre-2020 historical odds (market model only validatable on 2022)
- **Status:** OPEN (data limitation, not an account error). The Odds API historical coverage starts
  2020-06, so the 2018 fold and earlier have no market features and the market-vs-Elo comparison can
  only be run on 2022 + post-2020 internationals.
- **Impact:** the one signal that beats Elo (the market) cannot be validated across the dev folds →
  no statistically-backed path to promote a market model over B1 yet.
- **Action needed:** approval to spend Odds API historical credits to backfill 2020-06→ odds into
  schema N (append-only store), enabling a paired-bootstrap market-vs-B1 test on the odds-covered
  span. Not started (requires your go-ahead).
