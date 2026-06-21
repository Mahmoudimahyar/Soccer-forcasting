# Probability and Statistical Reasoning

## 1. The object being predicted

For each match, the model predicts a probability vector over three mutually exclusive outcomes:

\[
\mathbf p = (p_A, p_D, p_B)
\]

where:

- \(p_A\): team A wins in regulation/group-stage result time.
- \(p_D\): draw.
- \(p_B\): team B wins.

These probabilities must satisfy:

\[
p_A + p_D + p_B = 1, \quad p_j \ge 0
\]

The model is not primarily a classifier. It is a probabilistic forecaster. A prediction of `p_draw = 0.30` means that among many similar matches, roughly 30% should draw. It does not mean the model is “calling” a draw.

## 2. Why scoreline modeling is the correct backbone

Draws are diagonal score events:

\[
P(D) = P(0,0) + P(1,1) + P(2,2) + \cdots
\]

A direct win/draw/loss model can work, but it hides the mechanism. A score model estimates goal intensities:

\[
G_A \sim \text{Poisson}(\lambda_A), \quad G_B \sim \text{Poisson}(\lambda_B)
\]

For independent Poisson goals:

\[
P(G_A=i, G_B=j) = \frac{e^{-\lambda_A}\lambda_A^i}{i!}\frac{e^{-\lambda_B}\lambda_B^j}{j!}
\]

The match probabilities are then aggregated from the score matrix:

\[
P(A\ win)=\sum_{i>j}P(i,j)
\]

\[
P(D)=\sum_{i=j}P(i,j)
\]

\[
P(B\ win)=\sum_{i<j}P(i,j)
\]

This is why the project contains `src/wcdrawlab/models/scoreline.py`.

## 3. Why plain Poisson is not enough

Football scores are not perfectly independent Poisson counts. Low scorelines such as 0-0, 1-0, 0-1, and 1-1 often have dependence caused by tactics, tempo, game state, and risk management. The project therefore includes two simple correction mechanisms:

1. **Dixon-Coles-style low-score correction** through `rho`.
2. **Diagonal inflation** that increases mass on draw scorelines.

These are not assumed to be true. They are tested against simpler baselines.

## 4. Why rating gap matters

A strength rating difference, especially Elo-like difference, approximates the expected advantage of one team over the other. The larger the absolute gap:

\[
|\Delta R| = |R_A - R_B|
\]

the more asymmetric the score matrix should become. Draw probability usually peaks near parity and declines as the strength gap grows. This is why the feature table contains:

- `elo_delta`
- `abs_elo_delta`
- `fifa_z_delta`
- `abs_fifa_z_delta`
- optional market/squad strength deltas

The project deliberately does not rely on raw FIFA points across eras. FIFA points are standardized within each release:

\[
FIFA_Z = \frac{points - \mu_{release}}{\sigma_{release}}
\]

This prevents pre/post ranking-system changes from polluting the training set.

## 5. Why expected total goals matters

Two teams can be equal in strength but differ in draw risk depending on expected total goals:

\[
\lambda_T = \lambda_A + \lambda_B
\]

A close match with \(\lambda_T=1.7\) is much more draw-prone than a close match with \(\lambda_T=3.4\). Therefore the draw model must consider both:

\[
|\Delta R| \quad \text{and} \quad \lambda_T
\]

The market total, if available, is used as a practical proxy for expected total goals.

## 6. Tournament-state probability is not a narrative label

Terms like “must win,” “dead rubber,” and “mutual draw” are too crude. The model computes utilities from simulated advancement probabilities:

\[
P_i(advance | win), \quad P_i(advance | draw), \quad P_i(advance | loss)
\]

For each team:

\[
DrawUtility_i = P_i(advance | draw) - P_i(advance | loss)
\]

\[
MustWinPressure_i = P_i(advance | win) - P_i(advance | draw)
\]

The match-level mutual draw utility is:

\[
MutualDrawUtility = \min(DrawUtility_A, DrawUtility_B)
\]

This is the probability-theoretic replacement for hand labels. If a draw materially improves both teams’ advancement chances relative to losing, draw probability may rise. If one or both teams gain much more from winning than drawing, draw probability may fall.

## 7. Why group draw count is not a cap

A group having two previous draws does not mathematically prevent another draw. The model treats `prior_group_draws` as a feature, not as a rule.

Bad rule:

```text
if prior_group_draws >= 2: suppress draw
```

Correct approach:

\[
P(D) = f(|\Delta R|, \lambda_T, \text{table state}, \text{prior group goals}, \text{prior group draws})
\]

If prior draws reveal a genuinely low-event group, they can even increase future draw risk. Only backtesting decides the sign and size.

## 8. Market probabilities as a benchmark, not an oracle

Decimal odds imply raw probabilities:

\[
q_j = \frac{1}{odds_j}
\]

Because bookmakers include margin, the no-vig market probabilities are:

\[
p^{market}_j = \frac{q_j}{q_A + q_D + q_B}
\]

The model compares itself to this market baseline. For betting, the relevant quantity is not the model probability alone:

\[
Edge_D = p^{model}_D - p^{market}_D
\]

A positive edge is not enough. It must exceed calibration error, vig, and a safety margin.

## 9. Proper scoring rules

The project evaluates probability quality using:

### Log loss

\[
-\log(p_{actual})
\]

This heavily penalizes overconfident wrong predictions.

### Ranked Probability Score

For ordered outcomes \([A, D, B]\), RPS compares cumulative predicted and observed distributions:

\[
RPS = \frac{1}{2}\sum_{k=1}^3 \left( \sum_{j=1}^k p_j - \sum_{j=1}^k y_j \right)^2
\]

### Draw Brier score

\[
(y_D - p_D)^2
\]

### Draw calibration error

Predictions are binned by draw probability. The model compares average predicted draw probability with actual draw frequency inside each bin.

The project intentionally does not optimize raw accuracy, because a model can avoid predicting draws and still appear accurate.
