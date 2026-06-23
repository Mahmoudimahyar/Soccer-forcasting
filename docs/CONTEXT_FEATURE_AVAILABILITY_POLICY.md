# Context Feature Availability Policy (Phase 3 / 7D)

Governs venue/travel/rest/timezone/weather context features. **Research-only**: none of these is fit,
ranked, or added to B1 or any active model in this sprint. Schema: `schemas/context_features_v1.yaml`;
code: `src/wcdrawlab/research/context_features.py`; tests: `tests/test_context_features_7d.py`.

## Planes
- **pre_match** — knowable before kickoff (venue coords/altitude/roof, kickoff times, travel, rest,
  timezone displacement, location sequence, and a weather FORECAST issued before the decision time).
- **in_play** — also valid at an in-play decision time (same set; weather forecast must still be issued
  ≤ decision time).
- **retrospective** — knowable only after the fact (**observed weather**). Never a pre-match/in-play feature.
- **neither** — not contracted.

## Hard leakage rules
1. `feature_available_at <= decision_timestamp` for every feature used in a prediction.
2. **Weather:** only a forecast **issued at/before** the decision timestamp may inform a pre-match or
   in-play feature; store `weather_forecast_issued_at_utc`. **Observed** weather
   (`weather_observation_time_utc`) is retrospective and must NEVER enter a pre-match/in-play feature
   (`weather_feature_eligible("observed", …)` always returns False).
3. **Rest/travel** derive from each team's **previous** match only (strictly earlier kickoff).
4. **Neutral site:** both teams travel; no implicit host advantage.
5. Missing venue/coords → feature is NaN + `missingness_flag`; never silently imputed.

## Required provenance per feature value
`source`, `availability_timestamp`, `weather_forecast_issued_at_utc` / `weather_observation_time_utc`
(as applicable), `missingness_flag`, `leakage_eligibility`.

## Not done in this sprint (by design)
No live weather API calls; no per-fixture weather pull; no model fitting/ranking. Helpers + contract +
leakage tests only. Per-fixture computation requires a venue-coordinate reference + (for weather) an
approved weather source with issued-at timestamps.
