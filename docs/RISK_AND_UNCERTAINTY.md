# Risk and Uncertainty

Every prediction now carries risk/uncertainty columns. This is critical because a draw prediction is not complete unless it says how uncertain it is.

The implementation lives in:

```text
src/wcdrawlab/risk.py
```

## 1. Two kinds of uncertainty

The project separates two different concepts:

### A. Outcome randomness / irreducible risk

Even if the true draw probability is known perfectly, the match is still random. If:

\[
Y_D = 1 \quad \text{if draw, else } 0
\]

then:

\[
Var(Y_D) = p_D(1-p_D)
\]

\[
SD(Y_D) = \sqrt{p_D(1-p_D)}
\]

This is output as:

```text
outcome_var_draw
outcome_sd_draw
```

Example: if `p_draw = 0.30`, then:

\[
SD(Y_D)=\sqrt{0.30\times0.70}=0.458
\]

That is high because one match is a noisy Bernoulli event.

### B. Probability-estimate uncertainty / model risk

The model’s probability estimate itself is uncertain. The current implementation uses a pragmatic effective-sample-size approximation:

\[
SE(\hat p) \approx \sqrt{\frac{\hat p(1-\hat p)}{n_{eff}}}
\]

This is output as:

```text
prob_se_draw
```

The default effective sample size is conservative. In the backtest pipeline, it is based on the training window but capped, because 1,000 old matches do not equal 1,000 clean modern World Cup calibration examples.

## 2. Beta probability interval

The project also produces approximate probability intervals using a Beta approximation:

\[
\alpha = 1 + \hat p n_{eff}
\]

\[
\beta = 1 + (1-\hat p)n_{eff}
\]

Then it reports the interval quantiles:

\[
CI_{low} = Beta^{-1}(0.025; \alpha, \beta)
\]

\[
CI_{high} = Beta^{-1}(0.975; \alpha, \beta)
\]

Columns:

```text
prob_ci_low_draw
prob_ci_high_draw
```

Interpretation: this is not a perfect Bayesian posterior. It is a calibrated reporting device that prevents fake precision.

## 3. Three-way categorical covariance

For one-hot outcome vector \(Y=(Y_A,Y_D,Y_B)\):

\[
Cov(Y_i,Y_j)= -p_i p_j, \quad i\ne j
\]

\[
Var(Y_i)=p_i(1-p_i)
\]

The code exposes this through `categorical_covariance()` for deeper analysis.

## 4. Entropy and confidence

A match with probabilities `[0.34, 0.33, 0.33]` is much more uncertain than `[0.75, 0.15, 0.10]`.

The model reports normalized entropy:

\[
H(p)= -\frac{\sum_j p_j\log(p_j)}{\log(3)}
\]

`prediction_entropy` is in `[0, 1]`:

- near 0: sharp prediction
- near 1: highly uncertain prediction

The confidence score is:

\[
confidence = 1 - H(p)
\]

Columns:

```text
prediction_entropy
confidence_score
risk_band
```

## 5. Betting risk standard deviation

For a draw bet at decimal odds \(o\), staking 1 unit:

\[
X = \begin{cases}
o-1, & \text{if draw} \\
-1, & \text{otherwise}
\end{cases}
\]

Expected value:

\[
E[X]=p_D(o-1)-(1-p_D)
\]

Second moment:

\[
E[X^2]=p_D(o-1)^2+(1-p_D)(1)^2
\]

Variance:

\[
Var(X)=E[X^2]-E[X]^2
\]

Standard deviation:

\[
SD(X)=\sqrt{Var(X)}
\]

Columns:

```text
draw_bet_ev_per_unit
draw_bet_var_per_unit
draw_bet_sd_per_unit
draw_bet_sharpe_like
```

This matters because a positive expected value can still be extremely volatile.

## 6. Risk interpretation rules

A prediction should be treated as fragile when:

- `prediction_entropy` is high,
- `prob_se_draw` is high,
- draw probability interval crosses the market probability,
- model edge is smaller than calibration error,
- odds moved against the model,
- lineup or injury inputs are missing.

A bet should not be considered unless:

\[
p^{model}_D - p^{market}_D > vig + calibration\ error + safety\ margin
\]

The code deliberately reports uncertainty so the user does not confuse a thin model edge with a robust edge.
