# Runtime Model Governance — approved forecasts route through B1/Elo (2026-06-21)

Effective decision: **B1 / internal Elo is the sole approved runtime model of record.** V8 and the
market-anchored blend are **experimental, shadow-only** with **no runtime authority**. No shadow
model may affect displayed primary forecasts, advancement probabilities, paper-trade intents, risk
calculations, Kalshi integration, model-performance claims, or any approved prediction ledger.
Trading remains paper-mode; no provider credentials, live-trading settings, risk caps, or scraping
policy were touched.

## Authoritative registry
- Single source of truth: `configs/approved_models.yaml` (loaded/enforced by
  `src/wcdrawlab/runtime/model_registry.py`). It pins `approved_model_id=B1_ELO`, model version,
  commit hash (`e78cde4…`, tag `tier-1-complete`), training cutoff, feature schema version
  (`research_modeling_table_v1`), data-snapshot reference, approval date, allowed runtime uses, and
  the experimental models with their restrictions.
- Frozen governance decision: `notes/research/approved_model_registry.md` (committed `8338ad1`).

## Why B1 is approved
Tier-2 evaluation (`notes/research/tier_2_baseline_gate.md`, `outputs/research/tier2/`) showed **no
candidate beats B1 with statistical significance**: B7_nomarket dRPS vs B1 = +0.0011, 95% CI
[−0.0059, +0.0077] (a tie); B0/B2 significantly worse. B1 is also best on DEV-mean composite
(0.3553) and reproduces exactly (reconciliation audit, `model_state_reconciliation.md`). It is
parameter-free (ternary Elo, r=0.4) on time-safe `elo_delta`, so it carries the least overfitting
and leakage risk — the right model of record.

## Why V8 is experimental (shadow-only)
`src/wcdrawlab/research/candidate.py` (standardized logit + 0.85 ternary-Elo blend). On the 2026
prequential it is **worse than B1**: RPS 0.225 vs 0.174, log-loss 1.092 vs 0.958 (better only on
draw calibration), and it shows **no significant dev-fold improvement** over B1. It remains the
autoresearch candidate surface but has **no runtime authority**.

## Why the market blend is experimental (shadow-only)
`scripts/market_anchored_forecast.py` (0.6·market + 0.4·Elo). The market leg (B6) **cannot be
validated before 2020** (Odds API history starts 2020-06), so there is **no cross-fold backtest**.
It is a prospectively-scored forecast aid only — not an approved, backtested model.

## Exactly which path produces approved forecasts
```
wcdrawlab.runtime.forecaster.runtime_forecast(matches, model_id=None)
   -> model_id defaults to get_approved_model_id() == "B1_ELO"
   -> require_approved(model_id)         # fail-closed: V8 / market / unknown all raise
   -> approved_forecast(matches)         # B1 ternary-Elo on elo_delta
   -> stamps the APPROVED envelope (registry-derived, cannot be shadow)
```
CLI: `python scripts/forecast_runtime.py` → writes
`outputs/research/forecasts/approved_forecast_2026.csv` and `approved_ledger.csv`. **Every approved
row carries** `model_id, model_version, approval_status, prediction_mode=approved,
decision_timestamp, source_manifest_id, feature_schema_version, commit_hash`.

### Hard safeguards (enforced + tested in `tests/test_runtime_governance.py`)
- Runtime rejects any model not in the approved registry (`require_approved` → `ModelNotApprovedError`).
- Unknown model ids **fail closed** (`classify`/`make_envelope` → `UnknownModelError`); never a
  silent fallback to an experimental model. If the approved model's inputs/impl are unavailable,
  `approved_forecast` raises rather than substituting a shadow model.
- Decision / paper-trade / risk / Kalshi paths must call `require_decision_model(envelope)`, which
  raises `ShadowDecisionError` for any non-approved prediction.
- The actual paper-trade risk gate is **registry-bound**: `TradeIntent` carries a `model_id`, and
  `RiskGate.evaluate` (`src/wcdrawlab/trading/risk.py`) rejects the intent whenever that `model_id`
  is not the approved runtime model (`is_approved`). A shadow model (V8 / market blend) therefore
  **cannot produce a paper/demo/live decision**, in addition to the pre-existing
  `approved_model_versions` check. (No risk caps, live-trading settings, provider credentials, or
  scraping policy were changed; trading stays in paper mode.)
- The envelope's `prediction_mode` is **derived from the registry**, so it is **impossible to label
  a V8 or market-blend forecast as approved**; `label_shadow()` refuses the approved id.

## Shadow predictions & preserved history
- Shadow outputs (V8, market blend) may be produced for comparison only, each tagged
  `prediction_mode=shadow`, `experimental_status=true`, `no_runtime_authority=true`,
  `reason_not_approved=…`. Example relabelled artifact:
  `outputs/research/forecasts/shadow_market_blend_2026.csv`.
- Historical artifacts are **preserved, not deleted**, and relabelled as shadow/historical (see
  `historical_shadow_artifacts` in the registry): prior market-anchored forecasts, V8/ensemble
  forecasts, the prospective `forecast_ledger.csv`, advancement sims, and `prequential_2026.csv`.

## How shadow-model comparisons will be evaluated
Shadow models are scored **side-by-side with B1, never in place of it**, on identical, leakage-safe,
time-ordered folds (dev 2010/14/18; gate 2022 read once; locked 2026 prequential), using RPS,
log-loss, draw Brier, and draw calibration, with **paired bootstrap deltas vs B1**. Shadow ledgers
are kept separate from the approved ledger.

## Evidence required to promote a shadow model (to approved)
A shadow model is promoted **only if all hold**:
1. Paired-bootstrap **RPS improvement vs B1** with a 95% CI **excluding 0** on the DEV folds (and no
   log-loss regression).
2. **No regression** on the 2022 release gate (read once).
3. Calibration reported (slope/intercept + reliability) and not worse than B1 on the locked fold.
4. Reproducible from tracked code + pinned data snapshots.
On promotion: update `configs/approved_models.yaml` (+ `approved_model_registry.md`) with the new
`approved_model_id`, commit hash, and evaluation path, and demote B1 to experimental/reference.
Until then, **B1 remains the sole approved runtime model.**
