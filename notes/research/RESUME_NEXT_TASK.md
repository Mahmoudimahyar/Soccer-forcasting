> [!WARNING]
> **SUPERSEDED / CORRECTED (banner added 2026-09-20; original text kept unedited below).**
>
> **What this file is:** an agent session-state file last updated on 2026-06-21, not the project's current next
> task. The tasks below were later carried out or overtaken by subsequent work.
>
> **In-play status line:** M2 as a "SHADOW-CANDIDATE (beats M1 on 3/3 held-out competitions)" is an early
> 108-match reading. In the later nested evaluation on 302 matches, the selected model (plain M2 in 4 of 6
> folds) did not differ significantly from M1 (dRPS −0.0042, 95% CI [−0.0083, +0.0002]). M2 is now simply the
> unfitted reference model (hand-set constants), and no in-play model was ever scored prospectively.
>
> See [inplay_evaluation_reconciliation.md](inplay_evaluation_reconciliation.md),
> [inplay_nested_evaluation.md](inplay_nested_evaluation.md), the [notes index](README.md) and the [glossary](../../docs/GLOSSARY.md).

# Resume — exact next task

**State: World Cup Predictor V1 IN PROGRESS (not blocked).** Multi-competition in-play is unblocked on
the API-Football free tier (2022–2024). Built WC2022 + Euro2024 + Copa2024 (108 matches, 1934 rows);
**M2 remaining-time Poisson is a research-only SHADOW-CANDIDATE** (beats M1 on 3/3 held-out
competitions). B1 sole approved pre-match model; paper-only.

## Next tasks (in order)
1. **Widen the competition set (free tier; needs additional daily quota windows — not blocked, just
   rate-paced):** fetch AFCON 2023 (league 6, season 2023), UEFA Nations League (league 5), and
   friendlies via `scripts/build_multicomp_inplay.py`, then re-run `scripts/evaluate_inplay_multicomp.py`.
   Each tournament ≈ (group matches) event calls at ≥7s spacing; respect 100/day + reserve.
2. **Recalibrate M2's draw probability** (cross-fitted; slope 0.76 → ~1.0) and re-test SHADOW criteria.
3. **Player / tactical plane = BLOCKED (BLK-2):** needs lineups / on-pitch player IDs / xG. Approve
   **API-Football Pro (~$25–30/mo)** or a paid xG feed; then add lineup/shot columns to
   `build_state_for_competition` and re-run M3/M4 + substitution-impact models.
4. **Live 2026 in-play (BLK-3):** also needs API-Football Pro (free tier season-gated to 2022–2024).

## Quota note
This session spent most of the day's free API-Football quota (WC cached + Euro 36 + Copa 24). Further
competition fetches need the **daily quota reset** (next day) — an access/rate limit, not a hard block.

## Guardrails (unchanged)
No live trading; do not modify candidate.py / approved routing / trading / risk / Kalshi / .env /
provider credentials / scraping policy. M2 stays research-only; runtime promotion needs separate human
approval. Full detail: `inplay_multicompetition_results.md`, `program_model_registry.md`,
`PROGRAM_STATE.yaml`, `DURABLE_COLLECTOR_AND_SCHEDULER.md`.
