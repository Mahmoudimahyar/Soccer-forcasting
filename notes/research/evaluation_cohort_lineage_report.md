# Evaluation Cohort Lineage — Report (the WHY-58 funnel)

`research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible`

Built 2026-06-28T02:36:00.856126+00:00. Match-level lineage for every fixture in the in-play residual pipeline. Independent unit = MATCH. Every present→absent stage transition carries exactly one allowed drop reason; no fixture disappears silently.

## Funnel (match-level)

| stage | matches |
|---|---|
| raw_corpus | 298 |
| reconciled_corpus | 258 |
| international_population | 298 |
| exact_bridge_population | 258 |
| xg_snapshot_population | 58 |
| event_process_population | 58 |
| residual_population | 58 |
| primary_evaluation_population | 46 |
| loco_evaluation_population | 58 |

## The 258 → 58 reduction (answered)

- **exact_bridge_population = 258** international matches (exact `api<->statsbomb` bridge).
- **− 200** matches drop with reason `missing_statsbomb_events`: no StatsBomb event JSON physically on disk (prior larger pull pruned; only the read-only 60-file cache remains).
- **event_process_population = residual_population = 58** matches — these have events on disk AND a regulation-final W/D/L target (rows_skipped_no_wdl = 0).
- **primary_evaluation_population = 46** — forward-chain test set: the earliest competition (**FIFA World Cup 2018**) is train-only and drops with reason `held_out_fold_rule`.
- **loco_evaluation_population = 58** — every competition is held out once, so all present matches are LOCO-testable.

Forward-chain competition order (earliest kickoff first): ['FIFA World Cup 2018', 'UEFA Euro 2020', 'FIFA World Cup 2022', 'UEFA Euro 2024', 'Copa America 2024'].

## Drop-reason counts

| drop_reason | matches |
|---|---|
| `ambiguous_bridge` | 38 |
| `failed_reconciliation` | 2 |
| `held_out_fold_rule` | 12 |
| `missing_statsbomb_events` | 200 |

## Integrity

- all drop reasons in the allowed category set: **True**
- no silent disappearance (every 1→0 explained): **True**
- StatsBomb event JSONs currently on disk: **60**

The 58-match residual cohort is the live ceiling under current local data. To restore the cohort toward 258 the full StatsBomb event pull must be re-acquired (a data-acquisition step, not a modeling change). The 0-candidate honest-negative conclusion of the residual phase is unaffected by cohort size — it is a calibrated, match-level-bootstrapped result on the 58 it had.