# Full Corpus Execution Protocol (Phase 1)
research_only. Uses the ALREADY-predeclared player-history fixture manifest (no substitute sample; no
content-based selection). Manifest: data/reference/full_corpus_execution_manifest.{csv,json}.
- all_eligible_fixtures: 2,000 (5 leagues x 4 seasons x 100, hash-stratified fixed seed).
- complete (events+lineups valid): 60. outstanding: 1,940. manifest_completion_rate: **0.03**.
- Gate #2 (>=95%): **NOT MET**. Completion requires the durable run (events+lineups for 1,940 fixtures =
  ~3,880 API-Football requests) which EXCEEDS one day's research budget under the 25% reserve policy ->
  genuinely MULTI-DAY / quota-bounded. Resumable; append-only; never re-pull valid responses.
