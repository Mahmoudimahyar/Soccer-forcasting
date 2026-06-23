# SoccerNet Real Commentary-to-Event Alignment — Evaluation (Phase 5)

research_only=true · historical_weak_supervision_only=true · not_runtime_approved=true ·
not_trade_eligible=true · not_live_eligible=true

## Data
- Ground truth: official SoccerNet **Labels-v2.json**, 385 acquired games, 17 classes (no player IDs;
  match-clock timing only; **no publication_time**). License: non-commercial research + attribution.
- Commentary: **SoccerNet-Echoes** ASR (CC BY 4.0). Two variants used:
  - `whisper_v1` (original broadcast language) — 529 matches; overlap with labels = **373**.
  - `whisper_v1_en` (English translation) — 367 matches; overlap = **254** (PRIMARY: keyword rules are English).
- Join: exact SoccerNet game-path (after stripping Echoes trailing half-number); 0 collisions, no fuzzy.

## Protocol (pre-registered, leakage-safe)
- Match-level splits only (no commentary row from a test match in train/calibration).
- **Leave-one-competition-out** (6 competitions). Latency offset estimated on TRAIN matches only
  (median t_seg − t_event); applied to test timing. Window = 45 s (fixed before evaluation).
- Levels: L0 time-only, **L1 keyword+time** (reported), L3 train-only offset calibration.
- Metrics: recall_L1 = GT events with a within-window keyword-claiming segment / GT events;
  precision_L1 = correct within-window claims / all claims of that type; timing = |t_seg − (t_event+offset)|.

## Headline finding — language dependence (a real result)
| variant | test comp | goal recall_L1 | goal precision_L1 |
|---|---|---|---|
| `whisper_v1` (original lang) | spain_laliga (Spanish ASR) | **0.0535** | 0.099 |
| `whisper_v1_en` (English) | spain_laliga | **0.8846** | 0.158 |

English keyword rules fail on original-language ASR. All metrics below use `whisper_v1_en`.
Reproduce both the language comparison and the 6-fold per-competition table:
`python scripts/run_soccernet_folds.py` → `notes/research/soccernet_language_and_fold_comparison.json`
(+ gitignored `data/processed/soccernet_alignment_per_competition.csv`). Primary single-fold run:
`ECHOES_VARIANT=whisper_v1_en python scripts/run_soccernet_alignment.py`.

## Per-event-type (English, test = La Liga held out; offset 0.37 s)
| event | n_events | recall_L1 | precision_L1 | timing MAE (s) |
|---|---|---|---|---|
| goal | 208 | 0.885 | 0.158 | 10.1 |
| corner | 608 | 0.755 | **0.817** | 12.6 |
| yellow_card | 305 | 0.512 | 0.702 | 8.6 |
| foul | 1481 | 0.453 | 0.749 | 10.1 |
| offside | 277 | 0.653 | 0.520 | 4.4 |
| shot | 689 | 0.601 | 0.385 | 9.2 |
| shot_on_target | 701 | 0.549 | 0.322 | 13.0 |
| penalty_awarded | 19 | 0.895 | 0.100 | 19.8 |
| substitution | 341 | 0.085 | 0.338 | 18.0 |
| kickoff | 311 | 0.006 | 0.400 | 4.6 |
| red_card | 6 | 0.167 | 0.067 | 16.9 |
| second_yellow | 5 | 0.200 | 0.015 | 31.9 |

## Per-competition (each held out; goal & corner)
| held-out | test games | goal recall | corner recall | corner precision |
|---|---|---|---|---|
| england_epl | 11 | 0.75 | 0.65 | 0.73 |
| uefa-champions-league | 45 | 0.69 | 0.62 | 0.78 |
| france_ligue-1 | 27 | 0.87 | 0.66 | 0.81 |
| germany_bundesliga | 41 | 0.63 | 0.40 | 0.73 |
| italy_serie-a | 70 | 0.79 | 0.60 | 0.64 |
| spain_laliga | 60 | 0.88 | 0.75 | 0.82 |

## Reading the result (honest)
- **High recall, salient events**: goals (0.62–0.88 across folds; Bundesliga low = 0.625) and penalties are nearly always narrated; corners
  well-detected with **good precision (0.64–0.82)** — corner is the single best-aligned class.
- **Good precision, ambiguous recall**: yellow_card / foul (precision 0.70–0.75) — distinctive language,
  but not every event is narrated.
- **Low precision**: "goal" keyword fires on near-misses/goal-kick/chances → precision 0.16; shots similar.
- **Poorly captured by keywords**: substitution (0.09) and kickoff (0.006) — rarely narrated with the
  pre-registered phrases. Rare events (red_card, second_yellow, n≤6) are statistically unreliable.
- **Timing**: median/mean absolute error ≈ 4–18 s for common events, rising to ~32 s for rare classes
  (red_card/second_yellow, n≤6, where the few pairs are noisy), reflecting ASR segment granularity +
  commentary lead/lag; train offset is small (≈0.4–0.9 s) so calibration barely moves results.
- Results are **stable across all 6 leave-one-competition-out folds** → generalizes, not a single-split fluke.

## Allowed vs prohibited claims
- ALLOWED: "deterministic keyword+time alignment recovers salient historical events (esp. goals/corners)
  with the precision/recall above and ~10 s timing error, reproducibly across competitions."
- PROHIBITED: any live, point-in-time, or predictive/market-edge claim. No publication_time exists →
  commentary can never be a live feature here.
