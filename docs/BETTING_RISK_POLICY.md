# Betting Risk Policy

This project is a prediction and testing lab. It is not a guarantee of profit.

## Prediction is not edge

A high draw probability is not automatically a bet. The bet exists only if the model probability exceeds the no-vig market probability by enough to overcome uncertainty.

\[
Edge_D = p_D^{model} - p_D^{market}
\]

Minimum condition:

\[
Edge_D > vig + calibration\ error + safety\ margin
\]

## Fair odds

\[
FairOdds_D = \frac{1}{p_D^{model}}
\]

A draw bet is not considered unless offered odds exceed fair odds after accounting for uncertainty.

## Expected value per unit

For decimal odds \(o\):

\[
EV = p_D(o-1) - (1-p_D)
\]

Positive EV does not mean low risk.

## Standard deviation per unit

\[
SD = \sqrt{p_D(o-1)^2 + (1-p_D) - EV^2}
\]

This is reported in `edges.csv` as:

```text
draw_bet_sd_per_unit
```

## Kelly sizing

The Kelly fraction for decimal odds is:

\[
f^* = \frac{(o-1)p - (1-p)}{o-1}
\]

The project clips negative values to zero. In practice, full Kelly is too aggressive for noisy sports models. Use fractional Kelly if you use it at all.

## Reject these practices

- betting from a chatbot table without real odds
- betting because a group is “due” for a draw
- betting because a group “already has too many draws”
- parlays unless each leg is independently positive EV at real odds
- ignoring lineups, injuries, red cards, and weather
- trusting a small 2026 sample without Bayesian shrinkage

## Required reporting before any bet

A candidate bet should include:

```text
model draw probability
market no-vig draw probability
edge
fair odds
offered odds
probability interval
outcome standard deviation
bet EV per unit
bet SD per unit
calibration error of the model bucket
stake size rule
```

If any of these are missing, the bet is not research-grade.
