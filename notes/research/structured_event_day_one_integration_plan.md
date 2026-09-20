# Structured Event — Day-One Integration Plan (Phase 6)

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. For every still-plausible
provider. "Day one" = the day AFTER the user obtains lawful access; nothing here is executed in this sprint.

## Shared day-one sequence (all providers)
1. **Credentials**: user provides the key/contract OUT OF BAND; stored only in `.env` (never committed; never
   printed/hashed by this plane). A NEW real adapter subclasses `ProviderAdapter` — the existing mock stays.
2. **Legal approval gate**: the signed rights answers populate `licensed_provider_rights_v1`; storage/training
   begins ONLY after `accept_for_storage_and_research`.
3. **First safe endpoint/export**: a SINGLE historical match (or the 20-match sample) — read-only, rate-limited,
   no live polling. No trading, no collector contact.
4. **Raw storage**: append-only, gitignored `data/raw/licensed_events/<provider>/` + a source manifest
   (sha256, retrieval time, endpoint, rights tag) BEFORE parsing.
5. **Normalize** via the new adapter -> `licensed_event_record_v1` (preserve provider IDs + source hash; no
   invented fields; fail-closed causal eligibility).
6. **Reconcile** (score/own-goal/shootout, dedupe, corrections) + **quality gate** (completeness, thresholds).
7. **Acceptance**: run `scripts/run_provider_acceptance_tests.py` -> `provider_acceptance_result_v1`.
8. **First research dataset** (only if accepted): historical player/lineup/sub/card/timestamped-event tables
   (gitignored), derived-only, leakage-safe (competition holdouts), labeled not_runtime/not_trade/not_live.
9. **Boundary**: licensed-event modules remain non-importable by runtime/trading/Kalshi (enforced by test).
10. **Rollback**: delete gitignored raw + derived; revoke key in `.env`; remove the real adapter; the mock +
    contracts remain. No collector/runtime state is ever touched, so rollback is local-only.

## Per-provider day-one specifics
### Sportmonks (published price — fastest lawful start)
- Credential: API token (paid plan, user-chosen tier). First endpoint: a historical fixture with events+lineups
  (competition 732 = World Cup) + xG add-on if licensed. Unknowns to confirm first: older-international depth,
  model-training/redistribution rights. Enables: player/sub/card + timestamped next-goal research IF depth>=thresholds.
### API-Football / API-Sports (already configured)
- Credential: existing Pro key (already in use for fixtures). First endpoint: 2026 WC (league=1, season=2026)
  events+lineups+subs+cards (already 2xx). Unknowns: shot-location/xG completeness, formal training/retention
  terms, publication-time semantics. Enables: card/sub/lineup + next-goal (timestamp) research; xG-dependent work blocked until confirmed.
### Opta / Stats Perform (quote-only; FIFA-official WC2026)
- Credential: contract + SDAPI key after MLA/Work Order. First endpoint: SDAPI match feed sample. Unknowns:
  price, research-vs-commercial terms, correction protocol. Enables: the richest player/shot/xG/position +
  official WC2026 live — but highest cost + heaviest contract.
### StatsBomb (Hudl) (quote-only; best xG/360)
- Credential: commercial contract OR open free-data tier (non-commercial). First: free-data WC sample or
  commercial Live Data API sample. Unknowns: commercial price, intl historical depth, retention terms.
  Enables: best-in-class shot/xG/freeze-frame research; player/lineup/card.
### Sportradar (quote-only)
- Credential: Order Form + key. First: Soccer API match sample. Unknowns: per-package xG/shot-location, price,
  rights. Enables: broad coverage + live; xG/location depends on package.

## Model classes
- Become feasible on acceptance (any provider with player IDs + timestamps + thresholds): **player/substitution
  models, next-goal (timestamped) models, card/red-card models, WC in-play state models.**
- Still blocked without xG/shot-location depth: shot-quality / xG-based models (provider-dependent).
- Always blocked here: anything live/trading — out of scope; collector + B1 unchanged.
