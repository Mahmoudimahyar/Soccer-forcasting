"""Deterministic per-feature AVAILABILITY gate.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

A model must never consume a feature that is unavailable for a row. This module is the single place
that decides, per (row, feature), whether a feature is usable -- and it NEVER silently zero-fills an
unavailable feature. The contract:

  * A feature is AVAILABLE for a row iff the underlying cell is present and parseable to a finite number.
  * Missingness is PRESERVED: an unavailable feature is reported as such (not coerced to 0). Downstream,
    DM.FeatureSpace imputes a TRAIN-mean and sets a companion ``<col>__unknown`` indicator, so the model
    sees an explicit "this was missing" signal rather than a spurious zero.
  * The xG-derived families are additionally gated on the row's ``xg_present`` flag: when a match/source
    does not carry xG, every xg_* / cum_xg_* feature is treated as unavailable for that row regardless of
    whether the cell happens to be blank or a stale 0 -- preventing a missing-xG source from being read
    as "no xG happened".

The gate is deterministic and stateless w.r.t. targets. Train and test rows are gated identically.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from . import features as F

AVAILABILITY_VERSION = "residual_intensity_availability_v1"

# Columns whose availability additionally requires xg_present == True for the row. A source without xG
# must not let these masquerade as observed zeros.
_XG_GATED_PREFIXES = ("cum_xg", "xg_last", "xg_current_half", "xg_momentum", "xg_acceleration")
_XG_GATED_EXACT = {"cum_xg_diff", "cum_xg_total", "min_since_major_chance"}


def _xg_present(row: dict) -> Optional[bool]:
    v = row.get("xg_present")
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def _is_xg_gated(col: str) -> bool:
    if col in _XG_GATED_EXACT:
        return True
    return any(col.startswith(p) for p in _XG_GATED_PREFIXES)


def is_available(row: dict, col: str) -> bool:
    """True iff ``col`` is usable for ``row``: cell present + finite, and (for xG-derived columns) the
    row actually carries xG. Never raises; never mutates the row."""
    if _is_xg_gated(col):
        xp = _xg_present(row)
        if xp is False:
            return False  # source carries no xG -> treat xG feature as unavailable, NOT as zero
        # xp True or unknown: fall through to cell-presence check
    return F.fnum(row, col) is not None


def available_columns(row: dict, candidate_cols: Sequence[str]) -> List[str]:
    """Subset of ``candidate_cols`` that are available for this row (order preserved)."""
    return [c for c in candidate_cols if is_available(row, c)]


def gate_columns(rows: Sequence[dict], candidate_cols: Sequence[str],
                 min_coverage: float = 0.0) -> List[str]:
    """Return the columns from ``candidate_cols`` whose availability fraction across ``rows`` is
    >= ``min_coverage``. A column never seen as available in ANY row is always excluded (a model can
    never use a feature that is unavailable everywhere). Deterministic; targets are never consulted.
    With min_coverage=0.0 this drops only all-unavailable columns -- the minimal honest gate."""
    if not rows:
        return []
    n = len(rows)
    out: List[str] = []
    for c in candidate_cols:
        hits = sum(1 for r in rows if is_available(r, c))
        frac = hits / n
        if hits > 0 and frac >= min_coverage:
            out.append(c)
    return out


def coverage_report(rows: Sequence[dict], candidate_cols: Sequence[str]) -> Dict[str, float]:
    """Per-column availability fraction across ``rows`` (deterministic; 0.0..1.0)."""
    n = max(1, len(rows))
    return {c: round(sum(1 for r in rows if is_available(r, c)) / n, 6) for c in candidate_cols}


def row_completeness(row: dict, candidate_cols: Sequence[str]) -> float:
    """Fraction of ``candidate_cols`` available for a single row in [0, 1]. Used by the selective gate /
    regimes to decide how much event-process correction a row's evidence can support."""
    if not candidate_cols:
        return 0.0
    avail = sum(1 for c in candidate_cols if is_available(row, c))
    return avail / len(candidate_cols)


def annotate_completeness(rows: Sequence[dict],
                          candidate_cols: Optional[Sequence[str]] = None) -> str:
    """Attach ``ri_completeness`` (event-process feature completeness in [0,1]) and ``ri_xg_available``
    (bool) to each row in-place. Returns the completeness column name. Used by the selective gate."""
    cols = list(candidate_cols) if candidate_cols is not None else list(F.ALL_FEATURE_COLS)
    for r in rows:
        r["ri_completeness"] = row_completeness(r, cols)
        xp = _xg_present(r)
        r["ri_xg_available"] = bool(xp) if xp is not None else False
    return "ri_completeness"
