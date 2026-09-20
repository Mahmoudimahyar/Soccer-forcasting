# Player-Impact & xG — Current Truth (Phase 0, 2026-06-26)
Inherited (tag deep-research-inplay-foundation-v1 @ 6136443):
- Corpus 1,120 fixtures (627 intl + 493 club), 100% regulation reconciliation, sendings-off 176. Causal
  in-play snapshot harness + W0-W4/N0-N3/C0-C1 model pattern + restart-safe controller all present.
- Prior finding: W2 (remaining-time Poisson) is the in-play W/D/L leader; lineup-continuity features did NOT
  generalize. THIS sprint tests RICHER features: rolling PLAYER-IMPACT priors, substitution DELTAS, and xG fusion.
Data state:
- API-Football Pro (7,500/day; today's prior use ~2,500). StatsBomb OPEN data NOT local -> Phase 3 acquires a
  bounded set (CC-licensed). International overlap (WC2018/2022, Euro2020/2024, Copa2024) bounds the xG sample.
- xG via API-Football is partial/absent (shot-locations unavailable) -> xG MUST come from StatsBomb open data.
Boundaries: API-Football only (no Odds API); StatsBomb open data within license + attribution; key via read-only
loader (never printed); raw append-only gitignored; no model promoted; collector/frozen models untouched.
