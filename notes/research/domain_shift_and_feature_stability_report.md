# Domain Shift & Feature Stability Report (Phase 2)

_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_

Generated: 2026-06-28T08:18:29Z

## Verdict

- International feature profiling: **complete** (258 real matches, 5 competitions).
- Club feature profiling: **data_insufficient** (events materialized = 0 / 669 declared).
- Cross-domain overlap audit: **data_insufficient**.
  - reason: club event corpus not materialized in this worktree (Phase-1: events_materialized=0); cross-domain SMD / variance-ratio / distribution-overlap / Wasserstein / out-of-support / transfer-risk all require a REAL club feature distribution and are NOT fabricated

The cross-domain statistics (missingness diff, standardized mean difference, variance ratio, distribution overlap, Wasserstein distance, out-of-support rate, transfer-risk) each require a REAL feature distribution from BOTH domains. The club distribution is not derivable here, so these are reported as `data_insufficient` and NEVER fabricated. The international in-domain distribution profile, missingness, competition heterogeneity, and temporal stability ARE computed on real data and recorded below.

## Stable-transferable feature count

- features audited: **22**
- positively certified `stable_transferable`: **0** (cannot exceed 0 until the club distribution is materialized -- a positive certification requires a real cross-domain comparison)
- held at `insufficient_data` (cross-domain): **22**
- families flagged `domain_shifted`: none derivable yet

## International in-domain feature profile (REAL)

Per feature: pooled across decision minutes [30, 45, 60, 75]. `het_max_smd` is the largest standardized gap between any single international competition's mean and the pooled mean (an in-domain shift proxy); `temporal_spread` is the season-mean spread in pooled-std units.

| family | feature | n_obs | missing | mean | std | het_max_smd | temporal_spread | classification |
|---|---|---:|---:|---:|---:|---:|---:|---|
| score_time | goals_diff | 1032 | 0.0 | 0.107558 | 1.164068 | 0.2272 | 0.3764 | insufficient_data |
| score_time | score_diff_sign | 1032 | 0.0 | 0.03876 | 0.738605 | 0.2497 | 0.3178 | insufficient_data |
| score_time | remaining_regulation_min | 1032 | 0.0 | 37.5 | 16.778641 | 0.0 | 0.0 | insufficient_data |
| score_time | players_diff | 1032 | 0.0 | -0.001938 | 0.17057 | 0.0637 | 0.0287 | insufficient_data |
| score_time | min_since_last_shot_any | 1032 | 0.0 | 3.945907 | 4.116232 | 0.0781 | 0.1327 | insufficient_data |
| chance_quality | cum_xg_total | 1032 | 0.0 | 1.208924 | 0.768455 | 0.1501 | 0.2484 | insufficient_data |
| chance_quality | cum_xg_diff | 1032 | 0.0 | 0.057497 | 0.758479 | 0.0553 | 0.0744 | insufficient_data |
| chance_quality | shots_diff | 1032 | 0.0 | 0.386628 | 5.554835 | 0.061 | 0.0864 | insufficient_data |
| chance_quality | shots_on_target_diff | 1032 | 0.0 | 0.252907 | 2.358506 | 0.1197 | 0.1829 | insufficient_data |
| chance_quality | xg_last10m_diff | 1032 | 0.0 | 0.008197 | 0.31358 | 0.056 | 0.0928 | insufficient_data |
| chance_quality | min_since_major_chance | 860 | 0.1667 | 16.489497 | 13.610967 | 0.1942 | 0.2656 | insufficient_data |
| possession_territory | poss_share_home | 1032 | 0.0 | 0.509118 | 0.154718 | 0.1847 | 0.298 | insufficient_data |
| possession_territory | poss_share_diff | 1032 | 0.0 | 0.018237 | 0.309436 | 0.1847 | 0.298 | insufficient_data |
| possession_territory | final_third_actions_diff | 1032 | 0.0 | 16.13469 | 206.781222 | 0.2105 | 0.29 | insufficient_data |
| possession_territory | box_entries_diff | 1032 | 0.0 | 2.247093 | 20.067152 | 0.2093 | 0.2742 | insufficient_data |
| possession_territory | field_tilt_home | 1032 | 0.0 | 0.512618 | 0.187241 | 0.1841 | 0.3227 | insufficient_data |
| transition_disruption | recoveries_diff | 1032 | 0.0 | -0.563953 | 8.02178 | 0.0935 | 0.1566 | insufficient_data |
| transition_disruption | turnovers_diff | 1032 | 0.0 | -0.002907 | 5.251113 | 0.4279 | 0.1933 | insufficient_data |
| set_pieces | corners_diff | 1032 | 0.0 | 0.200581 | 2.939328 | 0.1535 | 0.2171 | insufficient_data |
| set_pieces | att_free_kicks_diff | 1032 | 0.0 | -0.075581 | 3.480597 | 0.1769 | 0.1664 | insufficient_data |
| data_quality | xg_present | 1032 | 0.0 | 1.0 | 0.0 | None | None | insufficient_data |
| data_quality | n_events_observed | 1032 | 0.0 | 2019.000969 | 676.138058 | 0.2924 | 0.1457 | insufficient_data |

## Feature families

- **score_time** (5 features): scoreline/time-state is provider-neutral and competition-neutral; expected stable
- **chance_quality** (6 features): xG magnitude/tempo can differ club-vs-international (pace, finishing); shift risk
- **possession_territory** (5 features): possession style is league-dependent; club->international shift plausible
- **transition_disruption** (2 features): transition rates vary by league intensity; moderate shift risk
- **set_pieces** (2 features): set-piece counts are structurally comparable; low-moderate shift risk
- **data_quality** (2 features): data-density/coverage is a provider/competition property, not a football signal

## What unblocks the cross-domain decision

Materialize the 669 club event objects under the statsbomb_raw aux root (`data/raw/statsbomb_open/event_process_auxiliary/`). The same engine path then computes the club feature distribution, and this audit will emit real SMD / variance-ratio / overlap / Wasserstein / out-of-support / transfer-risk and resolve each feature's classification (`stable_transferable` / `domain_shifted` / `source_incompatible` / ...). Until then the honest verdict is `data_insufficient` for every cross-domain statistic.
