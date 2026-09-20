# Commentary Data Licensing Policy (Phase 2)

Governs acquisition + use of soccer commentary text. research_only / not_runtime_approved /
not_trade_eligible. Authoritative per-source rights: `schemas/commentary_source_rights_v1.yaml`.

## Hard rules
- Each source gets exactly ONE classification (11-value enum). Default for every use = DENIED until an
  explicit official term permits it.
- **No scraping** of any source with uncertain or prohibited terms; **no automated browser extraction**
  from news/match-center sites unless their official terms explicitly permit automated retention + modeling.
- **No raw copyrighted commentary text in Git, ever.** Raw payloads (where permitted) live only in
  gitignored `data/raw/commentary/`, append-only.
- **Tests use only synthetic text written by us** — never copyrighted commentary.
- Use-types are distinct and separately gated: store_raw / store_hashed / store_derived_labels /
  train_on_text / evaluate_on_text / show_in_product / use_as_live_input / redistribute / commercial.
- `use_as_live_input` additionally requires the Phase-6 causal gate (publication_time <= decision_time);
  rights permission alone is never sufficient for live use.

## Current dispositions (see rights schema for the full matrix)
- **soccernet_echoes** — CC BY 4.0: download/train/eval/redistribute OK w/ attribution; **live blocked**
  (no publication_time).
- **soccerreplay_1988** — NDA: ALL uses blocked until YOU accept the NDA.
- **sportmonks_commentary** — commercial: ALL uses blocked until a paid license (your decision).
- **statsbomb_open / api_football** — structured (not prose); used as truth anchors only.
- **official_match_centers / news_live_blogs** — copyright/ToS: do NOT scrape.
- **yallashoot_arabic** — rejected (unverified rights).
