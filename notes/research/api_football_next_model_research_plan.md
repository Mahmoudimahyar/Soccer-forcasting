# API-Football Next-Model Research Plan (Phase 6) — NO training this sprint

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. Each class is specified;
none is trained or promoted here. All use competition-level holdouts + calibration on training folds only.

## Common protocol
- Split: leave-one-competition(-season)-out outer; thresholds/calibration on training competitions only; no
  random row split; match-level grouping (no row from a test match in train).
- Calibration: isotonic or Platt on a held-out training-competition dev fold; never on the test competition.
- Leakage guard: features use only events with elapsed <= decision minute; final score / post-match stats /
  later subs excluded; regulation-only targets exclude ET/shootout.
- Promotion: a model is "candidate" only if it beats a documented baseline on held-out competitions with
  calibrated probabilities; promotion to runtime is OUT OF SCOPE (B1 remains sole runtime).

## 1. Player / substitution-state model
- Eligibility: >=500 complete lineup/sub matches (measured Phase 5). Target: did player p start / be subbed by t.
- Features: lineup, formation, prior on-pitch minutes, sub history <= t. Baseline: base-rate / logistic on
  position+minute. Leakage: future subs excluded. Blocked if <500 lineup/sub matches.

## 2. Next-goal hazard model
- Eligibility: >=500 clean timestamped regulation-event matches. Target: next regulation goal within the next
  K minutes (regulation only). Features: score state, reds, subs, elapsed, team strength (Elo). Baseline:
  constant hazard / Poisson. Leakage: regulation goals only; no ET/shootout; no future events. Blocked if <500.

## 3. Yellow / second-yellow / direct-red model
- Eligibility: >=150 relevant positive events (measured Phase 5; reds rare -> club volume needed). Target:
  card event in next window. Features: fouls/elapsed/score-state. Baseline: base-rate. Class imbalance
  handled on train only. Blocked if <150 positives.

## 4. In-play W/D/L model with lineup state
- Eligibility: >=500 clean regulation-time event matches. Target: regulation W/D/L (90-min result; ET/shootout
  excluded -> separate). Features: regulation score state + reds + subs + lineup strength at t. Baseline:
  market-anchored / Elo. Leakage: regulation only; no final score leak. Blocked if <500.

## 5. Club-to-international transfer experiment
- See api_football_club_to_international_protocol.md. Club = AUXILIARY only; evaluate ONLY on held-out
  international competitions. Do NOT assume transfer helps.

## 6. xG / shot-quality model
- BLOCKED: API-Football provides no per-shot xy and only partial xG -> cannot build a shot-quality model on
  this source. Requires a richer provider (Opta/StatsBomb) or an xG add-on with history. Do NOT infer xG from
  event counts; do NOT claim readiness without per-shot xG.
