# Weather / Travel / Rest / Venue Readiness (Phase 3 / 7D, 2026-06-23)

Data-readiness + causal-safety work only. **No weather/travel feature was added to B1 or any active
model; no live weather API call was made; nothing was fit or ranked.**

## Delivered
- **Leakage-safe helpers** (`context_features.py`): `haversine_km`, `travel_distance_km` (neutral-site:
  both teams travel), `rest_days`, `timezone_displacement_hours`, `weather_feature_eligible`
  (forecast-issued-before-decision only; observed never eligible), plus the existing
  `build_context_features` (rest/travel from each team's PREVIOUS match).
- **Feature contract** (`schemas/context_features_v1.yaml`, 14 features) classifying each by plane
  (pre_match / in_play / retrospective / neither), known-before-kickoff, retrospective-only,
  computable-now, required source, and leakage risk.
- **Availability policy** (`docs/CONTEXT_FEATURE_AVAILABILITY_POLICY.md`).
- **Quality table** (`data/processed/venue_fixture_context_quality.csv`): 14 features, 13 pre_match + 1
  retrospective (observed weather).
- **8 leakage/computation tests** (`tests/test_context_features_7d.py`), all passing.

## Per-feature readiness summary
- **Computable now from existing data:** kickoff_utc, rest_days, match_location_sequence, and (given a
  venue-coordinate reference) venue lat/lon/altitude, travel_km, timezone displacement.
- **Needs a source not pulled this sprint:** roof/indoor status (venue reference), weather forecast
  (approved weather API with issued-at timestamps).
- **Retrospective only (excluded from features):** observed weather.

## Blockers / next steps (true)
- A **venue-coordinate + timezone reference** for all 2026 venues is required to compute per-fixture
  travel/timezone at scale (the helpers + contract are ready; the reference table is the missing input).
- A **weather forecast source with issued-at timestamps** is required before any weather feature can be
  used pre-match (leakage rule already enforced in code). No live weather call was made here by design.
- These are data-availability items, not modeling work. No causal/weather model is built or claimed.
