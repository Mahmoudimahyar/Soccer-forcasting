# Source Readiness Audit — Data Enrichment Gate 1 (2026-06-21)

Read-only safe availability tests. **No `.env` value was inspected, printed, hashed, committed, or
exposed.** Keys were sent only in request headers/params; failures captured exception *type* only
(never messages — The Odds API carries its key in the URL). Status **class** only is reported.
One minimal endpoint per provider. Trading stays paper (`KALSHI_ENABLE_LIVE_TRADING=false`,
`TRADING_MODE=paper`); no adapters were modified.

Reproduce: `python scripts/provider_health_check.py` (module `wcdrawlab.ingestion.health`).

## Live results (2026-06-21)
| provider | configured | endpoint | status_class | auth accepted | mode detected | rate-limit (header) |
|---|---|---|---|---|---|---|
| Open-Meteo | n/a (keyless) | GET /v1/forecast | 2xx | yes (keyless) | direct API | n/a |
| The Odds API | SET | GET /v4/sports | 2xx | **yes** | direct API | remaining=13100 used=6900 |
| football-data.org | SET | GET /v4/competitions/WC | 2xx | **yes** | direct API | ~9/min available (free 10/min) |
| API-Football (direct) | SET | GET /status (api-sports.io, x-apisports-key) | 2xx | **no** (token error in body) | direct | — |
| API-Football (RapidAPI) | SET | GET /v3/status (rapidapi host, x-rapidapi-key) | **4xx** | **no** | rapidapi | — |

## Per-provider readiness

### 1. API-Football — BLOCKED (key not usable via either auth)
- **Critical question resolved (not a guess, live-tested both ways):** the configured
  `API_FOOTBALL_KEY` is **rejected by BOTH** auth modes today:
  - **Direct** (`v3.football.api-sports.io` + `x-apisports-key`): HTTP 200 but body carries an
    `errors` token object → direct dashboard key **not valid**.
  - **RapidAPI** (`api-football-v1.p.rapidapi.com` + `x-rapidapi-key`/`x-rapidapi-host`): **4xx**
    (client auth error) → not a valid/subscribed RapidAPI key for this API either.
- **Conclusion:** the key is **not currently authenticated on either path**. This is either an
  expired/invalid key, or a RapidAPI key without an active API-Football subscription.
- **What is needed (user action):** EITHER (a) a **direct api-sports.io** dashboard key from
  https://dashboard.api-football.com (works with the existing adapter **unchanged**), OR (b) a
  **RapidAPI** key **with an active API-Football subscription** *and* explicit approval to make a
  one-line host/header change in `src/wcdrawlab/providers/api_football.py` (currently protected).
  **Adapter NOT modified.** Coverage (lineups / events / injuries / stats) is **unknown** until a
  working key exists. Not on the critical path for B1 (results/odds come from other providers).
- WC2026: unknown · historical: unknown · lineup: unknown · timeline: unknown · odds: n/a.
- Acceptable for approved runtime use: **No** (blocked).

### 2. The Odds API — READY
- Auth accepted (direct). Quota healthy: **13,100 remaining / 6,900 used** (≈20k/mo tier).
  `/v4/sports` is free and does not consume quota.
- WC2026 odds: **yes** (live `soccer_fifa_world_cup`); historical: **yes from 2020-06** via the paid
  historical-odds endpoint (no pre-2020 history — the known B6 limitation); lineup/timeline: **no**;
  odds: **yes**.
- Acceptable for runtime *ingestion*: **Yes** (note: the *market model* itself remains shadow-only
  per the approved-model registry; the odds **feed** is fine to ingest as a snapshot source).

### 3. football-data.org — READY
- Auth accepted (direct), ~9–10 req/min free tier. WC competition endpoint reachable.
- WC2026 fixtures/results/standings: **yes** (authoritative; already powering live 2026 results);
  historical WCs: **yes** (limited on free tier); lineup: **partial/paid**; event timeline
  (goals/cards/subs): **partial/paid**; odds: **no**.
- Acceptable for approved runtime use: **Yes** (results/fixtures/standings).

### 4. Open-Meteo — READY (keyless)
- Forecast API reachable, keyless. Forecast horizon 16 days; historical via the Archive API
  (`archive-api.open-meteo.com`). No match data.
- WC2026: n/a (weather) · historical: yes (archive) · lineup/timeline/odds: no.
- Acceptable for runtime use: **Yes** (venue-condition features; low predictive priority).

### 5. Existing open historical datasets — READY (already ingested)
- martj42 international results (CC0), jfjelstul WC matches/tournaments, Dato-Futbol FIFA rankings,
  Transfermarkt squad values (dcaribou). Provenance + hashes in
  `data/processed/source_provenance.json`.
- Historical results: **yes** (1872–2026); lineup/event/odds: **no**.
- Acceptable for runtime use: **Yes** (these are the B1/Elo data foundation).

### 6. Official FIFA public sources — NOT FETCHED (policy)
- Per `docs/DATA_SOURCE_GOVERNANCE.md`: allowlisted public pages only, robots respected, no login/
  paywall/CAPTCHA bypass. The FIFA.com tie-breaker page is JS-rendered (noted in Tier-1). **Not
  fetched in this read-only audit.** Status: available as a manual/archival reference only; any
  automated use requires a new approved `data_requests/pending/` entry.

## Summary
- **Working now:** The Odds API, football-data.org, Open-Meteo, open historical datasets.
- **Needs correction:** API-Football key (rejected by both direct and RapidAPI) — user must supply a
  valid direct api-sports.io key, or a subscribed RapidAPI key + approve the adapter change.
- **Safe for B1 runtime enrichment:** none change B1 today (B1 needs only Elo from results, already
  covered); the **highest-value ready feed is timestamped odds** (ingest-only; market model stays
  shadow). football-data results/standings remain the authoritative live feed.
- No secrets were exposed; no adapter, credential, or trading setting was changed.
