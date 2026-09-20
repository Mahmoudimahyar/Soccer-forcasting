# Commentary V2 — Data Decision Package (Phase 6)
research_only / historical_weak_supervision_only / not_live_eligible. Decisions follow the FROZEN gate.

## Multilingual limitation (quantified)
- Keyword/classifier pipeline is English. Reproduce: `python scripts/run_soccernet_folds.py`.
- English-translation (whisper_v1_en) goal recall 0.88 vs original-language (whisper_v1) 0.05 on the same
  held-out league -> the pipeline does NOT generalize to original-language ASR. 162 original-language-only
  games exist but are out of scope for an English pipeline. Building broad multilingual models is NOT
  justified by the source rights/value here.

## Decisions
### Is further SoccerNet work worth doing?
Marginal. Under the frozen high-precision bar, **0 classes qualify as silver**. corner/foul/yellow_card are
usable only as ~0.73-0.77 Wilson-LB LOW-CONFIDENCE historical signals. Diminishing returns for a
high-precision silver product; the ceiling on this source (keyword polysemy + proximity-label noise +
per-competition instability) is ~0.79 aggregate precision for the best classes.

### Which event classes are worth retaining?
- Retain (low-confidence flagged, historical only): corner, foul, yellow_card.
- Drop for silver: goal, shot, shot_on_target, penalty_awarded (low precision); offside, substitution,
  kickoff, red_card, second_yellow (insufficient coverage).

### Does SoccerNet support player / substitution research?
**No.** SoccerNet v2 action labels carry NO player IDs; substitution emits 43 high-confidence labels
(insufficient_coverage) and subs are barely narrated. Player-level research is unsupported by this source.

### Does it support red-card research?
**No.** 29 red-card events total; 30 emitted at precision 0.27 -> insufficient coverage AND precision.

### Does it support next-goal research?
**No.** Goal precision is 0.16 (rules) / 0.67 (abstention, n=76, Wilson LB 0.56), and there is NO
publication_time -> no live/point-in-time capability. Cannot support next-goal modeling.

### Is SoccerReplay-1988 likely to add unique value?
Plausibly for HISTORICAL richness (denser aligned commentary; potentially finer event/player detail than
v2). It does NOT solve the live problem (still no trustworthy publication timestamps) and requires an NDA.
Worth considering only if richer historical alignment is the goal; not a path to live or to the precision bar.

### Is a paid LIVE commentary provider still necessary for any live use?
**Yes.** SoccerNet-Echoes is historical-only by construction (no publication_time). Any live/delayed-live
use requires a paid feed with verified publication timestamps + the causal gate.

### Is a commercial STRUCTURED event provider still necessary for player/next-goal/card modeling?
**Yes.** SoccerNet labels lack player IDs and the commentary silver labels fail the precision bar. A paid
structured provider (Sportmonks lowest-cost; StatsBomb/Opta richer) remains the route for player/next-goal/
card models. Unchanged from the prior provider decision package.

## Bottom line
SoccerNet commentary is a useful HISTORICAL alignment + taxonomy research asset and a source of LOW-CONFIDENCE
weak signals, but NOT a high-precision silver-label source and NOT a substitute for a paid structured
provider or a paid live feed. Higher-value next investment = paid structured event provider (player/next-goal/
card) > paid live commentary (live use) > SoccerReplay-1988 NDA (historical richness) > more SoccerNet tuning.
