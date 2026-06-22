# Player / Card / Substitution Readiness (Phase 6, 2026-06-22)

Measured against the StatsBomb datasets built in Phase 4. Data provided by StatsBomb.

## Coverage counts
- matches with complete starting XI (both teams, player IDs): **374**
- matches with substitution events (timestamps): **374**
- matches with player IDs: **374**
- matches with position/role data: **374** (StatsBomb lineups carry positions)
- matches with 360 freeze-frames: **218**
- international matches: **314** | club (auxiliary) matches: **60**

## Event counts
- direct red events: **28**
- second-yellow events: **22**
- (red total = 50)
- penalties (shots): **370**
- goals: **1073**

## Class balance (final result, all built matches)
- H=170 D=74 A=130 (n=374)

## Competition coverage
```
competition_type  competition_id  
club              LALIGA_2015_2016    60
international     AFCON2023           52
                  COPA2024            32
                  EURO2020            51
                  EURO2024            51
                  WC2018              64
                  WC2022              64
```

## Readiness gates
- **player / substitution model** (need >=500 matches w/ lineup+subs): BLOCKED (374 < 500)
- **direct-red / second-yellow model** (need >=150 positive events): BLOCKED (50 < 150)
- **next-goal model** (need >=500 matches w/ event timestamps): BLOCKED (374 < 500)

## Honest conclusion
StatsBomb open data contains only ~333 men's **senior international** matches in total, so any
INTERNATIONAL-only player/next-goal model is structurally below the 500-match threshold — this is
**unavailable data**, not a processing gap. Club data could pad the counts, but the protocol
forbids silently mixing domains and club->international transfer is unproven (tested separately
in Phase 5). Red-card events are too sparse for a dedicated red model. Therefore:
- player/substitution model: **BLOCKED (international data ceiling ~333 < 500)**; club-augmented
  training is possible only as a separate, clearly-labelled auxiliary experiment.
- direct-red/second-yellow model: **BLOCKED (too few positive events)**.
- next-goal model: **BLOCKED for international-only**; revisit if StatsBomb adds more men's
  international tournaments, or run explicitly as a club-auxiliary study.
- player-specific causal claims: not attempted (observational data only -> association + uncertainty only).