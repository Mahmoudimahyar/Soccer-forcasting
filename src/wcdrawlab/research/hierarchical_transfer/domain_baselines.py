"""T0 / T1 / T2 — the reference and the two single-pool baselines of the ladder.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

  * ``T0Reference``          — the parameter-free remaining-time Poisson reference. NO fit. It reads the
    pre-computed ``t0_prob_*`` columns the Phase-3 dataset already carries (which were produced by
    ``research.transfer.w2_reference_t0`` == the locked W2 reference). The single anchor every candidate
    is judged against.

  * ``T1InternationalOnly``  — fits the ridge residual regressor on INTERNATIONAL TRAIN rows ONLY (club
    rows are dropped), over the stable-feature subset, predicting the home/away remaining-goal residual,
    then converts (domain_baseline + residual) -> H/D/A. This is the "no transfer" model: the honest
    international-only ceiling the transfer ladder must beat to justify importing club data at all.

  * ``T2NaiveClubPool``      — DIAGNOSTIC ONLY. Pools international + club TRAIN rows with NO domain
    correction (one shared baseline mean, one shared coefficient vector). Exposes the cost of ignoring
    domain shift. ``is_diagnostic_only = True`` and the registry/eval refuse to ever promote it. When no
    club rows are present in a fold it degenerates to T1 and records ``degenerate_to_T1 = True`` (honest:
    with no club data there is nothing to "naively pool").

All three return a ``predict_wdl(row) -> {H,D,A}`` callable and expose ``predict_intensity(row) ->
{home, away}`` so the W/D/L view and the intensity view stay consistent. Fitting touches TRAIN rows only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from . import DOMAIN_CLUB, DOMAIN_INTERNATIONAL, T0_REFERENCE, T1_INTERNATIONAL_ONLY, T2_NAIVE_CLUB_POOL
from .models import (
    RidgePoissonResidual,
    cell_float,
    current_score_diff,
    remaining_goal_exact_wdl,
    stable_feature_columns,
)


def _domain(r: dict) -> str:
    return (r.get("domain") or DOMAIN_INTERNATIONAL)


def _intl(rows: Sequence[dict]) -> List[dict]:
    return [r for r in rows if _domain(r) == DOMAIN_INTERNATIONAL]


def _club(rows: Sequence[dict]) -> List[dict]:
    return [r for r in rows if _domain(r) == DOMAIN_CLUB]


# =================================================================================================
# T0 — parameter-free reference (no fit). Reads the dataset's pre-computed t0_prob_* columns.
# =================================================================================================
@dataclass
class T0Reference:
    model_id: str = T0_REFERENCE
    short_id: str = "T0"
    is_reference: bool = True

    def fit(self, train_rows: Sequence[dict]) -> "T0Reference":
        return self  # nothing to fit; the reference is closed-form

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        pH = cell_float(row, "t0_prob_H")
        pD = cell_float(row, "t0_prob_D")
        pA = cell_float(row, "t0_prob_A")
        if pH is None or pD is None or pA is None:
            # fall back to the closed form from the symmetric base intensity + current score
            lam_h = cell_float(row, "t0_lam_home") or 0.0
            lam_a = cell_float(row, "t0_lam_away") or 0.0
            return remaining_goal_exact_wdl(lam_h, lam_a, current_score_diff(row))
        s = pH + pD + pA
        if s <= 0:
            return {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
        return {"H": pH / s, "D": pD / s, "A": pA / s}

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        return {"home": cell_float(row, "t0_lam_home") or 0.0,
                "away": cell_float(row, "t0_lam_away") or 0.0}


# =================================================================================================
# T1 — international-only residual model (no transfer). The honest intl ceiling.
# =================================================================================================
@dataclass
class T1InternationalOnly:
    model_id: str = T1_INTERNATIONAL_ONLY
    short_id: str = "T1"
    ridge: float = 1.0
    cols: List[str] = field(default_factory=list)
    home_model: Optional[RidgePoissonResidual] = None
    away_model: Optional[RidgePoissonResidual] = None
    n_train_intl: int = 0
    fitted: bool = False

    def fit(self, train_rows: Sequence[dict]) -> "T1InternationalOnly":
        intl = _intl(train_rows)
        self.cols = stable_feature_columns(intl) or stable_feature_columns(train_rows)
        self.home_model = RidgePoissonResidual(side="home", ridge=self.ridge).fit(intl, self.cols)
        self.away_model = RidgePoissonResidual(side="away", ridge=self.ridge).fit(intl, self.cols)
        self.n_train_intl = len(intl)
        self.fitted = True
        return self

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return {"home": cell_float(row, "domain_baseline_home") or 0.0,
                    "away": cell_float(row, "domain_baseline_away") or 0.0}
        return {"home": self.home_model.intensity(row), "away": self.away_model.intensity(row)}

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        it = self.predict_intensity(row)
        return remaining_goal_exact_wdl(it["home"], it["away"], current_score_diff(row))


# =================================================================================================
# T2 — naive pooled intl+club, NO domain correction. DIAGNOSTIC ONLY (never promoted).
# =================================================================================================
@dataclass
class T2NaiveClubPool:
    model_id: str = T2_NAIVE_CLUB_POOL
    short_id: str = "T2"
    is_diagnostic_only: bool = True
    ridge: float = 1.0
    cols: List[str] = field(default_factory=list)
    home_model: Optional[RidgePoissonResidual] = None
    away_model: Optional[RidgePoissonResidual] = None
    n_train_total: int = 0
    n_train_club: int = 0
    degenerate_to_T1: bool = False
    fitted: bool = False

    def fit(self, train_rows: Sequence[dict]) -> "T2NaiveClubPool":
        pooled = list(train_rows)                       # NO domain correction: pool everything as-is
        club = _club(pooled)
        self.degenerate_to_T1 = (len(club) == 0)
        self.cols = stable_feature_columns(pooled)
        self.home_model = RidgePoissonResidual(side="home", ridge=self.ridge).fit(pooled, self.cols)
        self.away_model = RidgePoissonResidual(side="away", ridge=self.ridge).fit(pooled, self.cols)
        self.n_train_total = len(pooled)
        self.n_train_club = len(club)
        self.fitted = True
        return self

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return {"home": cell_float(row, "domain_baseline_home") or 0.0,
                    "away": cell_float(row, "domain_baseline_away") or 0.0}
        return {"home": self.home_model.intensity(row), "away": self.away_model.intensity(row)}

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        it = self.predict_intensity(row)
        return remaining_goal_exact_wdl(it["home"], it["away"], current_score_diff(row))


def make_wdl_predictor(model) -> Callable[[dict], Dict[str, float]]:
    """Adapter so a fitted model can be passed to the eval layer as a bare ``predict(row)->{H,D,A}``."""
    return model.predict_wdl


__all__ = [
    "T0Reference", "T1InternationalOnly", "T2NaiveClubPool", "make_wdl_predictor",
]
