# Commentary Low-Confidence Historical Signals — Data Card
research_only / historical_weak_supervision_only / not_runtime_approved / not_trade_eligible / not_live_eligible.
is_silver=FALSE · confidence_tier=low_confidence. Reproduce: `python scripts/build_commentary_low_confidence_signals.py`.

## What this is
A FLAGGED, derived set of LOW-CONFIDENCE historical event signals for the only classes the V2 gate marked
`usable_only_with_low_confidence_flag`: **corner, foul, yellow_card**. Built from SoccerNet-Echoes (CC BY 4.0)
commentary aligned to SoccerNet action labels (non-commercial research). NO raw commentary text — content
hashes + derived fields only (gitignored parquet + tracked manifest/data-card).

## Contents (this build)
- 2,710 records: corner 1267, foul 1242, yellow_card 201.
- Per-class measured quality (LOCO Wilson-LB precision): corner 0.768, foul 0.768, yellow_card 0.729.
- Each record: match id, commentary record id + content hash, competition/season, event_class,
  model_confidence_score, quality_estimate_precision_wilson_lb, event_time_s, alignment_delta_s,
  is_silver=false, causal_status=historical_weak_supervision_only, live/runtime/trading_eligibility=false.

## What this is NOT
- NOT silver / NOT ground truth: ~23-27% of these records are expected false positives (Wilson LB 0.73-0.77).
- NOT live, NOT predictive, NOT for trading/paper-trading, NOT a runtime/B1/M2/M1-M5/Kalshi/risk input.
- NOT player-level; NOT valid on original-language ASR (English pipeline only).

## Intended use
Historical research only, and ONLY with the low-confidence flag surfaced (e.g., noisy distant supervision,
coverage exploration, qualitative analysis). Any downstream consumer MUST honor is_silver=false and the
non-live/non-runtime/non-trading flags.
