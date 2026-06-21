# Data Enrichment Gate 1 — Completion Report (2026-06-21)

Read-only data-readiness + ingestion-contract phase on branch `data-source-readiness`. **No model,
provider adapter, credential, risk cap, Kalshi/live setting, `.env`, or scraping policy was changed;
no data was enriched and no autoresearch was run.** Trading stays `KALSHI_ENABLE_LIVE_TRADING=false`,
`TRADING_MODE=paper`. `pytest -q` → **91 passed**. Tags `tier-1-complete` and `approved-b1-runtime`
were not moved; this release gets a new tag.

## Deliverables
- `notes/research/source_readiness_audit.md` — safe live availability tests (secrets never exposed).
- `schemas/live_data_contracts.yaml` + `docs/LIVE_DATA_CONTRACTS.md` — raw provenance envelope + 17
  normalized schemas A–Q with leakage/usability/conflict rules.
- `docs/EVENT_RECONCILIATION_POLICY.md` + `src/wcdrawlab/ingestion/reconcile.py` + tests.
- `notes/research/data_enrichment_priority.md` + 4 new `data_requests/pending/*.yaml`.
- Read-only scaffolding: `src/wcdrawlab/ingestion/{health,raw_store,validate,reconcile}.py`,
  `scripts/provider_health_check.py`, `scripts/ingest_dry_run.py` (`--dry-run --source --match-id
  --as-of-utc --output-dir`). Append-only immutable raw store; no trades/loops/scrapers.
- Tests: `tests/test_event_reconciliation.py`, `tests/test_ingest_scaffolding.py` (sanitized
  fixtures only, no real API calls).

## The nine questions

**1. Which configured APIs actually work?**
The Odds API (2xx, auth OK, 13,100/≈20k requests remaining), football-data.org (2xx, auth OK,
~10/min free), Open-Meteo (keyless, 2xx). **API-Football does NOT work.**

**2. Which account or key type needs correction?**
**API-Football.** The configured key is rejected by *both* paths (live-tested, not guessed): direct
api-sports.io returns a token error; RapidAPI returns 4xx. Fix = provide a **valid direct
api-sports.io key** (works with the existing adapter unchanged) **or** a **RapidAPI key with an
active API-Football subscription** + explicit approval for a one-line adapter host/header change.
Adapter left unmodified (`data_requests/pending/api_football.yaml` = blocked).

**3. Which World Cup 2026 data is genuinely available now?**
Results / fixtures / standings (football-data.org, authoritative, already live); pre-match + in-play
**odds** (The Odds API, `soccer_fifa_world_cup`); venue **weather** forecasts (Open-Meteo).
**Not available now:** confirmed lineups, injuries/suspensions, and event timelines (blocked on the
API-Football key or a licensed event feed).

**4. Which historical event / lineup / odds data is available?**
Odds: historical from **2020-06 only** (Odds API paid historical; **no pre-2020** — the known B6
limit). Results: 1872–2026 (martj42 / jfjelstul, already ingested with hashes). Event-level history:
**StatsBomb open data** (free, selected tournaments incl. some WCs; non-commercial license sign-off
needed). Historical lineups: only via StatsBomb (partial) or API-Football (paid) — not yet.

**5. Which data sources are safe for B1 runtime enrichment?**
B1 consumes only time-safe Elo from results, which is already covered with full provenance. The
ready/safe feeds (football-data results/standings, Odds API ingest-only, Open-Meteo) **do not change
B1 today**; they enable evaluation and Tier 3–5. The **market model itself stays shadow-only** per
the approved-model registry — only the odds *feed* is ingested.

**6. Which data sources remain research-only?**
StatsBomb historical events (license), FBref player minutes (scraping/terms), referee history
(source TBD), and any in-play event feed (until API-Football/licensed). The market-anchored blend
remains shadow-only.

**7. Which sources require your account creation or approval?**
API-Football (valid key/subscription), StatsBomb (non-commercial license sign-off), FBref (approve a
terms-compliant access method — no scraping until then), referee source (select one). Open-Meteo
needs **no account** — just an approval to adopt it as a low-priority supplemental source.

**8. Exact next highest-value implementation task.**
**Historical pre-match odds backfill (Odds API, 2020-06→) into schema N** via the append-only raw
store, then a **paired-bootstrap of a market-anchored model vs B1** on the folds where odds exist
(2022 gate + post-2020 internationals). This is the single test that could justify promoting a market
model over B1; it uses an already-approved source, needs no new account, and respects the pre-2020
gap. **Requires your approval to begin ingestion — not started.**

**9. Are any current forecasts invalid due to insufficient data provenance?**
**No.** The approved model (B1/Elo) uses time-safe Elo with complete provenance
(`data/processed/source_provenance.json`); its forecasts are valid. The market-anchored blend is
already shadow-only with no runtime authority (registry), so its provenance limits (post-2020 odds
only) do not invalidate any *approved* forecast. The pre-2020 odds gap constrains B6 validation, not
B1. No approved forecast is invalidated.

## Verification
- `pytest -q` → 91 passed. `git status --short` clean after commit (outputs/ health.json is gitignored).
- Protected paths unchanged vs `approved-b1-runtime`: `candidate.py`, `src/wcdrawlab/trading/`,
  `src/wcdrawlab/models/`, providers, `.env` — none modified.

**STOP.** No model changes, candidate.py experiments, provider expansion, scraping, or live
prediction changes until you explicitly approve this gate.
