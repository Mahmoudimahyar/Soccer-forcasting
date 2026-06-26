# Structured Event — Current Truth (Phase 0 reconciliation, 2026-06-26)

## Why this sprint exists (data gaps confirmed by prior sprints)
- Commentary path EXHAUSTED as a structured-event substitute: SoccerNet commentary gate (V2) approved
  0 high-precision silver classes; SoccerNet v2 labels have NO player IDs / no own-goal / no VAR; original-
  language pipeline fails. -> player/substitution/next-goal/card/red modeling needs a LICENSED structured
  provider. (See commentary_v2_data_decision_package.md, COMMENTARY_PRECISION_V2_COMPLETION.md.)
- Prior provider decision package (data_requests/pending/provider_comparison.yaml) recorded: StatsBomb
  commercial = quote-only; Opta/Stats Perform = enterprise quote-only; Sportmonks = published tiers
  (Starter/Growth/Pro) + add-ons; API-Football Pro = current configured provider (~$19/mo, 7500/day).
  All specifics beyond published pages are quote-only -> unknown_requires_vendor_confirmation.

## What the project already has (do not re-buy)
- 1X2 odds (Odds API), national-team Elo, FIFA-style features, market-anchored models, in-play state dataset
  + frozen in-play M2; prospective shadow collector running (paper-only, B1 sole runtime).
- API-Football Pro access already configured (2026 fixtures/events/subs/cards/lineups confirmed 2xx in V1.5).

## What is missing (the procurement target)
- A licensed structured-event provider giving: stable player IDs, lineups+benches, substitutions, positions,
  distinct card classes (Y/2Y/red), timestamped events, shots(+location)+xG, live publication timestamps,
  and historical men's-senior-international + major-tournament coverage at the adopted sample thresholds.

## This sprint's boundary
Prep only: catalog + provider-neutral contracts + mock adapter framework + acceptance tests + procurement
packet + day-one plans. NO purchase/trial/form/scrape/credential/provider-API-call. All outputs non-runtime,
non-trade, non-live. Active collector untouched (dc73318).
