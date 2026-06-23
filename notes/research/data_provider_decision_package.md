# Data Provider Decision Package (Phase 5, 2026-06-23)

Goal: unblock the player/substitution, next-goal, and card model classes, which are below threshold on
StatsBomb open data (men's-international ceiling ~333 matches; 50 red events). **No provider is
purchased, subscribed to, scraped, or integrated here** — this is a decision package using official
sources only. Thresholds to clear: 500 complete-lineup/substitution matches; 500 event-timestamp
matches (next-goal); 150 direct-red/second-yellow positive events.

## Paths compared (official sources)
### A. StatsBomb (commercial / Hudl StatsBomb) — quote-based
- Coverage: extensive incl. men's internationals over many years; **best-in-class shot xG, 360
  freeze-frames, full event timestamps, lineups/benches, subs, cards, player IDs, positions**.
- Licensing: commercial; **open tier is non-commercial research only** (we already use it + have the
  schema/loaders). Academic/research licensing may exist — quote only (no public price).
- Live latency: low (commercial feed). Export/API: yes (commercial API + bulk).
- Injury/suspension: limited (event data, not a medical feed).
- Threshold fit: **can meet 500/500 easily; 150 reds plausible across its full catalogue.**
- Value: highest for next-goal (per-shot xG) and player/tactical (360). Reuses our existing pipeline.

### B. Opta / Stats Perform — enterprise, quote-based
- Coverage: gold-standard, decades of internationals + qualifiers; full events/xG/lineups/subs/cards/
  player IDs/positions; injuries/suspensions via additional feeds.
- Licensing: enterprise contract; **research/paper eligibility must be negotiated**; typically the most
  expensive. Export/API: enterprise API/feeds. Live latency: lowest.
- Threshold fit: **comfortably meets all thresholds.** Value: highest, but cost + contract overhead
  are the largest; new schema integration required (we have no Opta loader).

### C. Sportmonks — self-serve, PUBLISHED pricing (lowest-cost path)
- Pricing (official, self-serve): **Starter €29/mo (€23 yearly, 5 leagues); Growth €99/mo (€79 yearly,
  30 leagues); Pro €249/mo (€199 yearly, 120 leagues)**. **xG add-on extra (~€19–99/mo)**; **historical
  data >3 seasons = one-time add-on (price on request)**; WC-2026 plans ~€69/€129/mo.
  Realistic config for our need (internationals history + xG): **Growth (~€79–99/mo) + xG add-on +
  one-time historical archive ≈ €100–200/mo + one-time fee**.
  ([plans](https://www.sportmonks.com/football-api/plans-pricing/),
  [pricing setup](https://www.sportmonks.com/blogs/introducing-our-new-pricing-setup/)).
- Coverage: 2500+ leagues incl. internationals; events (timestamped), lineups/formations, subs, cards,
  player IDs/positions, squads; **xG via add-on (recent-leaning; older-international xG depth weaker
  than StatsBomb/Opta)**. Injury feeds available as add-ons.
- Licensing: commercial API, self-serve; research/paper use permitted under standard terms.
  Export/API: REST API. Live latency: low.
- Threshold fit: **500 lineup/sub + 500 event-timestamp: plausible via the historical archive.**
  **Shot/xG depth for the next-goal model: marginal** (add-on, recent bias). **150 reds: likely still
  short from internationals alone** → would need club competitions pooled (domain-shift caveat).

## Threshold matrix (men's international focus)
| requirement | StatsBomb commercial | Opta/Stats Perform | Sportmonks |
|---|---|---|---|
| 500 lineup/sub matches | yes | yes | plausible (archive) |
| 500 event-timestamp matches | yes | yes | plausible (archive) |
| 150 red/2nd-yellow events | plausible (full catalogue) | yes | likely needs club pooling |
| per-shot xG quality | best | best | marginal (add-on) |
| reuses existing pipeline | **yes** | no | no |
| pricing transparency | quote | quote | **public/self-serve** |

## RECOMMENDATION (one)
**Lowest-cost path that can plausibly meet the thresholds: Sportmonks** — base plan + **xG add-on** +
the **historical archive one-time purchase**, scoped to men's international competitions (+ a club
block only if the 150-red threshold needs it).
- **Exact action you would take:** create a Sportmonks account; subscribe to a base plan that includes
  fixtures/events/lineups; add the **xG add-on**; purchase the **historical archive** for the target
  international competitions; place the API key in `.env` as a NEW variable (e.g. `SPORTMONKS_KEY`).
  Then approve it as a source (a `data_requests` entry → approved).
- **If per-shot xG depth proves insufficient** for the next-goal model after a coverage probe, escalate
  to **StatsBomb commercial/academic** (quote) — it reuses our existing StatsBomb loaders/schema and is
  the cheapest *high-xG-quality* option; Opta only if enterprise coverage/latency is required.
- **Work that can begin immediately after approval:** (1) a read-only Sportmonks adapter mirroring the
  API-Football adapter's safety; (2) extend the StatsBomb-style in-play builder to the licensed feed;
  (3) re-run the readiness gate — once ≥500 lineup/sub + ≥500 event-timestamp matches exist, build the
  player/substitution and next-goal models under the existing nested-CV protocol; (4) pool club data
  (clearly labelled) only if reds < 150.

## Honest caveats
- The 150-red threshold is the hardest; even 500 internationals yield only ~75–100 reds, so a red model
  may require club pooling regardless of provider.
- xG quality matters most for the next-goal model; if budget allows, StatsBomb commercial is the better
  value for that specific plane despite the quote process.
