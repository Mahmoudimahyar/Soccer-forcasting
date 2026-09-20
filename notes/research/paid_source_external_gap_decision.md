# Paid Source External Gap Decision (Phase 6)
research_only. What still genuinely requires an EXTERNAL action vs what is now feasible on already-paid sources.

## Now feasible WITHOUT a new provider (already-paid API-Football Pro)
- Historical player/substitution, card (yellow), next-goal, in-play W/D/L research — data verified clean
  (100% lineup/player-ID, dup 0.0005, 90% reconcile). Reach 500/500 thresholds via a larger BOUNDED backfill
  (budget-reserved; 2,180 matches available). No purchase needed.

## Still requires EXTERNAL action
1. **xG / shot-location / shot-quality research**: API-Football cannot supply per-shot xy + only partial xG.
   -> needs a richer provider (Opta/StatsBomb) OR confirmation that an API-Football xG add-on covers history.
   This is the ONE class a new/added paid source is still genuinely needed for.
2. **Rights in writing** (model-training-on-derived / redistribution / commercial future use): API-Sports ToS
   confirmation -> vendor/legal decision (research use of self-pulled data under the paid plan is in scope now).
3. **Red-card volume (>=150)**: not external per se — needs ~1,200-match backfill (add major leagues); bounded
   by research budget over multiple days, not a new purchase.
4. **Live/delayed-live shadow**: needs measured latency + causal gate before any live use (engineering, future).

## Decision
Do NOT buy another provider for player/sub/card/next-goal/in-play work — API-Football Pro is sufficient.
Only reconsider a richer provider (or xG add-on) IF xG/shot-quality research becomes a priority. Confirm
API-Sports retention/training/redistribution terms before any productization.
