# Evaluation Reproducibility Audit — 7 Major Evaluations

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Classifies the lab's seven major out-of-sample evaluations by whether each is **independently
reproducible from local artifacts only** (no network/provider). Companion machine-readable file:
`data/reference/evaluation_reproducibility_audit.json`.

## Classification rule

Each evaluation is scored on six traceability dimensions — **(1)** dataset manifest with counts,
**(2)** exact match cohort (ids), **(3)** split protocol (forward-chain order / LOCO / fold defs),
**(4)** a frozen reference model, **(5)** the reported metric file, **(6)** the stated bootstrap
**unit** (match vs row).

- **reproducible_verified** — all six present **and** ≥1 headline metric independently *recomputed*
  bit-close to reported.
- **reproducible_with_limitations** — manifests + cohort + metric present and recomputable *in
  principle*, but a fitted/parametric model or a row-level (non-clustered) bootstrap limits an exact
  cold rerun.
- **needs_rerun** — artifacts present but a metric was **not** recomputed here and a defect/ambiguity
  blocks confidence.
- **cannot_reproduce** — a required dimension (cohort ids / reference / metric) is absent.

> **Bootstrap-unit policy.** The honest independent unit is the **MATCH**, not the snapshot row.
> Evaluations that pool RPS/Brier over many snapshot rows per match keep a reproducible point estimate
> but must use a **match-level cluster bootstrap** for significance.

## Verdicts

| # | Evaluation | Classification | Metric recomputed here? |
|---|---|---|---|
| 1 | **Residual goal-intensity W/D/L** (R0–R6) | **reproducible_verified** | ✅ FC 0.15263 & LOCO 0.14906 reproduced bit-exact |
| 2 | Near-term scoring horizon (H0–H4) | reproducible_with_limitations | h0 parameter-free, not recomputed this pass |
| 3 | Remaining-goal intensity (I0–I3) | reproducible_with_limitations | i0 parameter-free, not recomputed this pass |
| 4 | Event-process intelligence (e0–e9) | reproducible_with_limitations | shares 58-match ceiling; reference deterministic |
| 5 | Dynamic in-play W/D/L (M0–M5 / p4/p5) | reproducible_with_limitations | manifest+ref+metric present; needs corpus to rebuild |
| 6 | Player-state + xG-fusion | reproducible_with_limitations | xG causal self-tests pass; cohort partially enumerated |
| 7 | Discipline / sendings-off | **needs_rerun** | no frozen cohort+metric; sendings-off count root-dependent |

**Tally:** 1 verified · 5 with-limitations · 1 needs-rerun · 0 cannot-reproduce.

## Cross-cutting finding (the binding constraint)

Five of the seven evaluations — every event-bearing StatsBomb eval (residual WDL / intensity /
horizon, event-process, xG-fusion) — share **one** data-availability ceiling: only **58 of the 258**
exact-bridge international matches have StatsBomb event JSONs cached on disk (60 files total, 58
in-bridge). `statsbomb_cache_audit.json` overstates this as `valid_cached: 258`; the snapshot builder
(`n_matches_with_events: 58`) and the on-disk file count both confirm 58. See
`notes/research/residual_58_match_audit.md` §4 for the full reconciliation. Consequence: across all
five, the bootstrap **unit must be the match (58 clusters)**, and backfilling the missing ~200 event
files is the single highest-leverage action to raise statistical power.

## Per-evaluation notes

1. **Residual W/D/L** — fully reconstructed; R0 reimplemented from scratch reproduces the pooled
   forward-chain RPS (0.15263), the LOCO pooled RPS (0.14906), every per-fold RPS, and the 58-value
   LOCO per-match array, all to 5 decimals. Fitted candidates (r1/r3/r4/r5) are reproducible only with
   sklearn refit, but none beats R0 so the negative conclusion is independent of them.
2. **Horizon / 3. Intensity** — references (h0, i0) are parameter-free and recomputable by the same
   engine; not recomputed in this WDL-primary pass. Right-censoring at 5/10/15m
   (4.7%/10.5%/17.0%) is a reproducibility-sensitive choice documented in `rg_dataset_manifest.json`.
4. **Event-process** — deterministic snapshot builder + e2 reference + match-level bootstrap; same
   58-match ceiling; leakage self-test (50 rows) `all_ok`. Reference path verifiable; e-heads need
   refit.
5. **Dynamic in-play WDL** — `model_decision_ledger.json` carries dataset_version (`dynamic_state_v1`)
   + source manifest + reference (`remaining_time_poisson_r2`) + metric + a real match-level
   `match_bootstrap_ci`. Rebuilds from the gitignored API-Football corpus; cohort ids not
   re-enumerated here. p5 rejected on a safety rule, so the conclusion stands regardless.
6. **xG-fusion** — xG causal self-tests all pass (`dynamic_xg_state_audit.json`: no-future-xg,
   monotonic cum-xg, regulation-only, no cross-match leakage). Note the `xg_snapshot_join_audit.json`
   "258 distinct matches / 4386 xG-eligible snapshots" counts bridge matches at the xG-field level;
   the snapshot-level fusion eval still inherits the 58 event-bearing matches — carry this distinction
   forward to avoid overstating N.
7. **Discipline** — the only **needs_rerun**: `canonical_counts_ledger.json` explicitly records a
   scope ambiguity in the sendings-off total (123 / 128 / 176 depending on resolved roots) and there
   is no single frozen decision-ledger + enumerated cohort for the discipline eval in this workspace.
   Freeze one cohort (declare resolved roots) and one metric file before any discipline claim.
