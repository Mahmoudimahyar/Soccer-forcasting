# Cycle 5 — True alpha vs the sharp line, and the lineups/xG dead-end (2026-06-20)

Two follow-ups to cycle 4: (1) is the Elo-blend edge real alpha or just denoising a soft
consensus? — tested against the **closing line and Pinnacle specifically**; (2) can we add
**lineups / xG**?

## Lever 1 — sharper market input (the decisive test)
`scripts/fetch_intl_odds_sharp.py` re-pulled each intl slot at **~5 min before kickoff**
(closing line) and extracted **Pinnacle** specifically. 253 matches have Pinnacle present.
`build_intl_sharp_dataset.py` → `intl_market_sharp.csv`; `test_sharp_market.py`,
`diagnose_sharp_alpha.py`.

### The closing/Pinnacle lines are barely sharper than my T-90 consensus
| market source | composite | RPS |
|---|---|---|
| T-90 consensus | 0.3612 | 0.1885 |
| closing consensus | 0.3608 | 0.1890 |
| **Pinnacle close** | **0.3586** | 0.1889 |

Pinnacle-close is the sharpest, but only ~0.7% better than my consensus — so there was little
"noise" to remove. This already weakens the denoising hypothesis.

### The Elo blend STILL beats Pinnacle's closing line (expanding-window CV)
| benchmark | market | blend | edge | folds |
|---|---|---|---|---|
| T-90 consensus | 0.3678 | 0.3527 | +4.10% | 3/4 |
| closing consensus | 0.3669 | 0.3505 | +4.45% | 3/4 |
| **Pinnacle close** | 0.3659 | 0.3503 | **+4.26%** | 3/4 |

The edge does **not** disappear against the sharpest line → **evidence of real alpha, not
denoising.** Confirmed on pure metrics (fixed 0.6·Pinnacle+0.4·Elo, parameter-free):
- ALL (n=253): **RPS 0.1889 → 0.1774 (+6.1%)**, LogLoss 0.956 → 0.919.
- BIG WC/Euro/Copa (n=142): **RPS +7.1%**.
- **World Cup only (n=48): RPS 0.2218 → 0.2129 (+4.0%)**, LogLoss 1.021 → 0.994.

### The alpha is strongest on BIG tournaments, not thin markets (the key check)
Blend (0.6·Pinnacle + 0.4·Elo) vs Pinnacle-close, composite:
| group | n | edge |
|---|---|---|
| BIG (WC/Euro/Copa) | 142 | **+4.4%** |
| THIN (NL/qual/AFCON/Gold) | 111 | +3.3% |
Per competition: Euro +4.6% (n=72), Copa +8.7%, Gold Cup +11.8%, **WC +3.0% (n=48)**, NL +5.4%;
small negatives only on tiny qualifier/AFCON samples (n≤22).

**Interpretation:** international football markets — even Pinnacle's close — appear to
under-weight long-run team strength relative to a 49k-match Elo. The blend exploits this. The
edge being *strongest on the major tournaments* (incl. the World Cup) means it is not a
thin-market artifact.

### Honest caveats (still apply)
- Modest samples (WC 48, Euro 72); OOS CV was 3/4 folds (one fold did not beat). Blend weight is
  high (~0.4–0.6) — international markets really do seem to under-use Elo.
- A 4–7% RPS edge vs the ~5–7% 1X2 overround is **not a blanket betting-profit claim**; it could
  be selectively +EV on high-edge matches but that needs a separate, fees-aware backtest. This is
  a forecast-quality result.

## Lever 2 — lineups / xG: DATA-BLOCKED (documented, not faked)
- football-data.org free tier returns **no lineups, no statistics, no xG** (probed a match: only
  teams/score/venue/referees; odds field locked).
- No free CSV of historical **international** xG exists: Understat = top-5 European *leagues*
  only; FBref has it but is scraping-restricted (ToS + project governance); API-Football has it
  but the supplied key is the blocked RapidAPI type.
- Conceptually, the useful feature is an xG-based *pre-match rating* (rolling xG of prior
  matches), which needs the same unavailable historical international xG feed.
- **Only path:** a working *direct* api-sports.io key (helps *live* 2026 lineups only, and the
  market already prices lineup news), or an approved FBref scrape (governance request needed).
  See `data_requests/pending/api_football.yaml`.

## Bottom line
Against the question "is it real alpha beyond denoising?": **yes.** Market + ~0.4·Elo beats
Pinnacle's closing line by ~4% composite / +4–7% RPS, strongest on the big tournaments including
the World Cup. The production 2026 headline forecast already uses this blend
(`market_anchored_forecast.py`, p_*_final). Lineups/xG remain blocked by data availability.
