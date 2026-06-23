# SoccerNet Alignment Failure Analysis (Phase 5)
research_only / historical_weak_supervision_only / not_live_eligible. Examples are SYNTHETIC placeholders
(no raw commentary text is quoted; raw ASR stays gitignored).

## Failure modes observed (from the real metrics)
1. **Language mismatch (dominant).** English keyword rules vs original-language ASR -> goal recall
   collapses 0.88 -> 0.05. Fix used: English-translation variant (whisper_v1_en). Implication: a
   production system needs per-language rule sets or translated commentary.
2. **Keyword polysemy -> low precision.** "goal" appears in "great chance for a goal", "goal kick",
   "goalkeeper" -> precision 0.16. Synthetic example: segment "the goalkeeper claims it" wrongly claims
   a goal. Mitigation: negative patterns / phrase rules / classifier (future work).
3. **Under-narration -> low recall.** Substitutions (0.09) and kick-offs (0.006) are often not narrated
   with the pre-registered phrases. Mitigation: expand phrase lists; subs often announced by name only.
4. **Timing spread.** Commentary lags or anticipates events; |dt| median 4-18 s. Goals narrated AFTER the
   ball crosses the line; fouls narrated around the whistle. Window=45 s captures most true pairs.
5. **Rare-event instability.** red_card (n=6), second_yellow (n=5), penalty (n=19) -> metrics are noisy;
   do NOT report as reliable. Need more games (more label splits) for these.
6. **One-to-many / many-to-one.** A single goal can trigger several commentary segments (replay talk);
   a "shot" segment can sit near multiple shot events. Engine takes the nearest claiming segment;
   duplicate/correction detection available via content_hash + correction markers.

## What would raise quality (research directions, all historical)
- Per-language rules or always use translated commentary.
- Negative/disambiguation patterns for goal/shot; a small local classifier (no external LLM).
- Player-name entity resolution would help subs — but SoccerNet v2 labels lack player IDs.
