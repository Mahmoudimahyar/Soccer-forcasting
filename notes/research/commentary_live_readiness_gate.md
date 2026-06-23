# Commentary Live Readiness Gate — Result (Phase 6, 2026-06-23)

| source | gate result | why |
|---|---|---|
| soccernet_echoes | ready_for_historical_weak_supervision | open rights, but broadcast time only (no publication_time) |
| statsbomb_open | ready_for_historical_weak_supervision | structured truth anchor; no commentary pub time |
| soccerreplay_1988 | provider_approval_required | NDA (your decision); also no original pub time |
| sportmonks_commentary | provider_approval_required | paid license (your decision); pub-time/lag to verify |
| api_football | provider_approval_required | structured events, not commentary text |
| official_match_centers | rights_blocked | copyright/ToS, no scraping |
| news_live_blogs | rights_blocked | copyright/ToS, no scraping |
| yallashoot_arabic | rejected | unverified/likely-infringing |

**No source is live-eligible.** The only path to a *delayed-live shadow test* is a licensed feed
(Sportmonks) AFTER verifying publication timestamps + measured lag + ID resolution + alignment quality —
all gated behind your paid-provider decision. Tests prove: unknown-pub-time never live; rights-uncertain
never live; post-decision lines blocked; safety lag enforced; commentary modules are NOT imported by
runtime/trading (hard isolation).
