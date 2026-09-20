# Commentary Weak-Supervision Readiness (Phase 5, 2026-06-23)

Weak supervision = using commentary-derived labels (with structured-event truth anchors) to label
historical matches. **Historical only; never a live feature; never relabeled as live.**

- **Ready in principle:** the canonical contract + alignment toolchain + event taxonomy exist and are
  tested (synthetic). Truth anchors (StatsBomb open / API-Football events) are available.
- **Blocked on data:** no rights-clear aligned commentary corpus is in hand. SoccerNet-Echoes (open) is
  the first eligible source (historical_weak_supervision_only); SoccerReplay-1988 (NDA) is richer.
- **Use boundary:** weak-supervision labels may enrich historical event/player/card research ONLY; they
  may not enter the active collector, the frozen M2, M1-M5 shadow, runtime, paper trades, or Kalshi.
- **Next step after a permitted sample:** run `commentary_alignment_audit.py` for real precision/recall,
  then derive event labels under the rights matrix (derived labels permitted for open sources).
