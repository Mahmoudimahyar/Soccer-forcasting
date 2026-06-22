# Program Blockers (require external action; program continues around them)

## BLK-1 — Multi-competition historical event data (HIGHEST)
- Need event-level data (goals/cards/subs + ideally shots/xG/lineups) across many tournaments; 2022
  WC alone (48 matches) is too small for player/card/next-event models.
- Cause: no approved multi-competition source. Options: StatsBomb open (free, non-commercial — needs
  license sign-off), paid event/xG provider, or authorization to spend API-Football free quota
  (2022–2024 only) across many days.
- Action needed: approve one source (`statsbomb_open_data.yaml` / `tier4_event_xg_feed.yaml`).

## BLK-2 — xG / shots / lineups / on-pitch player IDs
- Absent from the API-Football free-tier events → player & tactical plane and next-goal hazard blocked.
- Action: API-Football Pro (~$25–30/mo) for live lineups/events, or a paid xG feed.

## BLK-3 — Live 2026 events (API-Football free season gate)
- Free plan = seasons 2022–2024 only; cannot serve 2026 live. Action: API-Football Pro upgrade.

## BLK-4 — Pre-2020 dev-fold odds
- No clean, timestamp-valid, openly-licensed source for 2010/2014/2018 WC odds → market models cannot
  clear the frozen dev-fold promotion protocol. Action: none cheap; accept market as shadow-only.

## BLK-5 — Red-card / rare next-event volume
- 7 `red_within_10` positives in 858 rows → unlearnable. Resolved only by BLK-1 (more data).

No blocker stops the program: all independent unblocked work proceeds; these gate only the
player/multi-competition/shadow-ready planes.
