# Paid Source Integration & Merge Plan (Phase 6)

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. Do NOT merge into the active
collector checkout. This plan describes how the research artifacts could be integrated LATER, safely.

## Mergeable later (research-only modules)
- `src/wcdrawlab/research/paid_source/` (safe_config) + the API-Football audit/backfill/quality/reconcile/
  readiness scripts + the odds historical pilot. All read-only, budget-capped, append-only, gitignored raw.
- The 120-match pilot corpus is a reusable historical research asset (gitignored; re-pullable from manifests).

## Must remain research-only (never runtime/trading)
- Everything in this sprint. The paid_source modules must stay non-importable by runtime/trading/Kalshi/risk
  (enforced by `test_no_runtime_or_trading_imports_paid_source`).

## Fields that may NEVER enter the frozen prospective model
- Any post-hoc / retrospectively-corrected event field used as if known pre-decision.
- Any field lacking a per-event PUBLICATION timestamp used for LIVE/prospective inference (API-Football gives
  no per-event publication time -> historical only; live-shadow needs a measured safety lag first).
- M1-M5 and frozen in-play M2 stay FROZEN; B1 remains the sole approved runtime model. No backfilled field
  is wired into them.

## Delayed-live shadow feasibility (API-Football)
- Possible in principle (live fixtures endpoint with elapsed minute), but requires a MEASURED end-to-end
  latency + a causal gate (publication_time + lag <= decision_time) before any shadow use. NOT done here and
  out of scope. Until measured, API-Football data is historical_only for this project.

## Source-time limitations
- No per-event publication time; retrieval time recorded by the adapter. Adequate for historical research;
  inadequate for live/prospective without latency characterization.

## Odds API historical pilot
- Supports DIAGNOSTIC market-vs-outcome comparison only (Phase 4). No bearing on M1-M5; no market-edge claim.
  Useful as a reproducible historical-odds retrieval pattern (1 snapshot ~10 credits covers a matchday).

## Is another provider still needed?
- For player/substitution/card/next-goal/in-play W/D/L historical research: **NO** — API-Football Pro suffices
  (quality verified; thresholds reachable via bounded backfill) EXCEPT red-card VOLUME (needs ~1,200 matches).
- For **xG / shot-location / shot-quality** research: **YES** — API-Football cannot supply per-shot xy and only
  partial xG. A richer provider (Opta/StatsBomb) or an xG add-on remains required for that class only.

## Model classes — unblocked vs blocked (by data)
- UNBLOCKED for historical research (data exists + clean; scale backfill to thresholds): player/substitution,
  card (yellow), next-goal (timestamped events + goals), in-play W/D/L.
- PARTIALLY blocked: red-card models (need ~10x backfill for >=150 examples).
- STILL BLOCKED on API-Football: xG / shot-quality / shot-location models (provider gap).
- Always out of scope here: any live/trading model (frozen; KALSHI_ENABLE_LIVE_TRADING=false).

## Remaining requirements per class
- player/card/next-goal: a larger (still bounded, budget-reserved) backfill to reach 500/500; red >=150 needs
  major-league matches added.
- xG: a provider with historical per-shot xG + locations (or an API-Football xG add-on if it covers history).
