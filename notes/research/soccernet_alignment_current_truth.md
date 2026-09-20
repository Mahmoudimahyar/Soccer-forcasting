# SoccerNet Alignment Current Truth (Phase 0, 2026-06-23)

## SoccerNet-Echoes raw dataset (already acquired, gitignored)
- Status: ACQUIRED bounded sample (whisper_v1, CC BY 4.0) = 10 games / 6552 segments; full corpus
  780,160 segments available (one Arrow file, gitignored). Manifest: commentary_soccernet_sample_manifest.json.
- Commentary fields: game, segment_index, start_time, end_time, text.
- Timing fields: start_time/end_time = BROADCAST seconds (match/broadcast clock). NO publication_time.
- Legal: CC BY 4.0 (open_research_download_allowed, attribution); historical_weak_supervision_only.
- Action labels present? NO. SoccerNet-Echoes is ASR TEXT only; it carries no event/action labels.

## What is needed for real alignment
- Official **SoccerNet action-spotting labels** (Labels / Labels-v2.json per game) keyed to the SAME
  SoccerNet `game` paths -> structural overlap is exact IF labels are obtainable. License/access verified
  in Phase 1 (SoccerNet historically gates label download behind a signed agreement / NDA + password).

## What can be done WITHOUT action labels
- Match-mapping layer, canonical event taxonomy reconciliation, alignment ENGINE (rule/time/entity),
  derived-data product schema, and all synthetic tests + feasibility analysis.

## What remains impossible WITHOUT action labels
- Real precision/recall/F1 + timing error vs ground truth; real weak-supervision label emission.
  -> if labels are NDA/approval-gated, readiness = blocked_by_action_label_source (documented, not faked).
