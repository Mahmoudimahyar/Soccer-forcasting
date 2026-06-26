# Structured Event Provider — Requirements (Phase 0)
research_only / not_runtime_approved / not_trade_eligible / not_live_eligible.

## Adopted minimum data thresholds (already project policy)
- >= 500 complete lineup/substitution matches.
- >= 500 timestamped-event matches for next-goal research.
- >= 150 direct-red OR second-yellow examples.
- Competition-level holdouts (leave-one-competition-out), not random splits.
- Strict source-time / provenance: event time + provider update time + (publication time if live) +
  retrieval + correction time; live use requires publication_time <= decision_time (causal gate).

## 1. Must-have (per research goal)
### Player / substitution research
- player IDs (stable), starting lineups + benches, substitutions (on/off + minute), positions where available.
- >= 500 complete lineup/sub matches across men's senior internationals + (if needed) major leagues for n.
### Next-goal research
- event-level TIMESTAMPS (match clock + wall/update time), goals/own-goals/penalties, period
  (regulation/ET/shootout separated), >= 500 timestamped matches, live publication time for any live use.
### Card / red-card research
- yellow, second-yellow, direct-red as distinct classes with player + minute; >= 150 red/2nd-yellow examples.
### World Cup in-play research
- live event feed with publication/update timestamps + latency; WC + major continental coverage;
  event corrections; score reconciliation.

## 2. Nice-to-have
- shot locations, xG, assists, formations, referee IDs, injuries, possession sequences, VAR events,
  freeze-frames/360.

## 3. Not needed yet
- tracking/positional (player xy) data, broadcast video, advanced physical metrics, betting odds (already have).

## 4. Rights requirements (must clear before storing/training)
- local retention + historical research use + model-training on derived features + derived-label publication
  (aggregate) + clear redistribution boundary (no raw redistribution) + research (non-commercial OK now;
  commercial-future optional). Every unclear field -> unknown_requires_vendor_confirmation.
