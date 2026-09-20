# Club-to-International Transfer Protocol (Phase 6)
research_only. Hypothesis NOT assumed to hold.

## Rule
- Club data is AUXILIARY ONLY (pretraining / feature priors / regularization), never a test set for an
  international claim.
- Evaluate ONLY on held-out INTERNATIONAL competitions (leave-one-international-tournament-out).
- NEVER train and test on mixed club/international rows without explicit domain labels.
- Report international-only metrics; club metrics are diagnostic, not the claim.

## Design
1. Partition rows by comp_type (international vs club) — enforced by the dataset builder.
2. Baseline A: international-only model (no club data).
3. Experiment B: club-as-auxiliary (pretrain on club, fine-tune/evaluate on held-out international).
4. Transfer is supported ONLY if B beats A on held-out international competitions with calibrated probabilities;
   otherwise report "transfer not supported" (a valid negative).
5. Domain shift risks (club tempo/sub patterns differ from international) documented; no silver-bullet claim.
