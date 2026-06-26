# Structured Event — Provider Decision Matrix (Phase 6)
research_only. Factual fit + unknowns + actions required. NOT a recommendation by coverage alone; the binding
axis is RIGHTS clarity + coverage DEPTH at the adopted thresholds, then cost.

| provider | published price | player IDs | WC coverage | xG / shot-loc | rights clarity | integration complexity | key unknowns |
|---|---|---|---|---|---|---|---|
| Sportmonks | YES (EUR29/99/249 + addons) | yes | yes (comp 732, 2026) | xG add-on (recent-leaning) | low-published, terms unconfirmed | low (REST, current-style) | older-intl depth; training/redistribution rights |
| API-Football | YES (Free / Pro $19 / Mega+) | yes | yes (league=1, 2026) | partial/inconsistent | terms unconfirmed | low (already configured) | xG/shot-loc depth; formal training/retention terms; pub-time semantics |
| Opta/Stats Perform | NO (quote) | yes | yes (FIFA-official WC2026) | best | contract (MLA) heavy | high (SDAPI + contract) | price; research-vs-commercial; correction protocol |
| StatsBomb (Hudl) | NO (quote; free tier non-comm) | yes | yes (incl free data) | best-in-class (+360) | commercial terms unconfirmed | medium-high | commercial price; intl historical depth; retention |
| Sportradar | NO (quote) | yes | yes | per-package | quote terms unconfirmed | high | per-package xG/loc; price; rights |

## Factual reading (no over-claim)
- **Lowest-friction lawful start**: Sportmonks or API-Football (published price; can subscribe once rights
  confirmed). API-Football is already configured for 2026 WC fixtures/events/lineups.
- **Richest data**: Opta or StatsBomb (xG/shot-location/positions), at quote-only cost + heavier contracts;
  Opta additionally holds FIFA-official WC2026 rights.
- **Every provider's rights for retention + model-training-on-derived + aggregate publication are UNCONFIRMED**
  -> the acceptance protocol fails closed until the vendor confirms in writing. Coverage is NOT the bottleneck.
- No single provider is recommended here: the choice depends on the user's budget and which model classes are
  the priority (cheap player/sub/card/next-goal vs premium xG/shot-quality). Actions to resolve in external doc.
