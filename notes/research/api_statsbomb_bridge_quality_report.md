# API-Football ↔ StatsBomb Open-Data Match Bridge — Quality Report (Phase 3, xG bridge)

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Builder: `api_statsbomb_bridge_v1` · Feature builder: `xg_event_state_v1`
Inputs: API-Football historical corpus (gitignored) + StatsBomb Open Data (gitignored, never committed).
Raw external data is **not** tracked; only derived hashes/counts/metrics are.

## 1. Scope

Senior MEN'S INTERNATIONAL competitions present in BOTH StatsBomb open data AND the API-Football corpus:

| Competition | API (league.id, season) | StatsBomb (competition_id, season_id) |
|---|---|---|
| FIFA World Cup 2018 | (1, 2018) | (43, 3) |
| FIFA World Cup 2022 | (1, 2022) | (43, 106) |
| UEFA Euro 2020 | (4, 2020) | (55, 43) |
| UEFA Euro 2024 | (4, 2024) | (55, 282) |
| Copa America 2024 | (9, 2024) | (223, 282) |

StatsBomb data acquired only from `github.com/statsbomb/open-data` (already-public) via `urllib` over
`raw.githubusercontent.com` (resumable, no auth, no secrets). License: StatsBomb Open Data (non-commercial
research, attribution). Raw lands in `data/raw/statsbomb_open/` (gitignored).

## 2. Exact-bridge acceptance rule (ALL must hold)

1. **Exact competition + season** — fixed mapping above (no cross-tournament linking).
2. **Exact normalized team agreement** — `normalized(home)==normalized(home)` AND `normalized(away)==normalized(away)`,
   orientation-aware (a swapped-orientation StatsBomb row is accepted only if the score also swaps).
   Normalization is an **exact alias fold** (e.g. `USA→United States`, `Czechia→Czech Republic`,
   `FYR Macedonia→North Macedonia`, mojibake `T�rkiye→Turkey`), **not** fuzzy/probabilistic matching.
3. **Exact kickoff-DATE agreement** — API-Football fixture UTC calendar date == StatsBomb `match_date`.
4. **Exact final-SCORE agreement** — StatsBomb `(home_score, away_score)` (regulation, or after-ET for
   knockout; shootout excluded by StatsBomb convention) == API-Football after-90+ET cumulative
   `(fulltime + extratime_increment)`, shootout excluded. *(Verified: API `score.extratime` is the ET
   increment, not a cumulative — e.g. WC2022 final ft 2-2 + et 1-1 = 3-3 = StatsBomb 3-3.)*
5. **Unambiguous** — exactly ONE StatsBomb candidate on the same comp-season + date + team-pair.
   0 → unmatched; >1 → ambiguous (**rejected, never guessed**).

Any ambiguity, date mismatch, or score mismatch **rejects** the pair with a recorded reason. The bridge
is a pure function of its inputs (deterministic rebuild; covered by tests).

## 3. Results — ACTUAL matched international game count

**258 exact-matched senior men's international games** (sole bridge-confidence tier: `exact`).

| Competition | API fixtures | StatsBomb matches | Accepted (exact) | Rejected |
|---|---|---|---|---|
| FIFA World Cup 2018 | 64 | 64 | **64** | 0 |
| FIFA World Cup 2022 | 64 | 64 | **64** | 0 |
| UEFA Euro 2020 | 313 | 51 | **51** | 262 |
| UEFA Euro 2024 | 51 | 51 | **51** | 0 |
| Copa America 2024 | 32 | 32 | **28** | 4 |
| **Total** | 524 | 262 | **258** | 266 |

Result-type split of accepted: regulation 230, after-extra-time 8, penalty-shootout 20. All accepted rows
are same-orientation. Accepted-bridge digest: `c43a30b5…336e4d` (stable across rebuilds).

### Rejections (honest accounting)
- **`no_statsbomb_candidate` (254)** — almost entirely UEFA Euro 2020: the API corpus holds 313 fixtures
  for Euro 2020 (finals **plus qualifiers**), while StatsBomb open data covers only the **51 finals**
  matches. The 262 Euro-2020 rejects are qualifiers/play-offs with no StatsBomb finals counterpart — a
  correct rejection, not a linkage failure.
- **`date_mismatch` (12)** — team pair exists in the comp-season but on a different calendar date. Of
  these, **4 are genuine Copa America 2024 games** (Peru–Canada, Ecuador–Jamaica, Panama–USA,
  Colombia–Costa Rica): all kicked off 22:00 UTC, which StatsBomb records under the **previous local
  (US Central) match date**. This is a real timezone date-boundary disagreement; the strict rule
  **rejects rather than fuzzy-merges**. They are recoverable later with an explicit ±1-day timezone rule
  (deliberately NOT applied here to keep the bridge exact and conservative). The remaining 8 are
  Euro-2020 qualifier date artifacts.

**No score mismatches and no ambiguous matches occurred** on the real corpus — the exact-score and
exact-date constraints fully disambiguated every candidate that survived team+comp matching.

## 4. xG event-state feature coverage (this bounded run)

Raw events are acquired as a **bounded sample** (`--events-per-comp 12` → 60 event JSONs). Causal xG
features were built for the **58** bridged games whose events are on disk:

| Competition | games with features |
|---|---|
| FIFA World Cup 2018 | 12 |
| FIFA World Cup 2022 | 12 |
| UEFA Euro 2020 | 12 |
| UEFA Euro 2024 | 12 |
| Copa America 2024 | 10 |
| **Total** | **58** (986 feature rows = 58 × 17 decision minutes) |

The bridge itself covers all **258** games (match-list level). Full xG-feature coverage for all 258 is a
re-run away: `python scripts/acquire_statsbomb_open.py --events-per-comp -1` then rebuild features. The
**xG-fusion sample is therefore bounded by 258 international games** (58 currently feature-built).

## 5. Honesty notes / limitations

- 258 international games is a **small** fusion sample; treat any xG-fusion signal as low-powered and
  validate with leave-one-competition-out before any promotion. (Aligns with the frozen preregistration:
  intl-only LOCO, no 2026 tuning, no promotion on this evidence alone.)
- The 4 Copa timezone rejects mean the *bridgeable* Copa universe is effectively 28/32 until a timezone
  rule is added; documented rather than silently merged.
- StatsBomb event timestamps are **match-clock minutes**, not live publication times; features use them
  only as in-match elapsed time (see the data card and `build_xg_event_state_features.py`).

## 6. Reproduce

```bash
python scripts/acquire_statsbomb_open.py --events-per-comp 12     # bounded raw (gitignored)
python scripts/build_api_statsbomb_match_bridge.py               # -> bridge csv + audit json (gitignored)
python scripts/build_xg_event_state_features.py                 # -> xg event-state features (gitignored)
python -m pytest tests/test_statsbomb_bridge.py -q              # 15 synthetic tests, no network
```
