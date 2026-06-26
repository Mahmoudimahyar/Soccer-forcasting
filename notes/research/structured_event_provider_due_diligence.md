# Structured Event Provider — Official Due Diligence (Phase 1, 2026-06-26)

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. Evidence = OFFICIAL provider
docs/pricing/licensing/API pages only (no forums/resellers/comparison blogs). Full per-field detail +
official URLs: `data/reference/structured_event_provider_catalog.{json,csv}`. Every non-public fact is marked
**unknown_requires_vendor_confirmation** (counts: Opta 18, StatsBomb 15, Sportmonks 12, API-Football 14,
Sportradar 10).

## Summary by provider (publicly verifiable only)
### A. Stats Perform / Opta
- Coverage: 30y continuous (since 1996), 3,900+ competitions; World Cup historically (atlas to 1930, granular
  to 1966; Opta Vision tracking 2010-2022). **Jan 2026: FIFA's official worldwide betting-data/streaming
  distributor with EXCLUSIVE World Cup 2026 rights through 2029.** Unique game/team/player IDs. xG + shot
  origin coordinates + 3 card classes defined publicly. RESTful + websocket feeds, "sub-second latency."
- Pricing: **NOT public** (tailored quote; license by competition/country/data-level via MLA + Work Orders).
- Unknowns: continental-competition list, per-competition historical event depth, research-vs-commercial
  terms, model-training terms, event-correction protocol, self-serve historical export.

### B. StatsBomb (Hudl)
- Coverage: commercial event data; integer player IDs (object id+name); World Cup present (incl. free-data
  releases historically); best-in-class shot/xG (+360 freeze-frames in premium). Live Data API documented.
- Pricing: **NOT public** (quote). Open free-data tier exists for non-commercial research (separate from commercial).
- Unknowns: exact historical men's-international depth, commercial licensing terms, retention/training/
  redistribution clauses, live latency specifics.

### C. Sportmonks Football API
- Coverage: 2,500+ leagues incl. internationals; **World Cup explicitly covered (competition ID 732), 2026
  edition fixtures/events/lineups**; documented player IDs; xG as add-on. REST API.
- Pricing: **PUBLISHED** — Starter EUR29/mo, Growth EUR99/mo, Pro EUR249/mo (yearly 24/79/199); add-ons (xG,
  historical >seasons) extra. Lowest-cost published path.
- Unknowns: older-international event depth, model-training/redistribution rights specifics, live latency.

### D. API-Football / API-Sports (current configured provider)
- Coverage: **World Cup 2026 documented (league=1, season=2026)**; stable numeric player IDs; events,
  lineups, subs, cards, (inconsistent) xG. Already verified 2xx in V1.5 for 2026 fixtures/events/subs/cards/lineups.
- Pricing: **PUBLISHED** — Free 100/day; Pro USD 19/mo (7,500/day, 300/min); higher Mega/Ultra/Custom tiers.
- Unknowns: shot-location/xG completeness + depth, historical men's-international event-timestamp depth,
  formal retention/training/redistribution terms, live publication-time semantics/latency.

### E. Sportradar
- Coverage: Soccer API + Soccer Extended; stable IDs (sr:player:<id>); World Cup ("World Championship")
  covered; live feeds. Enterprise.
- Pricing: **NOT public** (quote via Order Forms; Realtime vs non-realtime packages).
- Unknowns: per-competition historical depth, xG/shot-location availability per package, rights terms, latency.

## Cross-cutting (all 5)
- **Player IDs: verifiable for all five.** World Cup coverage: verifiable for all five (Opta holds FIFA-official
  WC2026 rights). **Rights (research vs commercial, local retention, model-training-on-derived, raw
  redistribution): unknown_requires_vendor_confirmation for ALL** — these are contract/quote-dependent and are
  the binding gate, not coverage.
- Published pricing only from Sportmonks + API-Football; Opta/StatsBomb/Sportradar are quote-only (record the
  limitation; continue — per the no-stop-on-missing-price rule).
- Binding unknowns for THIS project: (1) historical men's-senior-international event depth at the adopted
  500/500/150 thresholds; (2) model-training + retention + derived-label rights; (3) live publication-time
  semantics for any future live use. All routed to the vendor questionnaire (Phase 4/5).
