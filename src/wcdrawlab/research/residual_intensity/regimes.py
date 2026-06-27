"""Interpretable REGIME classifier over causal availability/state fields.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

A regime is a coarse, interpretable bucket of the match SITUATION at the decision minute -- derived
ONLY from causal state (score difference, remaining time, player-count difference) and source
availability (event-process completeness, xG presence). It is deliberately NOT an outcome model: it
never reads a target, is fully rule-based and deterministic, and exists so that the intensity /
selective families can condition on a small number of human-readable situations rather than on a
high-dimensional, partly-unavailable feature vector.

Why rule-based and not learned: an outcome-trained "regime" would smuggle label information into a
gating decision. By keeping regimes a transparent function of (score, time, players, completeness) we
guarantee the gate's confidence cannot rise on label leakage -- only on observable, causal state.

Two orthogonal axes:
  * game_state   : score/time/manpower situation (close_early, close_late, lead_*, blowout, ...)
  * evidence_tier: how much event-process evidence backs this row (rich / partial / sparse), driven by
                   the availability gate -- the same signal the selective gate uses to cap correction.

The combined regime label is "<game_state>|<evidence_tier>".
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from . import availability as AV
from . import features as F

REGIMES_VERSION = "residual_intensity_regimes_v1"

# evidence-tier thresholds on event-process feature completeness (causal availability only)
EVIDENCE_RICH = 0.75
EVIDENCE_PARTIAL = 0.40
# "late" boundary in remaining regulation minutes
LATE_REMAINING_MIN = 25.0
EARLY_REMAINING_MIN = 65.0

GAME_STATES = (
    "level_early", "level_mid", "level_late",
    "narrow_lead_early", "narrow_lead_late",
    "two_plus_lead", "blowout",
    "down_a_man", "up_a_man",
)
EVIDENCE_TIERS = ("rich", "partial", "sparse")


def evidence_tier(row: dict, candidate_cols: Optional[Sequence[str]] = None) -> str:
    """Coarse event-process evidence tier from causal availability ONLY (no targets)."""
    comp = row.get("ri_completeness")
    if comp is None:
        cols = list(candidate_cols) if candidate_cols is not None else list(F.ALL_FEATURE_COLS)
        comp = AV.row_completeness(row, cols)
    comp = float(comp)
    if comp >= EVIDENCE_RICH:
        return "rich"
    if comp >= EVIDENCE_PARTIAL:
        return "partial"
    return "sparse"


def game_state(row: dict) -> str:
    """Interpretable game-state bucket from score diff, remaining time, and player-count difference."""
    diff = F._current_diff(row)
    rem = F.fnum(row, "remaining_regulation_min")
    if rem is None:
        mn = F.fnum(row, "snapshot_minute")
        rem = (90.0 - mn) if mn is not None else 45.0
    players_diff = F.fnum(row, "players_diff")

    # manpower regimes take precedence (a sending-off changes the intensity structure most)
    if players_diff is not None:
        if players_diff <= -1:
            return "down_a_man"
        if players_diff >= 1:
            return "up_a_man"

    ad = abs(diff)
    if ad >= 3:
        return "blowout"
    if ad == 2:
        return "two_plus_lead"
    if ad == 1:
        return "narrow_lead_late" if rem <= LATE_REMAINING_MIN else "narrow_lead_early"
    # level
    if rem >= EARLY_REMAINING_MIN:
        return "level_early"
    if rem <= LATE_REMAINING_MIN:
        return "level_late"
    return "level_mid"


def classify(row: dict, candidate_cols: Optional[Sequence[str]] = None) -> str:
    """Combined interpretable regime label '<game_state>|<evidence_tier>'."""
    return f"{game_state(row)}|{evidence_tier(row, candidate_cols)}"


def annotate(rows: Sequence[dict], candidate_cols: Optional[Sequence[str]] = None) -> str:
    """Attach ``ri_regime``, ``ri_game_state``, ``ri_evidence_tier`` in-place. Returns the regime col."""
    cols = list(candidate_cols) if candidate_cols is not None else list(F.ALL_FEATURE_COLS)
    for r in rows:
        gs = game_state(r)
        et = evidence_tier(r, cols)
        r["ri_game_state"] = gs
        r["ri_evidence_tier"] = et
        r["ri_regime"] = f"{gs}|{et}"
    return "ri_regime"


def regime_coverage(rows: Sequence[dict],
                    candidate_cols: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, int]]:
    """Counts of rows / matches per regime (and per game_state, per evidence_tier). Interpretable
    coverage table for the regime data card. Deterministic; no targets consulted."""
    cols = list(candidate_cols) if candidate_cols is not None else list(F.ALL_FEATURE_COLS)
    by_regime: Dict[str, set] = {}
    n_regime: Dict[str, int] = {}
    n_state: Dict[str, int] = {}
    n_tier: Dict[str, int] = {}
    for r in rows:
        gs = game_state(r)
        et = evidence_tier(r, cols)
        reg = f"{gs}|{et}"
        n_regime[reg] = n_regime.get(reg, 0) + 1
        n_state[gs] = n_state.get(gs, 0) + 1
        n_tier[et] = n_tier.get(et, 0) + 1
        by_regime.setdefault(reg, set()).add(str(r.get("match_id") or r.get("source_match_id")))
    return {
        "rows_per_regime": dict(sorted(n_regime.items())),
        "matches_per_regime": {k: len(v) for k, v in sorted(by_regime.items())},
        "rows_per_game_state": dict(sorted(n_state.items())),
        "rows_per_evidence_tier": dict(sorted(n_tier.items())),
    }
