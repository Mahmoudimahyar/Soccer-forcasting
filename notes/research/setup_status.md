# Setup Status — autoresearch session (2026-06-21)

Safe configuration + connectivity audit. **No `.env` value printed/copied/logged.** Only SET/MISSING
and HTTP status class. `pytest -q` → **91 passed** (documented before any model work). Trading remains
paper: `KALSHI_ENABLE_LIVE_TRADING` is false and Kalshi trading credentials are absent.
(Supersedes the 2026-06-20 Tier-1 refresh; findings consistent.)

| variable | status | note |
|---|---|---|
| API_FOOTBALL_KEY | **SET** | but **rejected by both direct + RapidAPI** (see BLOCKERS.md / source_readiness_audit.md) |
| ODDS_API_KEY | **SET** | working (2xx); ~13,100/≈20k requests remaining |
| FOOTBALL_DATA_KEY | **SET** | working (2xx); ~10/min free tier |
| KALSHI_ENV | SET | demo |
| KALSHI_API_KEY_ID | **MISSING** | no Kalshi trading credential present |
| KALSHI_PRIVATE_KEY_PATH | **MISSING** | — |
| KALSHI_ENABLE_LIVE_TRADING | SET = **false** | paper mode (unchanged, not modified) |

## Connectivity (minimal read-only, no quota burn)
| provider | connectivity | live-data capability now | quota/rate concern | blocker |
|---|---|---|---|---|
| The Odds API | success (2xx) | WC2026 pre-match + in-play odds; historical odds from 2020-06 | ~13.1k requests left; historical endpoint uses credits | none |
| football-data.org | success (2xx) | WC2026 fixtures/results/standings (authoritative) | ~10 req/min free | lineups/events paid |
| Open-Meteo | success (2xx, keyless) | venue weather forecast/archive | fair-use | none |
| API-Football | **auth fail** | none (key invalid on both auth modes) | — | **key correction needed** |

## Capability summary
- **Usable now:** results/fixtures/standings (football-data.org), timestamped odds (Odds API),
  weather (Open-Meteo), open historical datasets (already ingested).
- **Not usable now:** confirmed lineups / injuries / event timelines (blocked on API-Football key or
  a licensed event feed).
- **Exact blocker:** API-Football key authenticates under neither direct api-sports.io nor RapidAPI.
  Needs a valid direct dashboard key (adapter works unchanged) or a subscribed RapidAPI key + an
  approved one-line adapter change. Not on B1's critical path. Full detail in `BLOCKERS.md`.
