# API-Football — 2026 Coverage Check (2026-06-21)

One approved minimal request. No secrets/headers/credentials exposed.

## Request
- endpoint: `GET /fixtures`  (host `https://v3.football.api-sports.io`, header `x-apisports-key`)
- non-secret params: `league=1` (FIFA World Cup), `season=2026`
- HTTP status: **200**
- fixtures returned: **0**
- provider message: **`"Free plans do not have access to this season, try from 2022 to 2024."`**

## Findings
| question | answer |
|---|---|
| 2026 WC fixtures | **NO** — free plan blocks season 2026 |
| fixture IDs | n/a for 2026 (available for 2022–2024) |
| live/final status | n/a for 2026 |
| standings | n/a for 2026 (season-gated like fixtures) |
| lineups | n/a for 2026 |
| match events | n/a for 2026 |
| match statistics | n/a for 2026 |
| daily quota | **100 requests/day** (free), 0 used at check time (per `/status`) |

**Authentication works** (direct API-Sports, 32-char hex key). The limitation is **plan coverage,
not auth**: the free tier exposes only **seasons 2022–2024**.

## What this means
- **Live 2026** lineups/events/standings/in-play replay via API-Football free tier: **NOT possible.**
  Requires a **paid plan** (or another licensed live event feed). football-data.org remains the
  authoritative 2026 results/standings source.
- **Useful silver lining:** the free tier **does** cover **2022–2024**, so API-Football free could
  supply **2022 World Cup** lineups/events/statistics for **offline in-play replay training** (within
  100 req/day) — a no-cost path to build/validate the in-play model on real historical events.

## Ingestion configuration (built, NOT polling)
A provider interface + quota-aware scheduler were added (`src/wcdrawlab/providers/interface.py`,
`schedule.py`) so that if a paid 2026 plan (or the 2022 historical path) is enabled, ingestion runs
behind a single interface with a hard daily-budget guard. **No high-frequency polling is started.**

## Recommended polling schedule (stays under 100/day, when a covered season is enabled)
- **Lineups:** once per match at **T-75 min** (window T-90..T-60). 16 matches/day max → ≤16 calls.
- **Standings:** once **after each match's final whistle** (per group) → ≤16 calls/day.
- **Events/statistics:** **only on match-state change or at final whistle** (not continuous) →
  budget the remainder; cap total/day at 100 with priority lineups > standings > events.
- Never poll live minute-by-minute on the free tier.

## Limitations preventing live use (current)
Free-plan season gate (2022–2024 only) blocks **all** 2026 live result/lineup/event/standings/in-play
use. Resolve by upgrading the API-Football plan, or use the 2022–2024 window for offline replay.
