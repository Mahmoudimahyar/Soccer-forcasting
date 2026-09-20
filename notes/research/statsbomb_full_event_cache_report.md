# StatsBomb Full Event Cache — Report (research_only)
Official source: StatsBomb Open Data (github.com/statsbomb/open-data via raw.githubusercontent.com). No scrape,
no mirror, no paid product, no video, no 360, no unrelated competitions.
- Exact API-Football <-> StatsBomb bridge matches: 258 (all bridge_confidence=exact).
- Availability probe (deterministic sample): 5/5 missing matches resolved with xG fields + exact identity.
- Cache completion: 258/258 valid cached event files (100%), all with xG fields. Hard gate ceil(0.90*258)=233 MET.
- Validation per file: JSON parses; event `index` ordered; team identity matches bridge (sb_home/sb_away);
  xG-field presence checked. Recorded per match: canonical+StatsBomb ids, source URL, retrieval ts, file sha256,
  event count, xG availability, parse/bridge status, error class. Resumable first-write-wins; <=4 concurrent;
  exp backoff; <=2 retries; 2-min heartbeat; append-only manifest. Canonical root via registry
  (data/raw/statsbomb_open/events), gitignored. Audit: data/reference/statsbomb_cache_audit.json.
