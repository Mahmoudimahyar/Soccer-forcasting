# Live Provider Truth Audit (2026-06-23)

Resolves the inconsistency between earlier "free plan = 2022–2024 only" notes and later "Pro may be
available" notes. **No keys, headers, or raw .env values printed** — only SET/MISSING + status classes.
Used exactly **3 provider calls** (cap respected).

## Configured provider
- **API-Football (api-sports.io, direct host)** — `API_FOOTBALL_KEY` = SET (value never shown).
- `ODDS_API_KEY` = SET (for Section 4 odds capture).

## Authenticated plan / tier
- **Plan = Pro**, active=True, renews 2026-07-22. Daily quota **7/7500** at audit time.
- **Resolution:** the old "2022–2024 only" limitation was the FREE tier; the account is now on **paid
  Pro**, which removes the season gate. The free-tier notes are historical and superseded.

## 2026 World Cup coverage (call 2: `GET /fixtures?league=1&season=2026`, HTTP 2xx, 72 fixtures)
| capability | covered? | evidence |
|---|---|---|
| 2026 fixtures | **yes** | 72 fixtures returned |
| 2026 live/final-status | **yes** | statuses present: FT=43, HT=1 (live), NS=28 |
| 2026 events (goals/cards/subs) | **yes** | call 3 below |
| 2026 standings | **yes** | verified 2xx in the V1.5 Phase 1 audit (not re-called — 3-call cap) |
| 2026 lineups | **yes** | verified 2xx in the V1.5 Phase 1 audit (not re-called — 3-call cap) |

## Endpoints tested + HTTP
1. `GET /status` → **2xx (200)**, no errors (plan + quota).
2. `GET /fixtures?league=1&season=2026` → **2xx (200)**, results=72.
3. `GET /fixtures/events?fixture=1489369` (a finished 2026 match) → **2xx (200)**, 18 events;
   goals/cards/subs all present.

(Quota/rate-limit: daily 7/7500 reported by `/status`; per-minute headers present per prior audit.)

## Usability verdict
- **pre-match fixture verification:** YES (fixtures + kickoff times).
- **final-result verification:** YES (FT status + goals).
- **standings refresh:** YES (verified previously).
- **lineup updates:** YES (verified previously).
- **in-play event updates:** YES (events incl. goals/cards/subs; 1 match currently live).

## Conclusion
API-Football **Pro** is the authoritative live provider for the 2026 prospective study — sufficient for
fixture verification, final results, standings, lineups, and in-play events. The Odds API (key SET)
supplies pre-match 1X2 odds (Section 4). No plan was purchased, upgraded, or altered during this audit.
