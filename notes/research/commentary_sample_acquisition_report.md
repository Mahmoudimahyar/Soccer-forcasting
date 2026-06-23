# Commentary Sample Acquisition Report (Phase 4, 2026-06-23)

Gate: download ONLY a source classified `open_research_download_allowed` with `store_raw_text` permitted,
no access-control bypass, registered in the rights schema, raw kept in gitignored `data/raw/commentary/`.
Tool: `scripts/commentary_sample_acquire.py` (safe by default; `--execute` prints the bounded pull command).

## Dispositions
| source | acquisition status | reason / required action |
|---|---|---|
| **soccernet_echoes** | **ELIGIBLE (open, CC BY 4.0)** | bounded pull deferred this session to keep large data out; command provided; adapter ready; data would be historical_weak_supervision_only |
| soccerreplay_1988 | BLOCKED | NDA acceptance required (your decision) |
| sportmonks_commentary | BLOCKED | paid commercial license (your decision) |
| official_match_centers | BLOCKED | copyright/ToS — no scraping |
| news_live_blogs | BLOCKED | copyright/ToS — no scraping |
| yallashoot_arabic | REJECTED | unverified/likely-infringing rights |
| api_football / statsbomb_open | n/a (structured) | not commentary text; used as truth anchors only |

## What was built
- `adapters/soccernet_echoes.py` — normalizes ASR segments into the canonical contract; marks every
  record `historical_weak_supervision_only` (broadcast time only, no publication_time) → never live.
- `scripts/commentary_sample_acquire.py` / `commentary_normalize.py` / `commentary_source_quality_audit.py`
  — gate-checked, fail-closed, no-op without permitted raw data.
- `data/raw/commentary/` + `data/processed/commentary/` (gitignored) with READMEs.
- Adapter test (synthetic): asserts no pub-time + historical-only eligibility.

## Net
Only SoccerNet-Echoes is acquirable now, and only for historical weak supervision/alignment — never
live. No raw copyrighted text was downloaded or committed. Richer commentary needs NDA (SoccerReplay-1988)
or a paid license (Sportmonks) — your external decisions.
