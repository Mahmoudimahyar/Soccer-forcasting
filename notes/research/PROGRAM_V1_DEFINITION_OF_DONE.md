# World Cup Predictor V1 — Definition of Done

V1 is complete only when each item below is **done** or **explicitly blocked with evidence**. Safety
invariants (B1 sole approved model; paper-only; no protected-file edits) hold throughout.

## 1. Data & source plane
- [x] all configured providers safely audited (`source_readiness_audit.md`, `api_football_diagnostic.md`)
- [x] direct API-Football configuration classified (auth works; **free tier = seasons 2022–2024 only**)
- [x] historical/local sources catalogued (`data_inventory.md`, `source_provenance.json`)
- [x] append-only provenance + reconciliation contracts (`ingestion/`, `EVENT_RECONCILIATION_POLICY.md`)
- [x] durable collector design tested in dry-run (`five_hour_supervisor.py`, integrity validators)
- [x] high-value unapproved sources as structured data requests (`data_requests/pending/`)

## 2. Pre-match plane
- [x] B1/Elo reproducible (tier-2 gate; reconciliation audit)
- [x] incremental features tested with temporal holdouts (B0–B7; market shadow; no candidate beats B1 significantly)
- [x] no feature promoted without calibration + bootstrap (enforced; none promoted)
- [~] market/lineup/weather/travel/tournament-state kept separate until valid data — **partially BLOCKED**
  (no pre-2020 dev-fold odds; lineups need approved feed)

## 3. In-play plane
- [~] multi-competition event-state dataset — **BLOCKED** (only 2022 available without approval)
- [x] 2022 WC replay preserved as validated reference (`event-replay-2022-validated`)
- [x] simple before complex (M0→M5)
- [x] W/D/L + remaining-goal + next-goal + horizon evaluated honestly (sprint 1)
- [x] match/competition-level holdouts (leave-one-group-out + match bootstrap)
- [x] no training on future info (leakage tests)

## 4. Player & tactical plane — **BLOCKED**
- [ ] lineups/benches/subs/player IDs/positions/on-pitch state — needs approved lineup/event feed
- [ ] substitution effects as uncertain state updates — needs player IDs/positions
- [ ] disruption/fatigue/travel/weather/referee retained only if they improve holdouts — needs the features
- [x] red-card modeling remains blocked (7 positives/858 — insufficient) — correctly blocked

## 5. Shadow-validation plane
- [x] durable restart-safe low-cost collector exists (supervisor + resume + state)
- [x] predictions frozen before decision points (immutable ledger)
- [x] ledger has model ID, source hashes, decision timestamp, approval status
- [~] multi-match shadow eval **after** in-play models have sufficient historical evidence — **BLOCKED**
  (no in-play model is shadow-ready on 2022 alone)
- [x] no live trading enabled

## 6. Final program report
- [x] model registry (approved vs experimental)
- [x] data registry (usable vs blocked)
- [x] every claimed gain has reproducible evidence
- [x] limitations explicit
- [x] exact V2 next work documented

## Terminal state
V1 reaches **complete** only if planes 3/4/5 are satisfied. Planes 3 (multi-competition), 4 (player),
and 5 (shadow-ready) all require **approved new data** (StatsBomb open sign-off, paid event/xG feed, or
authorization to spend API-Football quota across many days) → these are **external blockers**.
Therefore V1's expected terminal state is **externally blocked** (tag `worldcup-predictor-v1-blocked`),
not complete, until a multi-competition event source is approved.
