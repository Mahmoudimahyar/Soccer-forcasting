# Commentary Data Provider Decision Package (Phase 7, 2026-06-23)

Procurement-ready ranking. Nothing purchased/subscribed/scraped. research_only.

## Rankings by use-case
- **A. Historical event-label enrichment:** StatsBomb open (structured, already held) > Sportmonks (paid).
- **B. Commentary-to-event extraction research:** SoccerNet-Echoes (open, CC BY 4.0) > SoccerReplay-1988 (NDA).
- **C. Historical player/sub/card expansion:** Sportmonks (paid) or StatsBomb commercial (paid) — open
  data caps coverage; no zero-cost path meets the 500/150 thresholds.
- **D. Delayed-live shadow use:** Sportmonks Match Commentary (paid) — only realistic timestamped feed;
  must verify publication time + measured lag before any shadow test.
- **E. True live in-play prediction:** Sportmonks (paid) IF the live causal gate passes; otherwise NONE.
- **F. Multilingual commentary coverage:** SoccerNet-Echoes (10 langs, open) > Sportmonks (paid).
- **G. World Cup / continental coverage:** none open with pub-time; StatsBomb open has structured WC/EURO/
  AFCON/Copa events (not prose); commentary text for these tournaments = paid/unavailable.
- **H. Major European league coverage:** SoccerReplay-1988 (NDA) / SoccerNet-Echoes (open) for research;
  Sportmonks (paid) for live.

## Recommendations
1. **Best zero-cost research-only:** SoccerNet-Echoes (CC BY 4.0) — historical/weak-supervision only.
2. **Best academic/weak-supervision:** SoccerReplay-1988 (richer, NDA) — needs your NDA acceptance.
3. **Best for historical player/sub/card expansion:** Sportmonks historical (paid) or StatsBomb commercial.
4. **Best realistic LIVE commentary:** Sportmonks Match Commentary API (paid) — only after the causal gate.
5. **Best for WC + continental tournaments:** no open prose source; StatsBomb open (structured) + a paid
   commentary feed if narrative text is required.
6. **Best route for a future commercial/production system:** Sportmonks or Opta/Stats Perform (licensed,
   timestamped) — never scraped news/match-center text.
7. **Reject despite attractive coverage:** news live blogs + official match-center scraping + YallaShoot/
   Arabic mirrors (copyright/ToS/unverified rights).
