# Prospective Score Harvest — Blockers

(none confirmed yet — populated only with evidence)

## Watch items
- Result freshness: football-data.org free tier must currently report 06-24..06-28 WC matches as FINISHED.
  If it lags, fall back to API-Football Pro (`API_FOOTBALL_KEY` SET) per the result-source hierarchy.
  If neither verifies a given fixture's final result, that fixture → `awaiting_final` and the program's
  terminal state for it is WAITING_FOR_FINAL_RESULTS (not a stop for the already-final fixtures).
- Knockout fixtures not yet scheduled/played are outside the locked completed-pool universe.
