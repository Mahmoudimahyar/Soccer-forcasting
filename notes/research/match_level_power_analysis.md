# Match-level statistical power analysis — in-play residual WDL correction

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Run id: `evp_20260627_power1` · Script: `scripts/run_match_level_power_analysis.py` ·
Output: `data/reference/match_level_power_analysis.json` (byte-identical on re-run; sha `3b9e131b…`).

## Question

The residual-goal-intensity evaluation (`rg_20260627_155623_run1`) tested whether any in-play
correction model beats a parameter-free **W2 remaining-time Poisson reference** on out-of-sample
RPS across **58 independent international matches** (7376 leakage-safe regulation snapshots,
5 tournaments). **No candidate beat the reference** (best, `selective_correction_r4`, pooled LOCO
RPS 0.15394 vs reference 0.14906 — i.e. *worse*). This analysis asks the prior design question:
**given the real match-to-match RPS variance, what uplift could 58 matches actually detect, and
how many independent international matches would a credible claim need?**

## Why 58? (provenance, not an assumption)

The StatsBomb↔API-Football bridge contains **258** exactly-reconciled international matches with
verified xG (`statsbomb_cache_audit.json`: `total_exact_bridge=258`, `xg_field_available=258`).
But the in-play **snapshot panel** that the residual eval consumes was built from a curated
**~10–12 matches per competition**:

| Competition | Matches in snapshot panel |
|---|---|
| FIFA World Cup 2018 | 12 |
| UEFA Euro 2020 | 12 |
| FIFA World Cup 2022 | 12 |
| UEFA Euro 2024 | 12 |
| Copa America 2024 | 10 |
| **Total** | **58** |

(Confirmed by distinct `source_match_id` counts in
`event_process_snapshots/intl_event_process_snapshots.csv` and `competition_source_quality.csv`,
where all 21 capability families are `available_verified` for these 58.) So **58 is a build-time
cap, not the data ceiling** — 258 bridged matches with verified xG already exist on disk. The
7376 rows = 58 matches × many decision-minute snapshots; the snapshots are **not** independent.

## Method (match-level, deterministic)

- **Independent unit = match.** Each match collapses to one per-match mean-RPS; every snapshot of
  a match moves together. All resampling is match-clustered.
- **Empirical noise template.** From `rg_wdl_loco.json` per-match arrays we take the paired delta
  `d_i = rps(r4)_i − rps(r0)_i` for the candidate that tracks the reference most closely
  (`selective_correction_r4`: identical to r0 on **46 / 58** matches, the only `calibration_ok`
  candidate). We center it (`e_i = d_i − mean(d)`) to get a zero-mean paired-noise template with
  the **observed** match-level spread (sd = 0.0199). This is the real noise an in-play correction
  layer close to the reference exhibits.
- **Power.** For a target absolute improvement `δ` and dataset size `M`, draw `M` matches with
  replacement from `e_i`, form `x_i = e_i − δ`, and apply the **same decision rule the gate used**:
  a match-level paired cluster bootstrap whose 95% upper CI bound on the mean delta is `< 0`
  (candidate favored, CI excludes zero on the improvement side). Power = fraction of outer
  simulated datasets that fire the rule.
- **Determinism.** Single fixed `MASTER_SEED = 20260627`; numpy PCG64 via
  `default_rng(seed).spawn()`. No wall-clock / unseeded randomness. Re-running reproduces the JSON
  byte-for-byte.

## Results

### Current power at 58 matches

| Abs RPS improvement | Power @ 58 | Reading |
|---|---|---|
| 0.0005 | **0.10** | indistinguishable from the 5% false-positive floor |
| 0.0010 | 0.14 | practically blind |
| 0.0020 | 0.20 | mostly blind |
| 0.0030 | 0.28 | weak |
| 0.0050 | 0.49 | coin-flip |
| 0.0100 | **0.90** | only a *large* edge is visible |

Power-estimate uncertainty across 12 independent seeds is small (sd ≈ 0.007–0.019), so these are
stable, not noise.

### Matches / tournaments needed (80% power, observed 11.6 matches/tournament)

| Abs RPS improvement | Matches @80% | Tournaments @80% |
|---|---|---|
| 0.0005 | not reachable (≤3000 grid) | >250 |
| 0.0010 | not reachable (≥2000 for 60%) | >170 (for 60%) |
| 0.0020 | 1000 | 86 |
| 0.0030 | 400 | 35 |
| 0.0050 | **150** | **13** |
| 0.0100 | 58 | 5 |

### More snapshots, same 58 matches → no power gain (clustering ceiling)

At δ=0.0030, inflating snapshots 1×/2×/4×/8× on the same 58 matches leaves power flat
(0.30 / 0.29 / 0.27 / 0.29). Independent clusters stay 58; extra snapshots are within-cluster and
carry no new independent information. **Densifying snapshots is not a path to a claim.**

### Club-only lever → data_insufficient

The eval had **zero** club matches (`club_transfer_active=false`). No club per-match RPS exists, so
a club-only power curve cannot be estimated without fabricating variance. Flagged honestly.

## Headline answers

1. **Is 58 enough for the uplift we care about?** **No.** 58 matches reaches ~90% power only for a
   *large* 0.0100 RPS improvement. For the realistic small corrections actually tested, power is
   10–28%. A null at 58 cannot separate "no edge" from "small real edge we can't see" — the eval
   correctly returned `reference_only`, not a positive claim.
2. **How many independent international matches for a credible claim?** ~**150** (≈13 tournaments)
   for a moderate 0.0050 edge at 80% power; ~400 for 0.0030; ~1000 for 0.0020. Smaller true effects
   are out of reach at realistic tournament volume.
3. **Are more snapshots useful without more matches?** **No** — power is flat under snapshot
   inflation. Only **more independent matches** move the needle.

## Caveats

- Power assumes the true effect equals the target and that the centered r4-vs-r0 delta is a faithful
  noise template; a genuinely different correction family could have larger per-match variance,
  pushing requirements **up**, not down.
- This is a **research evidence threshold**, not runtime/trade approval. No 2026 WC data used; all
  artifacts remain `research_only / not_runtime_approved / not_trade_eligible / not_live_eligible`.
