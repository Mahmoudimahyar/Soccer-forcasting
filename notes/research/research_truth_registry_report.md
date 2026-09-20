# Research Truth Registry Report (Phase 0)
research_only. Built by scanning ACTUAL gitignored raw across worktrees (not trusting summaries). Data:
data/reference/research_truth_registry.{json,csv}. Reproduce: `python scripts/build_research_truth_registry.py`.

## Resolved conflicting claims (from actual data)
| claim | canonical resolution |
|---|---|
| AF reconciled fixtures (900 vs 1120) | **1,180 distinct fixtures with event files** across worktrees: 900 (api-football-corpus) + ~220 (deep-research extension) + 60 (player-impact player-history). "900" = single-corpus view; "1120" = 900+220; full union incl. the 60 player-history = **1,180**. |
| Sending-off count (123 vs 176) | **123** for the 900-fixture corpus; **176** after the +220 extension (1,120). Both correct for their corpus scope; neither is wrong. |
| Predeclared player-history corpus | planned **2,000**, completed **60**, outstanding **1,940** -> **completion rate 0.03 (3%)**. The prior sprint used a 60-fixture substitute, NOT the full corpus. |
| StatsBomb bridge | **258** exact bridge matches; **60** with raw event files (23%); **0** joined to dynamic snapshots (xG join unwired). |

## Objective Phase-10 gate status (current)
- Gate #2 (AF manifest completion >=95%): **FALSE** (player-history 3%).
- Gate #5 (StatsBomb cache >=90%): **FALSE** (23%).
- Gate #6 (xG snapshot join nonzero): **FALSE** (0 joined).
- Gates #1 (registry), #15/16 (isolation/frozen): registry now exists; collector untouched.
-> Multiple hard gates FALSE -> the sprint is **INCOMPLETE** and must NOT be tagged complete (per the sprint's
   anti-shortcut mandate). The completion requires the durable ~10h run (1,940 fixtures + StatsBomb cache + join).
