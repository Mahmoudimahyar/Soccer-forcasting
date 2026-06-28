# Residual Goal-Intensity 58-Match Cohort — Independent Reconstruction & Recompute Audit

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

**Question.** The residual goal-intensity W/D/L evaluation (`rg_20260627_155623_run1`) reports a
**58-match / 7376-snapshot** international cohort and a pooled forward-chain reference RPS of
**0.15263** for the parameter-free W2 remaining-time Poisson reference
(`research.residual.w2_reference_r0`). This audit asks, from raw manifests + already-validated local
artifacts only: **why 58? is it valid? did anything disappear unintentionally? is there a pipeline
defect? would a repair change the conclusion?**

**Method.** `scripts/audit_residual_58_match_cohort.py` (1) rebuilds the count funnel from the bridge
+ on-disk StatsBomb event caches, (2) reconstructs the cohort from the snapshot/target tables, and
(3) **independently** recomputes the R0 forward-chain and LOCO RPS by reimplementing the W2
Poisson convolution from scratch (no `residual_intensity` import). Verified by
`tests/test_residual_cohort_reconstruction.py` (15 tests, all passing).

---

## 1. The count funnel (why 58)

| Stage | Matches | By competition | Loss | Reason |
|---|---:|---|---:|---|
| Exact international bridge | **258** | Copa 28 / WC18 64 / WC22 64 / Euro20 51 / Euro24 51 | — | API-Football ↔ StatsBomb exact bridge (`api_statsbomb_match_bridge_v1`) |
| StatsBomb events cached on disk | **58** | Copa 10 / WC18 12 / WC22 12 / Euro20 12 / Euro24 12 | **−200** | **No StatsBomb event JSON present in any local cache** |
| Residual-target-eligible snapshots | **58** | (same 12/12/12/12/10) | −0 | every event-bearing match yields snapshots + a W/D/L target; `rows_skipped_no_wdl=0` |

- Forward-chain = 4 scorable folds (Euro2020, WC2022, Euro2024, Copa2024 — WC2018 is train-only as
  the earliest competition), **5789** test rows.
- LOCO = 5 folds (each competition held out once), **7376** test rows, **58** per-match RPS values.

**The 58 is a data-availability number, not a rule.** The snapshot builder
(`build_event_process_snapshots.py::_find_intl_event_file`) resolves each of the 258 bridge matches
to a local file `events/{sb_match_id}.json` in two roots only — the canonical `statsbomb_raw/events`
(empty, 0 files) and the read-only prior pull
`worldcup-player-impact-xg/data/raw/statsbomb_open/events` (**60 files**). Of those 60 cached files,
**58 are in the exact-international bridge** (the other two, `3939978` / `3939980`, are Copa fixtures
the bridge rejected and so were never eligible). Every one of the 200 "lost" matches is dropped with
`n_matches_no_events_present += 1` purely because **its event JSON was never downloaded to disk**.

## 2. Independent recompute vs reported (bit-exact)

R0 is parameter-free (no training), so it is fully determined by the current score difference and the
remaining-time-scaled base rate (1.35 goals/team/90′). Reimplementing the exact independent-Poisson
convolution (`kmax=10`) from the raw snapshot CSV columns reproduces every reported number:

| Metric | Recomputed | Reported | Δ |
|---|---:|---:|---:|
| Forward-chain pooled RPS (R0) | **0.15263** | 0.15263 | 0.000000 |
| Forward-chain pooled n_test_rows | 5789 | 5789 | 0 |
| LOCO pooled RPS (R0) | **0.14906** | 0.14906 | 0.000000 |
| LOCO per-match RPS array (58 values) | identical multiset | — | max Δ = 0.0 |
| Per-fold RPS (Euro20/WC22/Euro24/Copa24) | 0.15408 / 0.15713 / 0.13758 / 0.16322 | identical | 0.0 each |

The reported metric is **reproducible_verified**: an entirely independent implementation lands on the
same value to 5 decimals on every fold and on the pooled estimate.

## 3. Is 58 valid under the preregistered rules?

**Yes, given the data on disk.** The residual eval is, by design, *international exact-bridge only*
across the 5 tournaments. The preregistered population is the 258 exact-bridge international matches;
the realized population is the subset whose StatsBomb event files are locally present. No
non-international rows leak in (`all_international=true`, every `comp_type='international'`), no 2026
World Cup rows appear (`no_2026_audit.ok=true`; re-asserted in the loader), and the W/D/L target
coverage is 100% (`rows_skipped_no_wdl=0`). The 12/12/12/12/10 split is simply how many event JSONs
happen to be cached per competition — **not** a hard-coded per-competition cap (`limit_matches`
defaults to `None`; no `[:12]`/`head(12)` anywhere in the builder).

## 4. Did any valid match disappear unintentionally? Is there a pipeline defect?

- **No silent empty join / path bug / fold bug / duplicate collapse / hard-coded threshold** in the
  residual eval itself. The funnel reconciles exactly (258 → 58 → 58, 0 lost at the eligibility step;
  the 2 cached-but-ineligible files are correctly excluded as not-in-bridge). Per-fold N and per-match
  RPS reproduce bit-exact, which rules out a fold-assignment or duplicate bug.
- **One real metadata defect found (does not change the science).**
  `data/reference/statsbomb_cache_audit.json` claims `valid_cached: 258`, `xg_field_available: 258`,
  `missing_or_invalid: 0` — i.e. that **all 258** exact-bridge matches have valid cached events. That
  is **contradicted** by (a) the actual on-disk count (60 event JSONs total, 58 in-bridge), (b) the
  snapshot builder (`n_matches_with_events: 58`, `n_matches_no_events_present: 200`), and (c) the
  per-competition quality roll-up (12/12/12/12/10 = 58). The cache audit is therefore **stale or was
  generated against a planned/declared cohort rather than the on-disk reality**. It overstates cached
  coverage by 4.4× and should be regenerated from the same `_find_intl_event_file` resolution the
  builder uses. **This is a provenance/accounting defect, not an evaluation defect** — the eval used
  the real 58, and its metrics are correct for those 58.

## 5. Would a repaired cohort change the scientific conclusion?

**Almost certainly not, for the residual finding as stated.** The conclusion is *negative*: no
richer residual/intensity/horizon candidate (r1, r3, r4, r5; i1, i2; h1–h4) beats the parameter-free
W2 reference out-of-sample, on either protocol. The best candidate (selective-correction r4) merely
*reproduces* R0 on most folds (FC pooled 0.15767 vs 0.15263; LOCO 0.15394 vs 0.14906) and never
favorably clears the match-level bootstrap. Adding the missing ~200 matches would *strengthen* the
statistical power but is very unlikely to flip a uniformly-negative result into a promotion — and the
preregistered bar still requires a match-clustered bootstrap win, which none approach.

**However, the cohort is genuinely thin for any positive claim.** The honest unit is the **match (58
clusters), not the 7376 snapshot rows.** The match-level cluster bootstrap of R0's per-match RPS gives
a 95% CI of **[0.12706, 0.17055]** around a mean of 0.1479 — wide enough that small candidate
differences are not separable. So: the *negative* conclusion is robust; any *future positive* claim
must wait for more cached event data and must be judged at the match level.

## 6. Recommendations

1. **Regenerate `statsbomb_cache_audit.json`** from the builder's actual file-resolution so its
   counts (should read 58 cached / 200 missing) match reality; flag the current file as stale.
2. **Backfill the 200 missing StatsBomb event JSONs** (open data; the bridge ids are known) to lift
   the cohort toward the full 258 and materially increase match-level power.
3. **Report all residual metrics with a match-level cluster bootstrap CI** (58 clusters) as the
   primary significance statement; keep the row-pooled number only as a descriptive point estimate.

## Artifacts

- `scripts/audit_residual_58_match_cohort.py` — reconstruction + independent recompute
- `tests/test_residual_cohort_reconstruction.py` — 15 tests (10 unit math + 5 integration)
- `data/reference/residual_58_match_audit.json` — machine-readable funnel + comparison + verdict
- `data/reference/residual_58_match_cohort.csv` — the 58-match cohort (one row per match)
