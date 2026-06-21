# API-Football Diagnostic (2026-06-21)

Exactly **one** low-cost direct health request (`GET /status`). Credentials not rotated or exposed;
the key value was never printed (only a structural fingerprint). PII in the response body is redacted.

## Result
| field | value |
|---|---|
| base URL | `https://v3.football.api-sports.io` |
| auth header name | `x-apisports-key` |
| HTTP status | **200** |
| provider `errors` | **`[]` (none)** — authentication **accepted** |
| key fingerprint | length **32**, **hex-only** → **direct API-Sports format** (NOT RapidAPI's ~50-char alphanumeric) |
| account | `<redacted name/email>` |
| subscription | **Free** plan, active until 2027-06-20 |
| rate limit | **100 requests/day** (0 used at check time) |

### Redacted response body
```json
{"get":"status","parameters":[],"errors":[],"results":0,"paging":{"current":1,"total":1},
 "response":{"account":{"firstname":"<REDACTED>","lastname":"<REDACTED>","email":"<REDACTED>"},
 "subscription":{"plan":"Free","end":"2027-06-20T00:00:00+00:00","active":true},
 "requests":{"current":0,"limit_day":100}}}
```

## Interpretation — STATUS CHANGED vs the earlier audit
The earlier audit (and `BLOCKERS.md` B-1) found this key **rejected** on the direct host (HTTP 200
with a token error). It now **authenticates cleanly on the direct host** — the key has evidently
been corrected to a valid **direct api-sports.io** key. **No auth corrective action is required.**

## Remaining caveat — free-tier COVERAGE (not auth)
API-Football's **Free** plan is historically limited (typically older seasons / a subset of leagues,
often excluding current live competitions) and capped at **100 req/day**. Authentication is solved;
**data coverage for the live 2026 World Cup is not yet confirmed.**

## Exact corrective action required
- **Auth:** none — the direct key works as-is with the existing adapter (`x-apisports-key`).
- **To use it for 2026 lineups/events:** verify free-tier coverage with **one** additional low-cost
  call (e.g., `GET /fixtures?league=<WC id>&season=2026`); if the free plan excludes 2026 WC, a paid
  tier (or another licensed event feed) is needed. This single coverage check was **not** run here
  (the task authorized exactly one request). Recommend it as the next step before any event ingestion.
