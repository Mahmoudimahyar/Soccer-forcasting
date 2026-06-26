# Commentary Precision V2 — Current Truth (Phase 0 reconciliation, 2026-06-26)

## Inherited from soccernet-real-alignment-v1 (tag @ 80ef15c)
- Real overlap: 254 games (whisper_v1_en) / 373 (whisper_v1); exact game-path join, 0 collisions.
- Alignment engine: L0 time / L1 keyword / L3 train-only offset (src/.../soccernet_alignment.py).
  KEYWORD_RULES cover 12 canonical classes; precision was the weak point (goal 0.16, corner 0.82).
- Labels: SoccerNet Labels-v2.json, 385 games, 17 classes, match-clock timing, NO player IDs, NO publication time.
- Readiness was historical_weak_supervision_only; never live.

## What V2 changes
- PRECISION-FIRST: build R0-R4 ladder (rules -> TF-IDF+logreg -> hybrid -> abstention) to push per-class
  precision to a preregistered bar (Wilson LB >= 0.80) with abstention, and decide which classes yield
  high-precision historical "silver labels".

## Known limits going in (from prior sprint)
- Keyword polysemy hurts goal/shot precision; subs/kickoff barely narrated; rare events (red/2nd-yellow) tiny n.
- Language: English rules fail on original-language ASR (goal recall 0.88 en vs 0.05 orig).
- SoccerNet v2 has no player IDs / own-goal / VAR -> player & those event classes unsupported.

## Tooling available
- sklearn 1.7.0, numpy 2.3.5, scipy 1.15.3 -> R2 + Wilson intervals feasible. No external LLM/NLP APIs used.
