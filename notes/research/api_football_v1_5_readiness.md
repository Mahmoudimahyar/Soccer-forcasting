# API-Football V1.5 Readiness (Phase 1, 2026-06-23)

Minimal read-only direct diagnosis (5 harmless requests). **The API key was never printed, hashed, or
logged** — only SET/MISSING and HTTP status classes are reported.

| check | result |
|---|---|
| .env available | yes |
| API_FOOTBALL_KEY | SET |
| configuration source | dotenv |
| direct authentication (api-sports.io host) | **accepted** |
| status endpoint | HTTP 2xx |
| rate-limit availability | yes (headers present) |
| World Cup fixtures (league 1 / season 2026) | available (2xx) |
| standings (league 1 / season 2026) | available (2xx) |
| match-events | available (2xx) |
| substitutions (in events) | available |
| cards (in events) | available |
| lineups | available (2xx) |
| **direct API compatibility** | **yes** |

## Conclusion
Direct API-Sports/API-Football works on the paid Pro plan for the 2026 World Cup, including the in-play
event categories needed for prospective collection (fixtures, events, subs, cards, lineups). No blocker.

## Action taken
Built a **read-only, rate-limited adapter wrapper** — `src/wcdrawlab/operations/api_football_adapter.py`:
- GET-only; refuses any non-GET / non-allowlisted endpoint (fail-closed).
- Enforces a minimum inter-request interval + a daily request budget with a reserve (quota-aware).
- Reads the key from env; **never logs/prints the key**; logs only sanitized endpoint+params templates.
- Persists raw payloads append-only with a provenance envelope (gitignored).
- No model code touched; no high-frequency polling; injectable transport so tests never hit the network.

This adapter is the read path for the Phase 2 durable collector. It is research/operations-only and
cannot influence runtime, paper-trading, risk, or Kalshi.
