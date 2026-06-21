# Live-2026 Provider Recommendation (2026-06-21)

Full comparison: `data_requests/pending/live_2026_results_lineups_provider_comparison.yaml`.
No purchase made. Prices indicative — verify before buying.

## The gap
- **Results / final status / standings for 2026: already covered FREE** via football-data.org
  (authoritative, in use). No spend needed for these.
- **Missing for 2026: lineups, cards, substitutions, full match events** (API-Football free tier is
  season-gated to 2022–2024; cannot serve 2026).

## Preferred option
**API-Football "Pro" (~$25–30/mo).** Cheapest path that unlocks the current (2026) season for
fixtures, lineups, events, statistics, and standings at near-live latency. Crucially it **reuses the
existing adapter and provider interface unchanged** — only a plan upgrade, no code change, no new
credential type (the direct key already authenticates). ~7,500 req/day fits the quota-aware
scheduler comfortably.

## Low-cost fallback
**football-data.org (free, already integrated) for results/standings** — closes the *results* gap at
$0. If cheap lineup/event coverage is also wanted, **TheSportsDB Patreon (~$3–9/mo)** is the only
sub-$10 option, but its community-sourced live event data is **quality-risky** and must be validated
before trust (and would need a new adapter behind the interface).

## Not recommended now
- **SportMonks** — capable but redundant with API-Football and needs a new adapter.
- **Sportradar / Stats Perform (Opta)** — official and richest (incl. xG) but enterprise-priced and
  contract-bound; overkill for this project's scale and budget.

## Bottom line
- If you want **live 2026 lineups/events** (for an online in-play model): **upgrade API-Football to
  Pro (~$25–30/mo).** One option, reuses everything.
- If you only need **results/standings** (the pre-match shadow eval works on these): **no purchase** —
  football-data.org free already suffices, and the in-play engine is already validated offline on
  2022 events.
