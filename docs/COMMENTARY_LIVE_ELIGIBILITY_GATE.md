# Commentary Live-Eligibility Gate (Phase 6)

A source is `live_eligible` ONLY if ALL hold (fail-closed):
1. explicit rights allow the relevant API/data use;
2. original/trustworthy publication timestamps exist;
3. publication time is comparable to the prediction decision time;
4. measured update delay OR a defensible conservative safety lag is available;
5. match/event IDs resolve reliably;
6. event alignment passes the source-quality threshold;
7. source reliability is adequate during live matches;
8. no unsupported scraping is required;
9. live data can be captured append-only with raw source hashes;
10. no retrospective line is ever used as if it were live.

Source classes: ready_for_historical_weak_supervision / ready_for_historical_alignment_research /
ready_for_delayed_live_shadow_test / not_ready_for_live_use / rights_blocked / timestamp_blocked /
coverage_blocked / quality_blocked / provider_approval_required.

Validator: `scripts/validate_commentary_live_eligibility.py` (fail-closed; exits non-zero if any source
is wrongly live-eligible). Current result: **no source is live-eligible.**
