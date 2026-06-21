# Next Actions — after API-Football coverage check + odds pilot (2026-06-21)

## API-Football viability
- **Auth: works** (direct API-Sports, 32-char hex key). **Coverage: free plan = seasons 2022–2024
  only** — `season=2026` returns 0 with `"Free plans do not have access to this season"`.
- **Live 2026** (fixtures/lineups/events/standings/in-play): **NOT viable on the free tier.** Needs a
  paid plan or another licensed live event feed. football-data.org stays the 2026 results authority.
- **Free silver lining:** 2022–2024 IS covered → API-Football free can supply **2022 WC lineups/
  events/statistics** (≤100/day) for **offline in-play replay** training at no cost.
- Built (no polling): provider interface + quota-aware scheduler with a hard daily-budget guard
  (`src/wcdrawlab/providers/interface.py`, `schedule.py`, tested).

## Odds pilot data-quality verdict
- **PASS (high quality), 0 credits spent** — the 2022 group-stage odds already existed in the repo.
  MD1: 16/16 matches, 0 missing, all strictly pre-kickoff (~94 min lead), 32–35 books, no-vig sums to
  1, raw overround ~1.05 (margin correctly removed), team names canonicalized. Output:
  `data/processed/odds_pilot_2022_md1.csv`; report: `odds_pilot_2022_md1_report.md`.
- Safe to enter the historical modeling table for a market-vs-B1 evaluation (not yet used to tune
  `candidate.py`, per instruction).

## Credits remaining
- **The Odds API: ~13,100 / ~20,000 remaining** (6,900 used). Pilot spent **0**.
- **API-Football: 100 requests/day** free (0 used at check time).

## Exact next recommended action
**Run the market-vs-B1 evaluation on the existing 2022 fold** (no new spend): join
`market_features_2022.csv` into the modeling table as a leakage-safe pre-match feature/probability,
then paired-bootstrap a market-anchored candidate vs B1 on 2022. This is the only evidenced path to
beat Elo on 1X2 and uses data already in hand. (Still gated on your "ok to evaluate" — it does not
spend credits, but it is the step toward a candidate change, which needs your go-ahead.)

Parallel no-cost step: pull **2022 WC events/lineups from API-Football free** (≤100/day, via the new
provider interface + scheduler) to build an **offline in-play replay** scoring set for the existing
in-play model.

## My recommendation on the three options
| option | recommendation |
|---|---|
| Approve a **full 2022 group-stage** odds backfill | **No** — already complete (all 48 matches present). No spend warranted. |
| **Preserve credits for live 2026** | **Yes** — The Odds API is the only viable 2026 odds source (API-Football free can't do 2026). Reserve the ~13,100 credits for 2026 pre-match + in-play capture. |
| **Upgrade a provider plan** | **Optional, deferred** — only upgrade **API-Football** (to a paid tier) *if* live 2026 lineups/events/in-play become a priority. Not required for B1 or for the 2022 market evaluation. |

## Governance (unchanged)
B1/Elo remains the only approved runtime 1X2 model; scoreline + in-play stay research-only; no live
trading; no `.env`/trading/risk/provider-credential edits; `candidate.py` untouched.
