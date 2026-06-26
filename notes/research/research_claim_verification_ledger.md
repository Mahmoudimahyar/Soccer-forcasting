# Research Claim Verification Ledger (Phase 0)
research_only. Status of every prior model/data claim against CURRENT verifiable data.

| claim | status | basis |
|---|---|---|
| W2 (remaining-time Poisson) is the in-play W/D/L leader | verified_current_data | reproduced on 900-fixture intl snapshots (deep-research + player-impact); RPS 0.150 |
| Player-impact features do NOT beat W2 | incomplete_or_partial | evaluated on PARTIAL data (60/2000 player-history; sparse priors). Valid ONLY for the partial impl; **needs_rerun** on the full corpus. |
| Next-goal: player-impact adds nothing (N2/N3) | incomplete_or_partial | same partial-data caveat; needs_rerun |
| xG fusion (X0-X3) | incomplete_or_partial | bridge built (258) but 0 joined to snapshots, 60/258 events -> never actually evaluated; needs_rerun after join |
| Discipline C1 | historical_reference_only | skipped (123<150 in 900-corpus view); 176 in 1120 scope -> re-evaluate with full corpus |
| 100% regulation reconciliation | verified_current_data | 900/900 + 273/273 reconciled exact in this scan |
| Corpus 1,120 fixtures / 176 sendings-off | verified_current_data (scoped) | true for the deep-research 1,120 scope; the player-impact worktree only saw 900 (raw locality) |

## Rule applied
No model result is treated as CURRENT if its source dataset cannot be identified exactly. The player-impact
negative result is downgraded to incomplete_or_partial (partial corpus) -> the full-corpus rerun is the
outstanding scientific work this sprint targets but has NOT completed.
