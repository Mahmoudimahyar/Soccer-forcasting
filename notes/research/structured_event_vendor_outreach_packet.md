# Structured Event Provider — Outreach Packet (Phase 5)

A ready-to-send package for the user to give providers. **Nothing here has been sent.** No trials requested,
no forms submitted, no credentials included.

## 1. Project description (share verbatim)
Research-only World Cup and international-football forecasting research. **No live trading.** No redistribution
of raw data. No unauthorized scraping. Outputs are DERIVED research artifacts (aggregate metrics/labels) only.
Data would be stored locally, append-only, for historical research and model training on derived features.

## 2. Exact data request
Historical events (timestamped) + starting lineups + benches + substitutions + stable player IDs + positions
+ cards (yellow / second-yellow / direct-red distinct) + shots + shot locations + xG + formations; for men's
senior international tournaments (World Cup, Euro, Copa America, AFCON, Asian Cup, qualifiers) and — if needed
for sample size — major domestic leagues. Live event updates with publication/update timestamps IF available.

## 3. Exact legal questions
Local storage; local retention; model training on derived features; derived-label creation; aggregate
research publication; commercial future use; attribution; raw redistribution boundary; historical export;
API quotas. (Full list: data_requests/pending/structured_event_vendor_questionnaire.yaml.)

## 4. Exact sample-data request
- 20 historical matches (full events + lineups + substitutions + corrections + source timing metadata).
- 5 live or archived event timelines (with publication + update timestamps).

## 5. Exact acceptance criteria (we will run these before storing/training)
- Data thresholds: >=500 lineup/sub matches; >=500 timestamped-event matches; >=150 red/2nd-yellow examples.
- Schema: unique match + player IDs; per-event timestamps; correction support; sub/lineup/card/shot/xG/position.
- Timing: publication time + update time; historical vs live distinction; no retrospective relabel-as-live.
- Reconciliation: score reconciliation; ordering; low duplicate/missingness; cross-source reconciliation.
- Rights: retention + research + model-training-on-derived + aggregate publication confirmed in writing.
(Machine-readable: data_requests/pending/structured_event_acceptance_criteria.yaml.)

## Provider-specific notes
- Sportmonks / API-Football: published pricing — can start with a paid plan directly once rights confirmed.
- Opta(Stats Perform) / StatsBomb / Sportradar: quote-only — request a scoped quote + sample + the answers above.
- Opta holds FIFA-official World Cup 2026 rights (relevant for WC-specific live/official coverage).
