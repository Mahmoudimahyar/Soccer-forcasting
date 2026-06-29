# Hierarchical Cross-Domain Transfer v1 -- Completion Report

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible

- Generated: 2026-06-28T18:23:38.311201+00:00
- Run id: ht_fullrun
- Reference model (anchor): `research.transfer.w2_reference_t0`
- Collector commit (independent system): dc73318 (unchanged=True)

## Population & folds
- Primary test population: INTERNATIONAL test rows only (club rows = auxiliary training, never a test row).
- Forward-chain folds: 4; held-out international test matches: 194.
- Dataset rows: 93940; stable-feature subset sizes: [19].
- Coverage regime: intl_only_no_club_evidence (club rows total = 0).

## Forward-chain results (pooled, vs T0)

| model | RPS | RPS(T0) | delta vs T0 | beats T0 | CI excl 0 |
|---|---|---|---|---|---|
| `international_only_t1` | 0.246031 | 0.244572 | 0.001459 | no | yes |
| `naive_club_pool_t2` | 0.246031 | 0.244572 | 0.001459 | no | yes |
| `partial_pooling_t4` | 0.246031 | 0.244572 | 0.001459 | no | yes |
| `domain_weighted_t5` | 0.246031 | 0.244572 | 0.001459 | no | yes |
| `selective_transfer_t6` | 0.246031 | 0.244572 | 0.001459 | no | yes |
| `shared_stable_features_t3` | 0.246033 | 0.244572 | 0.001462 | no | yes |
| `calibrated_transfer_simulation_t7` | 0.247154 | 0.244572 | 0.002582 | no | yes |

## Verdict

NO model beat T0 on pooled RPS

**Single-domain caveat:** the club auxiliary event corpus is not materialised locally, so the cross-domain transfer ladder (T2..T6) reduces to the international-only T1 and the selective gate correctly falls back. Cross-domain transfer lift is UNTESTED in this run and is NOT claimed.

## Decision

NO model is accepted for runtime/trade/live; all research_only. NO model beat T0 on pooled RPS

Decision ledger: `data/reference/hierarchical_transfer_decision_ledger.json` / `.csv`.

## Final integrity audit

- Isolation: in_collector=False, roots_in_collector=none, raw_git_tracked=(none), forbidden_imports=0.
- Leakage backstop: 2026-WC rows in dataset = 0; dataset_invariants_ok=True.
- Provenance: dataset_sha256=1e47e7fa925e6f00c68cd2de5854bc366e5492bcc3010a8eb73fae4c6845268d.
- Violations: NONE.

All models and artifacts are research_only and NOT runtime/trade/live approved.
