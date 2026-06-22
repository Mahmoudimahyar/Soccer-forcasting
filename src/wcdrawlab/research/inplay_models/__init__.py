"""Research-only in-play baseline models (M0-M5). NONE are runtime-approved.

All carry research_only=True / experimental / not_runtime_approved and must never influence approved
forecasts, advancement, paper decisions, risk, or Kalshi. 2022-only foundation; no neural nets.
"""
from wcdrawlab.research.inplay_models.models import (  # noqa: F401
    M0_StaticB1, M1_TimeScore, M2_RemainingPoisson, M3_GoalHazard, M4_CompetingRisk, M5_Ensemble,
    M6_MarketInplay, M2cal_CalibratedPoisson,
    WLD_MODELS, full_output_envelope, pregame_lambdas, remaining_lambdas,
)
