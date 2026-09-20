# Figures

Two static SVG figures used by the top-level [README](../../README.md). Both are drawn by one
dependency-free script from files that are already committed. The script does not fit, tune, select or
re-score anything; it only re-draws numbers that are already in the repository.

| Figure | What it shows | Source of every plotted number |
|---|---|---|
| [`prospective_paired_deltas.svg`](prospective_paired_deltas.svg) | Forest plot of the paired RPS differences in the prospective 2026 benchmark | [`notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md`](../../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md) |
| [`power_curve.svg`](power_curve.svg) | Match-clustered power to detect an RPS gain, against the number of matches | [`data/reference/international_event_lake_power_analysis.json`](../../data/reference/international_event_lake_power_analysis.json) |

## Regenerate

```bash
python scripts/make_readme_figures.py           # rewrites both SVGs in docs/img/
python scripts/make_readme_figures.py --check   # writes nothing; exit 1 if the SVGs are out of date
```

Standard library only (Python 3.10+), no network, no API quota, no gitignored data. The output is
deterministic: no timestamps, fixed number formatting, `\n` line endings, pure-ASCII SVG. Running it twice
gives byte-identical files. The script prints every number it plots.

It fails closed. Exit code `2` means a source could not be parsed, or a sentence printed on a figure is
no longer true for the parsed numbers (for example, if an interval stopped crossing zero). Exit code `3`
means the computed layout would push something outside the viewBox or make two labels overlap.

Script: [`scripts/make_readme_figures.py`](../../scripts/make_readme_figures.py).

---

## Figure 1 - prospective paired RPS differences

![Forest plot of paired RPS differences; every 95% interval crosses zero](prospective_paired_deltas.svg)

**What it is.** The eight `rps` rows of the "Paired fixture-level deltas" table in the scorecard: each
model against the B1 Elo reference, and each model against the market reference. The point is the mean
per-fixture RPS difference (RPS = ranked probability score, lower is better); the bar is the 95%
match-level percentile bootstrap interval (5,000 resamples, fixture = unit of analysis). Negative means
the row model scored better than the reference.

Model names: `M1_B1` is B1, the ternary-Elo model with no fitted parameters. `M2_market` is the no-vig
bookmaker consensus, a read-only comparator. M3-M5 are fixed, untuned blends of the two. These are the
*pre-match* shadow models; the in-play research lines reuse the labels M0-M6 for different models (see
[`docs/GLOSSARY.md`](../GLOSSARY.md)).

**How to read it.** Every interval crosses zero. At 34 fixtures there is no evidence that any model
differs from B1 Elo or from the market. That is a null result at this sample size, not a claim of "no
effect". The scorecard table also has log-loss and draw-Brier rows; none of the 24 reported paired
differences has an interval that excludes zero. Only the RPS rows are drawn.

Each fixture is scored on one snapshot, chosen by a rule that depends only on timestamps and model
coverage, never on results. The rule was pre-specified in the repository
([`prospective_score_harvest_preregistration.md`](../../notes/research/prospective_score_harvest_preregistration.md)).
That ordering is self-attested: the rule, the scoring script and the results share one commit.

**Caveats printed on the figure.**

- The sample is exploratory: 34 fixtures is the lab's own tier C (20-49 fixtures; 50 or more is the lab's
  bar for a confirmatory claim). See [`docs/GLOSSARY.md`](../GLOSSARY.md).
- The market comparator is an **early line, not a closing line**. The script re-derives the lead time
  from [`data/reference/prospective_frozen_input_manifest.csv`](../../data/reference/prospective_frozen_input_manifest.csv)
  using the benchmark's own outcome-independent rule (per fixture, the latest pre-kickoff snapshot that
  carries all five models): median 97.6 h before kickoff across the 34 scored fixtures, 30 of them more
  than 24 h. B1's forecast was frozen at the same early time, so the two sides had the same lead; what
  the figure cannot tell you is how B1 compares with a closing line. The cause is
  [erratum E2](../ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger).
- The eight rows are not eight independent tests. They all use the same 34 fixtures, M3-M5 are fixed
  mixtures of the same two forecasts, and the "market vs B1" and "B1 vs market" rows are one comparison
  seen from both sides. Those two intervals differ slightly because each row was bootstrapped with its
  own random draws in the source table.
- These are forecast-quality metrics from a paper-only research project. Nothing here is betting or
  financial advice.

**Plotted values** (copied by the script from the source table):

| Reference | Row model | Mean RPS difference | 95% interval |
|---|---|---:|---|
| B1 Elo (`M1_B1`) | Market (`M2_market`) | +0.0057 | [-0.0118, +0.0226] |
| B1 Elo | M3, 75% Elo / 25% market | +0.0001 | [-0.0044, +0.0042] |
| B1 Elo | M4, 50% / 50% | +0.0011 | [-0.0080, +0.0094] |
| B1 Elo | M5, 25% Elo / 75% market | +0.0029 | [-0.0100, +0.0159] |
| Market (`M2_market`) | B1 Elo (`M1_B1`) | -0.0057 | [-0.0222, +0.0120] |
| Market | M3, 75% Elo / 25% market | -0.0056 | [-0.0189, +0.0073] |
| Market | M4, 50% / 50% | -0.0046 | [-0.0132, +0.0041] |
| Market | M5, 25% Elo / 75% market | -0.0028 | [-0.0073, +0.0016] |

---

## Figure 2 - how many matches would it take?

![Power against number of matches on a log axis, one line per RPS gain](power_curve.svg)

**What it is.** A power analysis for the in-play research lines, built by
[`scripts/run_international_event_lake_power_analysis.py`](../../scripts/run_international_event_lake_power_analysis.py)
(human-readable copy:
[`international_event_lake_power_analysis.md`](../../data/reference/international_event_lake_power_analysis.md)).
The noise template is the set of per-match paired RPS differences actually observed on the 231 eligible
internationals (5 tournaments; event-process model e7 minus the e2 remaining-time Poisson reference),
centred to zero, SD 0.059. Each simulated dataset is resampled **by match**, because every in-play
snapshot of a match moves together. "Detect" means the match-level bootstrap 95% interval lies wholly
below zero.

Two notes on the template. First, e2 is the unfitted remaining-time Poisson reference that other research
lines call in-play M2, R0 or T0 (see "One reference model, seven labels" in
[`docs/GLOSSARY.md`](../GLOSSARY.md)). Second, only the *spread* of the template is used. Centring removes
its mean, so the figure says nothing about whether e7 is better than e2; the decision ledger records e7
as `reference_only`.

**How to read it.** With the 231 matches available, the simulated power to detect a 0.005 absolute RPS
gain is 0.28. For that gain, 0.80 power is first reached at the 1,200-match grid size. Gains of 0.002 or
smaller never reached 0.60 power at any grid size up to 2,000 matches. So a null result at these sample
sizes cannot rule out a small real gain. That is why in-play rows in this repository are worded "no
evidence of improvement at this sample size" rather than "no effect".

The template comes from one in-play comparison on one cohort. No separate power analysis was run for the
34-fixture pre-match benchmark in Figure 1, so do not read these match counts across to it.

**What the marks mean - please read this before quoting the figure.** The committed JSON does *not*
store power at every grid size. It stores two kinds of number, and the figure shows only those:

- **Filled circle** - a simulated power estimate at that match count: 231 (all eligible matches) and 139
  (the JSON's 60%-coverage scenario).
- **Open triangle** - the *first grid size* at which the simulated estimate reached 0.60, 0.80 or 0.90.
  The triangle is drawn at the threshold. The estimate at that size was at or above it (the exact value
  is not stored), and at every smaller grid size the estimate was below it. Grid sizes: 20, 30, 40, 50,
  58, 75, 100, 150, 200, 300, 500, 800, 1,200, 2,000.

The dashed lines only join those committed values as a visual guide. They are not simulated or fitted
curves, and no simulation was run to make the figure. The 0.010 line stops at 500 matches because that is
the last number the JSON records for it (0.80 and 0.90 were both first reached at 500, so one triangle
is drawn, at 0.90).

Every plotted value is a single Monte-Carlo estimate (400 simulated datasets x 400 bootstrap resamples),
not an exact power: five repeat estimates at 231 matches ranged 0.215-0.300 for the 0.005 gain. That
noise is the likely reason the 0.003 line dips very slightly between 139 and 231 matches (0.1350 to
0.1325). For the same reason, read the grid sizes as rough orders of magnitude ("about a thousand
matches, not a few hundred"), not as precise requirements.

An earlier 58-match analysis
([`match_level_power_analysis.json`](../../data/reference/match_level_power_analysis.json)) used a
different, more optimistic noise template (paired-difference SD 0.020 instead of 0.059). Its match-count
projection is superseded and is not plotted.

**Plotted values** (copied by the script from the JSON):

| Absolute RPS gain | Power at 139 matches | Power at 231 matches | First grid size reaching 0.60 | 0.80 | 0.90 |
|---:|---:|---:|---:|---:|---:|
| 0.010 | 0.4925 | 0.7050 | 200 | 500 | 500 |
| 0.005 | 0.1975 | 0.2800 | 800 | 1,200 | 2,000 |
| 0.003 | 0.1350 | 0.1325 | 2,000 | not reached | not reached |
| 0.002 | 0.0675 | 0.1000 | not reached | not reached | not reached |
| 0.001 | 0.0500 | 0.0525 | not reached | not reached | not reached |
| 0.0005 | 0.0400 | 0.0400 | not reached | not reached | not reached |

"Not reached" means not reached at any grid size up to 2,000 matches.

---

## Design notes

- Static SVG only: no scripts, no external resources, no embedded raster images. A white background
  rectangle keeps the figures legible in GitHub dark mode.
- System sans-serif font stack; dark grey text (`#24292f`); muted palette; 1.5 px strokes; light
  gridlines (`#d0d7de`).
- Colour is never the only cue. Series are also identified by a legend and by direct labels, and the
  colour order keeps red, green and brown (hard to tell apart with some colour-vision deficiencies) from
  being neighbours.
- The standard library has no font metrics, so label widths are estimated with roughly 10% slack and the
  script refuses to write a figure if two estimated label boxes touch. If you change any label text,
  regenerate and look at the result in a browser.
