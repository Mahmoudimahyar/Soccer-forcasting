# SoccerNet Commentary/Label Quality Audit (Phase 1, real data, 2026-06-26)
research_only / historical_weak_supervision_only / not_live_eligible. No raw text in tracked outputs.
Reproduce: `python scripts/audit_soccernet_commentary_label_quality.py`

## Volume
- Commentary games: 367 (whisper_v1_en) / 529 (whisper_v1 original). Label games: 385. **Overlap = 254** matched.
- Competitions (matched games): EPL 11, UCL 45, Ligue-1 27, Bundesliga 41, Serie-A 70, La-Liga 60. Seasons: 17.
- Commentary segments: **383,591**; supported events: **20,450**. Median match commentary duration 5,446 s (~91 min).

## Events by class (supported)
| class | n | | class | n |
|---|---|---|---|---|
| foul | 6214 | | offside | 1118 |
| shot_on_target | 3026 | | yellow_card | 1061 |
| shot | 2782 | | goal | 846 |
| corner | 2513 | | penalty_awarded | 89 |
| substitution | 1449 | | red_card | 29 |
| kickoff | 1299 | | second_yellow | 24 |

## Quality / integrity
- Duplicate segment rate: **0.211** (ASR repetition / overlapping windows) — dedup by content_hash matters.
- Correction rate: 0.0002 (negligible). Match-mapping: exact game-path, confidence 1.0, 0 collisions.
- Source-hash traceability: every segment carries a content_hash. Taxonomy: 12/12 supported classes have events.
- Timing sanity: segment-time p50 1416.7 s ~ event-time p50 1414.7 s (aligned clocks).

## Rights & language
- Echoes = CC BY 4.0; labels = non-commercial research; **no publication_time -> historical only**.
- Primary = English-translation; 162 original-language-only games exist (audited separately in Phase 6).

## Implications for the gate
- goal/corner/yellow/foul/offside/substitution/kickoff/shots all have >> 50 events -> coverage OK to attempt.
- penalty_awarded (89) borderline; **red_card (29) and second_yellow (24) are below comfortable thresholds**
  -> likely insufficient_coverage regardless of precision.
