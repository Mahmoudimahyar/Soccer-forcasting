# Commentary Source Landscape (Phase 1, 2026-06-23)

Evidence-based survey of minute-by-minute soccer commentary sources, from official docs / dataset cards
/ repos / papers only. Catalogue: `data/reference/commentary_source_catalog.{csv,json}`. Every match
count is marked verified or `[verify]`; nothing fabricated.

## Verified key sources
- **SoccerNet-Echoes** (G, broadcast transcript) — ASR transcriptions (Whisper) of broadcast audio,
  multilingual (10 langs), **CC BY 4.0** (open, attribution). Timestamps are **broadcast video time**,
  not publication time. arXiv:2405.07354; HF `SoccerNet/SN-echoes`. → **open download; weak-supervision/
  alignment only; NOT live** (no publication_time, ASR noise).
- **SoccerReplay-1988 / MatchTime / MatchVoice** (D, academic) — 1,988 matches, ~150K commentary lines,
  24 event classes, second-level alignment. **NDA + non-commercial.** arXiv:2412.01820; HF
  `Homie0609/SoccerReplay-1988`. → **needs your NDA acceptance**; then weak-supervision/alignment only;
  NOT live (no original publication_time).
- **API-Football** (A, structured) — structured events every ~15s, NOT narrative text. Already used by
  the live collector. → structured truth anchor, not a commentary-text source.
- **Sportmonks Match Commentary API** (C, licensed) — narrative commentary lines, multilingual,
  live + historical (add-on). **Commercial license (EUR29–249/mo + add-ons).** → **best realistic LIVE
  commentary route IF publication/update timestamps verify**; requires your paid-account decision.
- **StatsBomb Open Data** (E) — structured events + xG + 360; non-commercial research + attribution. →
  truth anchor for alignment (already used); not commentary text.

## Restricted / rejected
- **Official match centers** (B, FIFA/UEFA/CONMEBOL/AFC/CAF) — copyrighted live text, ToS restrict
  automated use, **no open commentary API** → do NOT scrape; license/approval required.
- **News live blogs** (F, BBC/Guardian/ESPN…) — copyrighted, often Opta-powered, ToS prohibit automated
  extraction → **REJECT** for automated retention/modeling.
- **YallaShoot / Arabic mirrors** (J) — no authoritative source, unclear/likely-infringing rights →
  **REJECT** (unverified).

## Coverage reality vs the target competitions
- World Cup / continental tournaments (Euro, Copa, AFCON, Asian Cup): **no open, rights-clear,
  publication-timestamped commentary text dataset** is confirmed. Academic sets (SoccerNet-Echoes,
  SoccerReplay-1988) skew to **European leagues + UCL**, not international tournaments.
- Major European leagues (EPL/La Liga/Bundesliga/Serie A/Ligue 1): covered by the academic sets
  (broadcast/aligned), but rights-gated (CC BY / NDA) and **historical-only** (no publication_time).
- Multilingual: SoccerNet-Echoes (10 langs, open) is the strongest open multilingual option.

## Headline finding
There is **no currently-approved, open, publication-timestamped commentary source usable for LIVE
prediction.** The open/academic options are **historical / weak-supervision / alignment** only. Live
commentary realistically requires a **commercial license** (Sportmonks) with verified publication
timestamps — a paid decision. This drives Phases 2 (rights), 5 (alignment, on permitted data), 6 (live
gate — nothing passes yet), and 7 (procurement).
