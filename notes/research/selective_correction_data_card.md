# Selective Correction — Data Card

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Model: `research.residual.selective_correction_r4`
(`wcdrawlab.research.residual_intensity.SelectiveCorrection` + `selective_gate.SelectiveGate`).
Reference: `research.residual.w2_reference_r0` (W2 remaining-time Poisson). Population: the real
international event-process panel — **7,376 snapshots, 58 matches, 5 competitions** (WC2018, WC2022,
Euro2020, Euro2024, Copa2024). No 2026 World Cup in any fit / calibration / selection path.

## What the selective gate does
Per row it chooses how much event-process correction to apply on top of the W2 reference:

| decision | weight |
|----------|--------|
| `fallback_to_w2` | `alpha = 0.0` (pure W2 reference) |
| `apply_low_weight_correction` | `alpha = alpha_low` |
| `apply_full_correction` | `alpha = alpha_full` |

The blend is a fixed convex form `p = (1 - alpha) * p_w2 + alpha * p_correction` (per class, renormalized).
The gate selects only the completeness thresholds `(t_low, t_full)` and the alpha bands
`(alpha_low, alpha_full)` from small **predeclared grids** — no test-tuning, no broad search:
`ALPHA_LOW_GRID = [0, 0.25, 0.5]`, `ALPHA_FULL_GRID = [0, 0.5, 0.75, 1.0]`,
`COMPLETENESS_GRID = [(0.40,0.75),(0.50,0.80),(0.60,0.85)]`.

## Invariants (all enforced + self-tested on real rows)
1. **`alpha = 0` is reachable.** Completeness below `t_low` → `fallback_to_w2` → `alpha = 0` → output is
   bit-for-bit the W2 reference. Self-test: a low-completeness row (completeness `0.093`) → decision
   `fallback_to_w2`, `alpha = 0`, blend equals pure W2.
2. **Thresholds chosen on TRAIN only; never on a test row/label.**
3. **Uses ONLY causal availability/state fields** (event-process completeness, xG presence) — never a
   target.
4. **Never raises confidence when completeness is low.** Completeness maps monotonically to the correction
   band; a sparser row can only get a smaller-or-equal `alpha`. The `partial` (no-xG) evidence tier
   therefore never receives a *larger* correction than a `rich` row.
5. **Degenerates to pure fallback when correction is not earned.** If no configuration beats the W2
   reference, the gate keeps `alpha_low = alpha_full = 0` (it selects pure W2). `diagnostics()` reports
   `degenerate_fallback`, the chosen thresholds, and correction coverage.

## Honest selection: internal held-out folds (`fit_cv`)
A naive gate that scores alpha on the **same rows the correction model was fit on** over-trusts the
correction: the in-sample fit looks far better than W2, so the gate picks aggressive alpha — and then
collapses out-of-sample. We measured this directly on the real panel.

`SelectiveCorrection.fit` therefore selects alpha with `SelectiveGate.fit_cv`: the correction is **refit
inside each internal leave-one-competition-out fold within TRAIN** and scored on the held-out internal
competition, so the gate sees the *true generalization gap* before choosing alpha. This is the honest
reading of "alpha chosen in-train" — chosen using only TRAIN, but never scored on rows the correction
memorized.

### The finding (this corpus, 58 matches)
The event-process correction **does not beat the W2 reference out-of-sample.** Leave-one-competition-out
(5 folds), pooled out-of-fold log-loss:

| model | OOF log-loss | OOF RPS |
|-------|-------------:|--------:|
| `w2_reference_r0` (reference) | **0.7733** | **0.1491** |
| `selective_correction_r4` (honest CV gate) | 0.7958 | — |
| `intensity_glm_r1` (always-on correction) | 1.246 | 0.172 |
| `event_process_boost_r3` (HGB) | 1.105 | 0.164 |
| `calibrated_simulation_r5` | 1.247 | 0.172 |

The always-on corrections (`r1`, `r3`, `r5`) are **badly overfit** — their in-sample log-loss is ~0.33–0.58
but out-of-competition they are ~1.1–1.25, far worse than W2's 0.773. This is expected: ridge intensity
heads + isotonic calibration trained on ~46 matches memorize the train competitions; 5 competitions is too
few for the side-specific intensity heads to generalize.

The **selective gate correctly recognizes this**: with the honest internal-CV fit, on 4 of 5 LOCO folds it
degenerates to `alpha = 0` (pure W2 fallback); on the 5th it picks a mild `alpha = 0.5` that ties W2
in-CV. Fit on the FULL panel, the gate reports `degenerate_fallback: true`
(`alpha_low = alpha_full = 0`, `correction_coverage_oof = 0`, `gated_oof_logloss == baseline_w2_oof_logloss
= 0.7733`). The selective model thus reduces to the W2 reference rather than emitting an overconfident
correction. That is the intended, honest behavior — **the gate is doing its job by refusing to correct.**

## Correction coverage
- Honest CV gate on full panel: **correction coverage = 0%** (gate falls back everywhere).
- A naive in-sample gate would report 100% coverage with `alpha_full = 1.0` — and lose ~0.47 log-loss
  out-of-sample. The data card records this contrast as the justification for the CV-honest selection.

## Data sufficiency verdict
On the currently available local corpus (58 international matches, 5 competitions, StatsBomb open-data),
**there is not enough data for the event-process correction to beat the W2 remaining-time reference
out-of-sample.** The honest output of `selective_correction_r4` is the W2 reference. To earn a positive
correction we would need substantially more international matches per competition (the intensity heads are
the bottleneck, not the gate). Until then, any claim that the event-process correction improves on W2 on
this corpus would be **overclaiming** and is explicitly not made here.

## Reproduce
```
python scripts/build_event_process_snapshots.py        # builds the 7,376-row panel from StatsBomb
python -c "import sys; sys.path.insert(0,'src'); \
  from wcdrawlab.research import residual_intensity as RI; import json; \
  print(json.dumps(RI.self_test(), default=str, indent=2))"   # status=complete on real rows
```
Self-test is deterministic (seeded); two runs produce identical diagnostics.
