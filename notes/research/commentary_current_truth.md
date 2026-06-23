# Commentary Current Truth (Phase 0, 2026-06-23)

What the project already has vs. what commentary work requires. Reconciled from PROGRAM_STATE,
source/readiness audits, StatsBomb records, event reconciliation policy, live-data contracts, model
identity registry, replay semantics, in-play schemas, the active-collector isolation manifest, and the
prospective scorecard protocol.

## Structured event sources ALREADY available (verified earlier this program)
- **API-Football (Pro)** — events (goals/cards/subs), lineups, fixtures, standings; 2026 + historical;
  used by the live collector. Structured, licensed (paid account). NOT text commentary.
- **StatsBomb Open Data** — events + per-shot xG + 360 for WC2018/2022, Euro2020/2024, AFCON2023,
  Copa2024 (+ women's/club). Non-commercial research, attribution required. Structured events, NOT
  free-text minute-by-minute commentary.
- **The Odds API** — 1X2 odds only (no commentary).

## Text commentary sources ALREADY available / integrated
- **NONE.** No minute-by-minute free-text commentary source is integrated. The earlier analysis
  (this program) concluded that scraping news live-blogs is ToS/copyright-restricted and that licensed
  commentary feeds are derived from the same Opta/StatsBomb event data. No commentary dataset is in repo.

## Sources only MENTIONED, not verified (Phase 1 must verify against official refs)
- SoccerNet-Echoes, SoccerReplay-1988, MatchTime, MatchVoice, "Live Football Commentary/LFC",
  YallaShoot / Arabic commentary datasets, StatsBomb commentary/alignment resources, official
  FIFA/UEFA/CONMEBOL/AFC/CAF match-centre data, API-Sports commentary endpoints, other commercial feeds.

## Provisional rights buckets (to be made rigorous in Phase 2)
- **May be legal for research:** academic datasets released under explicit research licenses (verify each).
- **Legal only with approval / paid:** commercial commentary/event feeds; StatsBomb commercial; Opta.
- **Unknown rights:** news live-blog text, fan/Arabic commentary mirrors (assume restricted until proven).
- **Potentially live-usable:** only sources with official API rights + trustworthy publication timestamps
  (none confirmed yet).
- **Retrospective weak-supervision only:** datasets with event_time but no trustworthy publication_time.

## Source gaps that block player/substitution/card/next-event research
- No large, licensed, timestamped event+lineup corpus beyond StatsBomb open (~333 men's intl) → the
  player/next-goal/card model thresholds (500 matches / 150 reds) remain blocked (established prior).
- Commentary COULD add weak-supervision labels historically, but only a licensed/open source with clear
  rights can be used; and it can NEVER be a live feature unless the causal gate (publication_time ≤
  decision_time) passes — which no source has yet satisfied.

## Carry-in constraints
research_only / experimental / not_runtime_approved / not_trade_eligible for all commentary work; active
collector + B1 + frozen M2 + M1–M5 shadow + trading flags untouchable; no new odds/API calls.
