# Structured Event Provider Questionnaire (no credentials)

Research-only World Cup / international football forecasting. No live trading; no raw-data redistribution; no scraping. Derived research outputs only.

## rights
- May we store your data locally (append-only) for research?
- May we use it for historical research and model training on DERIVED features?
- May we publish AGGREGATE derived metrics/labels (no raw data)?
- Any restriction on commercial future use? Attribution required?
- Raw redistribution: prohibited / conditional? Historical export allowed?

## coverage
- How many complete lineup+substitution matches across men's senior internationals (+ major leagues)?
- How many matches carry per-event TIMESTAMPS (match clock + update/publication time)?
- How many direct-red / second-yellow examples across your historical coverage?
- Which historical seasons carry full event/xG/lineup granularity? Competition IDs?
- World Cup + Euro/Copa/AFCON/Asian Cup coverage + depth?

## schema
- Stable unique match IDs and player IDs? Bench/substitute lists included?
- Card semantics (yellow / second-yellow / direct-red distinct)?
- Shot + shot-location + xG semantics? Position/formation fields?
- Substitution semantics (on/off + minute)? Event correction support?

## causal_availability
- Do events carry a source publication time and a provider update time?
- Published live latency? Historical vs live feeds clearly distinguished?
- Are retrospectively-corrected events ever relabeled as live? (must be no)

## quality
- Score reconciliation guarantees? Event ordering? Duplicate + correction rates? Missingness?

## operational
- Rate limits? Historical backfill practicality? Append-only raw export? Resumability? Quota budgeting? Documented retry behavior?

## sample_data_request
- 20 historical matches (events + lineups + subs + corrections + source timing metadata)
- 5 live or archived event timelines with publication/update timestamps

> Do NOT send API keys or account credentials in your reply; documentation + a sample export are sufficient for evaluation.