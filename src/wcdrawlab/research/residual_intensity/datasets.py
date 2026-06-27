"""Dataset loading + annotation for the residual goal-intensity phase.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Reuses the already-built, already-leakage-checked event-process snapshot+target tables and the
event_process eval loader (which joins targets, attaches the leakage-safe side-specific remaining-goal
labels ``rem_goals_home/away``, enforces international-only, and asserts NO 2026 World Cup rows). On top
of that this module:

  * annotates each row with the W2 reference intensities (w2_lam_home/away/diff, w2_remaining_fraction,
    w2_current_diff) -- features.annotate_w2;
  * annotates per-row event-process completeness + xG availability -- availability.annotate_completeness;
  * annotates the interpretable regime label -- regimes.annotate;
  * provides leave-one-competition-out (LOCO) folds and a forward-chaining-by-competition order;
  * provides a deterministic SYNTHETIC generator (no files) so self-tests run without touching disk.

It NEVER fits a model and NEVER reads a target into a feature column. Targets stay as separate keys
(target_wdl, rem_goals_home/away, any_goal_next{5,10,15}m, next_goal_any_15) added by the eval loader.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.event_process import eval as EPE  # join loader + assert_no_2026 (leakage-safe)
from . import availability as AV
from . import features as F
from . import regimes as RG

DATASETS_VERSION = "residual_intensity_datasets_v1"


class DataInsufficient(Exception):
    """Raised when a required local product is absent/empty so a job can emit an honest skip."""


def annotate(rows: Sequence[dict]) -> List[dict]:
    """Attach W2 reference intensities + completeness + regime labels in-place; return the list. Safe to
    call repeatedly (idempotent)."""
    F.annotate_w2(rows)
    AV.annotate_completeness(rows, F.ALL_FEATURE_COLS)
    RG.annotate(rows, F.ALL_FEATURE_COLS)
    return list(rows)


def load_residual_rows() -> Dict[str, object]:
    """Load + join the international event-process snapshots/targets and annotate them for this phase.

    Returns {'rows', 'n_matches', 'n_competitions'}. Raises DataInsufficient if the underlying tables
    are absent (honest skip -- never fabricates rows). No-2026 + international-only are enforced upstream
    by the event_process eval loader (re-asserted here for traceability).
    """
    try:
        bundle = EPE.load_eval_rows()
    except EPE.DataInsufficient as e:
        raise DataInsufficient(str(e))
    rows = list(bundle["snapshot_rows"])
    EPE.assert_no_2026(rows)  # belt-and-suspenders: never fit/select on completed 2026 WC
    annotate(rows)
    return {"rows": rows,
            "n_matches": bundle["n_matches"],
            "n_competitions": bundle["n_competitions"]}


def load_club_aux_rows(max_rows: Optional[int] = None) -> List[dict]:
    """Club auxiliary rows (for the club-transfer representation ONLY). Annotated like intl rows but
    tagged comp_type='club'; the caller must NEVER use these as international test rows."""
    try:
        rows = EPE.load_club_aux_rows(max_rows=max_rows)
    except EPE.DataInsufficient:
        return []
    except Exception:
        return []
    annotate(rows)
    return rows


# =================================================================================================
# folds
# =================================================================================================
def loco_folds(rows: Sequence[dict]) -> Iterator[Tuple[str, List[dict], List[dict]]]:
    """Leave-one-competition-out folds keyed on 'competition'. Each test fold is one competition; train
    is every other competition. International rows only (club rows must not appear here)."""
    comps = sorted({r.get("competition") for r in rows if r.get("comp_type", "international") == "international"})
    intl = [r for r in rows if r.get("comp_type", "international") == "international"]
    for held in comps:
        train = [r for r in intl if r.get("competition") != held]
        test = [r for r in intl if r.get("competition") == held]
        if train and test:
            yield held, train, test


def forward_chain_order(rows: Sequence[dict]) -> List[str]:
    """Competitions ordered by earliest kickoff date (forward-chaining order). Falls back to label sort
    when dates are missing."""
    first_date: Dict[str, str] = {}
    for r in rows:
        comp = r.get("competition")
        k = r.get("kickoff_date") or ""
        if comp is None:
            continue
        if comp not in first_date or (k and k < first_date[comp]):
            first_date[comp] = k
    return [c for c, _ in sorted(first_date.items(), key=lambda kv: (kv[1] or "~", kv[0]))]


# =================================================================================================
# deterministic synthetic generator (no files) -- for self-tests / smoke
# =================================================================================================
def synthetic_rows(n_matches: int = 6, seed: int = 7) -> List[dict]:
    """Build a small deterministic set of residual-intensity rows shaped like the real joined panel.
    Two synthetic 'competitions' so LOCO has >= 2 folds. Includes rows with MISSING xG (xg_present
    False) and missing event-process cells so availability/gate self-tests exercise real missingness.
    Targets are attached (target_wdl, rem_goals_home/away, any_goal_next{5,10,15}m, next_goal_any_15)
    but NEVER as features. No disk, no network."""
    import numpy as np
    rng = np.random.default_rng(seed)
    rows: List[dict] = []
    comps = ["SynthCupA", "SynthCupB"]
    for m in range(n_matches):
        comp = comps[m % 2]
        mid = f"S{m:03d}"
        reg_h = int(rng.integers(0, 4))
        reg_a = int(rng.integers(0, 4))
        tgt = "H" if reg_h > reg_a else ("A" if reg_a > reg_h else "D")
        # every 3rd match has NO xG source (xg_present False) -> xG features must be unavailable
        has_xg = (m % 3 != 0)
        # a couple of decision minutes
        for t in (20.0, 40.0, 60.0, 75.0):
            cur_h = int(round(reg_h * (t / 90.0)))
            cur_a = int(round(reg_a * (t / 90.0)))
            rem_frac = (90.0 - t) / 90.0
            row: dict = {
                "source_match_id": mid, "match_id": mid, "competition": comp,
                "competition_label": comp, "comp_type": "international",
                "kickoff_date": f"2024-0{1 + (m % 2)}-15",
                "snapshot_minute": t, "snapshot_reason": "clock",
                "remaining_regulation_min": 90.0 - t, "period": 1 if t < 45 else 2,
                "goals_home": cur_h, "goals_away": cur_a, "goals_diff": cur_h - cur_a,
                "players_home": 11, "players_away": 11, "players_diff": 0,
                "yellow_diff": int(rng.integers(-1, 2)), "sendoff_diff": 0,
                "subs_used_diff": int(rng.integers(-2, 3)),
                "poss_share_home": float(0.4 + 0.2 * rng.random()),
                "poss_share_diff": float(-0.2 + 0.4 * rng.random()),
                "final_third_actions_diff": int(rng.integers(-10, 11)),
                "field_tilt_home": float(0.4 + 0.2 * rng.random()),
                "box_entries_home": int(rng.integers(0, 12)), "box_entries_away": int(rng.integers(0, 12)),
                "box_entries_diff": int(rng.integers(-6, 7)),
                "recoveries_diff": int(rng.integers(-8, 9)), "turnovers_diff": int(rng.integers(-8, 9)),
                "corners_diff": int(rng.integers(-4, 5)), "att_free_kicks_diff": int(rng.integers(-5, 6)),
                "shots_diff": int(rng.integers(-6, 7)), "shots_on_target_diff": int(rng.integers(-4, 5)),
                "n_events_observed": int(500 + rng.integers(0, 800)),
                # targets (NEVER used as features)
                "target_wdl": tgt,
                "rem_goals_home": float(max(0, reg_h - cur_h)),
                "rem_goals_away": float(max(0, reg_a - cur_a)),
                "any_goal_next5m": int(rng.integers(0, 2)),
                "any_goal_next10m": int(rng.integers(0, 2)),
                "any_goal_next15m": int(rng.integers(0, 2)),
                "next_goal_any_15": int(rng.integers(0, 2)),
            }
            if has_xg:
                row["xg_present"] = "True"
                row["cum_xg_home"] = float(reg_h * (t / 90.0) * (0.8 + 0.4 * rng.random()))
                row["cum_xg_away"] = float(reg_a * (t / 90.0) * (0.8 + 0.4 * rng.random()))
                row["cum_xg_diff"] = row["cum_xg_home"] - row["cum_xg_away"]
                row["cum_xg_total"] = row["cum_xg_home"] + row["cum_xg_away"]
                row["xg_last5m_diff"] = float(-0.3 + 0.6 * rng.random())
                row["xg_last10m_diff"] = float(-0.4 + 0.8 * rng.random())
                row["min_since_last_shot_any"] = float(rng.random() * 8.0)
            else:
                # NO xG source: leave the xG cells ABSENT (do not zero-fill) and mark xg_present False
                row["xg_present"] = "False"
            rows.append(row)
    annotate(rows)
    return rows
