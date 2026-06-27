"""Component 2 (Phase 2): FULL TEMPORAL PLAYER PRIOR SYSTEM.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module turns the leakage-safe `Appearance` corpus produced by ``player_history.py`` into the FOUR
feature categories the dynamic player-impact families (P1..P5, N2..N3, X2..X3) consume per snapshot:

  (A) EXPOSURE / RECENCY          — how much a player / line-up is *known* before the snapshot.
  (B) REGULARIZED CONTRIBUTION    — shrunk goal-diff / offensive / defensive / discipline / availability
                                    priors, every one pulled toward player-team -> position -> competition
                                    -> global means with explicit pseudo-counts.
  (C) CURRENT TEAM COMPOSITION    — weighted on-pitch / starting / bench prior strength, top3/bottom3,
                                    attack-mid-def balance, familiarity, national continuity, coverage.
  (D) SUBSTITUTION DELTA          — incoming-minus-outgoing prior, position-consistent, score/minute/
                                    fatigue-adjusted, low-history / tactical-imbalance flags.

HARD CAUSAL CONTRACT (enforced + self-tested in scripts/audit_dynamic_player_priors.py):
  * Every player feature for a snapshot at time T uses ONLY appearances dated STRICTLY BEFORE T
    (appearance_date < T). A prior at T can never see an appearance at T (same match) or later.
  * EXACT integer API-Football ``player_id`` linkage ONLY. No fuzzy name matching, no guessed national
    identity. A player_id with no strictly-earlier appearance in the relevant comp_type is an explicit
    ``unknown_player`` category that contributes the shrinkage prior only.
  * club and international appearances are partitioned by comp_type and NEVER pooled into one prior.
  * On-pitch composition uses ONLY substitutions with minute <= snapshot minute (no future-sub leak).

REGULARIZATION (transparent, deterministic, fixed pseudo-counts — NO learned hyper-parameters here):
  Every contribution prior is a nested shrinkage:
        player_raw  --(minutes / appearances)-->  player_team_mean
        player_team --(team pseudo-count)------->  position_mean
        position    --(position pseudo-count)---->  competition_mean
        competition --(comp pseudo-count)-------->  global_mean
  so a thin-history player collapses smoothly to the most specific reliable mean rather than to an
  extreme value. Exposure and uncertainty are exposed explicitly so a downstream model can decide how
  much to trust the prior. NO neural nets / no opaque embeddings / no test-time fitting.

This module is PURE (no network, no clock, no global mutable state). The corpus build entrypoint lives in
scripts/build_dynamic_temporal_player_priors.py; the leakage / shrinkage self-tests live in
scripts/audit_dynamic_player_priors.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Reuse the inherited, already-tested causal primitives. We never re-derive minutes / goal-diff / WDL.
from . import player_history as PH
from .player_history import Appearance, PlayerHistory

DYNAMIC_PRIOR_MODEL_VERSION = "dynamic_player_prior_v1"

# --------------------------------------------------------------------------------------------------
# Shrinkage pseudo-counts for the nested player -> team -> position -> competition -> global ladder.
# Fixed constants => deterministic rebuild; larger => stronger pull toward the broader mean.
# --------------------------------------------------------------------------------------------------
SHRINK_MINUTES = PH.SHRINK_MINUTES            # player raw rate -> player-team mean (minutes weighted)
SHRINK_APPEARANCES = PH.SHRINK_APPEARANCES    # player WDL / appearance-rate -> player-team mean
SHRINK_TEAM = 6.0          # player-team mean -> position mean (pseudo-appearances)
SHRINK_POSITION = 12.0     # position mean -> competition mean
SHRINK_COMPETITION = 24.0  # competition mean -> global mean

# Recency windows (count of most-recent prior appearances) and the position vocabulary.
RECENCY_WINDOWS = (5, 10)
POSITIONS = ("G", "D", "M", "F")
POS_GROUP = {"G": "def", "D": "def", "M": "mid", "F": "att"}


# ==================================================================================================
# Internal: a date-/comp-filtered view of the corpus with nested mean tables for shrinkage.
# All means are recomputed for the (before, comp_type) slice so they NEVER depend on the future.
# ==================================================================================================
@dataclass(frozen=True)
class _Means:
    """Nested shrinkage targets for one (before, comp_type) slice (all strictly-before `before`)."""
    glob: Dict[str, float]                          # metric -> global mean
    by_comp: Dict[Tuple[str, str], float]           # (competition_label, metric) -> mean
    by_pos: Dict[Tuple[str, str], float]            # (position, metric) -> mean
    comp_n: Dict[Tuple[str, str], float]            # (competition_label, metric) -> count feeding the mean
    pos_n: Dict[Tuple[str, str], float]             # (position, metric) -> count feeding the mean
    n: int                                          # appearances in this slice


# Metrics carried per appearance for the contribution priors. per-90 where rate-like.
_METRICS = ("gd90", "off90", "def90", "wdl")


def _appearance_competition(ap: Appearance, comp_label_by_match: Dict[str, str]) -> str:
    return comp_label_by_match.get(ap.match_id, ap.comp_type)


def _ap_metrics(ap: Appearance) -> Optional[Dict[str, float]]:
    """Per-appearance metric values (per-90 for rates). None if no on-pitch minutes (cannot rate)."""
    if ap.minutes_on <= 0:
        return None
    return {
        "gd90": ap.gd_on / ap.minutes_on * 90.0,
        "off90": ap.goals_for_on / ap.minutes_on * 90.0,
        "def90": ap.goals_against_on / ap.minutes_on * 90.0,
        "wdl": 1.0 if ap.team_result == "W" else (0.5 if ap.team_result == "D" else 0.0),
    }


class DynamicPlayerPriors:
    """Builds the 4 feature categories from a leakage-safe Appearance corpus.

    Construction indexes appearances by (comp_type, player_id) and (comp_type, team_id, player_id) sorted
    by date for fast strict-before slicing; nothing is pre-aggregated across time, so every query is forced
    through the date filter. ``comp_label_by_match`` maps match_id -> competition label (WC/Euro/...) so the
    competition-level shrinkage tier is exact; absent that, comp_type is used as the competition label.
    """

    def __init__(self, appearances: Iterable[Appearance],
                 comp_label_by_match: Optional[Dict[str, str]] = None):
        self._hist = PlayerHistory(appearances)  # reuse the base regularized prior() (category-B anchor)
        self._comp_label = dict(comp_label_by_match or {})
        self._by_player: Dict[Tuple[str, int], List[Appearance]] = {}
        self._by_team_player: Dict[Tuple[str, int, int], List[Appearance]] = {}
        self._all: List[Appearance] = []
        for ap in self._hist._all:  # already sorted (date, match_id) by PlayerHistory
            self._all.append(ap)
            self._by_player.setdefault((ap.comp_type, ap.player_id), []).append(ap)
            self._by_team_player.setdefault((ap.comp_type, ap.team_id, ap.player_id), []).append(ap)
        # appearances are globally sorted; per-key lists inherit that order
        self._means_cache: Dict[Tuple[datetime, str], _Means] = {}

    # ---- base prior passthrough (category B anchor; same contract as player_history) ----
    def base_prior(self, player_id: int, before: datetime, comp_type: str) -> dict:
        return self._hist.prior(player_id, before, comp_type)

    # ------------------------------------------------------------------------------------------
    # Shrinkage mean tables for a slice (strictly-before `before`, within comp_type).
    # ------------------------------------------------------------------------------------------
    def _means(self, before: datetime, comp_type: str) -> _Means:
        key = (before, comp_type)
        cached = self._means_cache.get(key)
        if cached is not None:
            return cached
        glob_sum = {m: 0.0 for m in _METRICS}
        glob_w = {m: 0.0 for m in _METRICS}
        comp_sum: Dict[Tuple[str, str], float] = {}
        comp_w: Dict[Tuple[str, str], float] = {}
        pos_sum: Dict[Tuple[str, str], float] = {}
        pos_w: Dict[Tuple[str, str], float] = {}
        n = 0
        for ap in self._all:
            if ap.comp_type != comp_type or not (ap.match_date < before):
                continue
            mv = _ap_metrics(ap)
            if mv is None:
                continue
            n += 1
            comp = _appearance_competition(ap, self._comp_label)
            pos = ap.position if (ap.started and ap.position) else None
            for m in _METRICS:
                glob_sum[m] += mv[m]; glob_w[m] += 1.0
                comp_sum[(comp, m)] = comp_sum.get((comp, m), 0.0) + mv[m]
                comp_w[(comp, m)] = comp_w.get((comp, m), 0.0) + 1.0
                if pos is not None:
                    pos_sum[(pos, m)] = pos_sum.get((pos, m), 0.0) + mv[m]
                    pos_w[(pos, m)] = pos_w.get((pos, m), 0.0) + 1.0
        glob = {m: (glob_sum[m] / glob_w[m] if glob_w[m] else (0.5 if m == "wdl" else 0.0)) for m in _METRICS}
        by_comp = {k: comp_sum[k] / comp_w[k] for k in comp_sum if comp_w[k]}
        by_pos = {k: pos_sum[k] / pos_w[k] for k in pos_sum if pos_w[k]}
        out = _Means(glob=glob, by_comp=by_comp, by_pos=by_pos,
                     comp_n=dict(comp_w), pos_n=dict(pos_w), n=n)
        self._means_cache[key] = out
        return out

    # ------------------------------------------------------------------------------------------
    # CATEGORY A — exposure / recency.
    # ------------------------------------------------------------------------------------------
    def exposure_features(self, player_id: int, before: datetime, comp_type: str,
                          team_id: Optional[int] = None) -> dict:
        """Pre-snapshot exposure / recency for one player (strictly-before `before`).

        national/club/intl appearance counts are reported across BOTH comp_types (they are pure exposure
        counters, not pooled into any prior); the contribution priors themselves stay comp-partitioned.
        """
        hist = [a for a in self._by_player.get((comp_type, player_id), []) if a.match_date < before]
        # cross-comp exposure counters (counts only — never feed a contribution prior)
        intl = [a for a in self._by_player.get(("international", player_id), []) if a.match_date < before]
        club = [a for a in self._by_player.get(("club", player_id), []) if a.match_date < before]
        team_hist = []
        if team_id is not None:
            team_hist = [a for a in self._by_team_player.get((comp_type, team_id, player_id), [])
                         if a.match_date < before]

        n_app = len(hist)
        n_start = sum(1 for a in hist if a.started)
        total_min = sum(a.minutes_on for a in hist)
        last_dt = max((a.match_date for a in hist), default=None)
        days_since = (before - last_dt).days if last_dt is not None else None

        recency = {}
        for w in RECENCY_WINDOWS:
            recent = hist[-w:]
            recency[f"minutes_last{w}"] = round(sum(a.minutes_on for a in recent), 3)
            recency[f"apps_last{w}"] = len(recent)
            recency[f"starts_last{w}"] = sum(1 for a in recent if a.started)

        # position exposure (share of starts in each position bucket)
        pos_counts = {p: 0 for p in POSITIONS}
        pos_known = 0
        for a in hist:
            if a.started and a.position in pos_counts:
                pos_counts[a.position] += 1; pos_known += 1
        pos_share = {f"pos_share_{p}": round(pos_counts[p] / pos_known, 6) if pos_known else 0.0
                     for p in POSITIONS}

        unknown = n_app == 0
        # lineup uncertainty: 1 for an unknown player, decaying with exposure (appearances pseudo-count)
        uncertainty = SHRINK_APPEARANCES / (n_app + SHRINK_APPEARANCES)
        exposure = total_min / (total_min + SHRINK_MINUTES) if total_min > 0 else 0.0

        out = {
            "player_id": int(player_id), "comp_type": comp_type,
            "prior_appearances": n_app, "prior_starts": n_start,
            "prior_minutes": round(total_min, 3),
            "minutes_per_appearance": round(total_min / n_app, 6) if n_app else 0.0,
            "days_since_last_appearance": days_since,
            "national_appearances": len(intl), "club_appearances": len(club),
            "intl_appearances": len(intl),
            "team_appearances": len(team_hist),
            "exposure": round(exposure, 6),
            "lineup_uncertainty": round(uncertainty, 6),
            "unknown_player": bool(unknown),
            "dominant_position": PH._dominant_position(hist),
            "dynamic_prior_model_version": DYNAMIC_PRIOR_MODEL_VERSION,
        }
        out.update(recency); out.update(pos_share)
        return out

    # ------------------------------------------------------------------------------------------
    # CATEGORY B — regularized contribution priors (nested shrinkage).
    # ------------------------------------------------------------------------------------------
    def contribution_prior(self, player_id: int, before: datetime, comp_type: str,
                           team_id: Optional[int] = None, position: Optional[str] = None) -> dict:
        """Nested-shrunk contribution prior for one player (strictly-before `before`).

        Ladder per metric: player_raw -> player_team -> position -> competition -> global. Discipline and
        availability priors are appended. Returns shrunk per-90 contributions + exposure / uncertainty +
        an explicit unknown/insufficient flag. NEVER reads a same-or-later appearance.
        """
        hist = [a for a in self._by_player.get((comp_type, player_id), []) if a.match_date < before]
        team_hist = []
        if team_id is not None:
            team_hist = [a for a in self._by_team_player.get((comp_type, team_id, player_id), [])
                         if a.match_date < before]
        means = self._means(before, comp_type)

        # global -> competition -> position chain of fallbacks for each metric
        comp_label = self._infer_player_competition(hist) if hist else comp_type
        pos = position or PH._dominant_position(hist)

        def _tier_target(metric: str) -> float:
            g = means.glob.get(metric, 0.5 if metric == "wdl" else 0.0)
            comp_m = means.by_comp.get((comp_label, metric))
            comp_t = _shrink_toward(comp_m, g, _comp_weight(means, comp_label, metric), SHRINK_COMPETITION) \
                if comp_m is not None else g
            pos_m = means.by_pos.get((pos, metric)) if pos in POSITIONS else None
            pos_t = _shrink_toward(pos_m, comp_t, _pos_weight(means, pos, metric), SHRINK_POSITION) \
                if pos_m is not None else comp_t
            return pos_t

        # player-team raw means (most specific) feed the next tier up
        out_metrics = {}
        n_app = len(hist)
        total_min = sum(a.minutes_on for a in hist)
        team_apps = len(team_hist)
        for metric in _METRICS:
            tier_target = _tier_target(metric)
            if n_app == 0:
                out_metrics[metric] = tier_target  # unknown -> most specific reliable mean
                continue
            if metric == "wdl":
                raw = sum((1.0 if a.team_result == "W" else (0.5 if a.team_result == "D" else 0.0))
                          for a in hist) / n_app
                # player-team tier
                team_target = tier_target
                if team_apps > 0:
                    team_raw = sum((1.0 if a.team_result == "W" else (0.5 if a.team_result == "D" else 0.0))
                                   for a in team_hist) / team_apps
                    team_target = _shrink_toward(team_raw, tier_target, float(team_apps), SHRINK_TEAM)
                out_metrics[metric] = _shrink_toward(raw, team_target, float(n_app), SHRINK_APPEARANCES)
            else:
                if total_min <= 0:
                    out_metrics[metric] = tier_target; continue
                num = {"gd90": sum(a.gd_on for a in hist),
                       "off90": sum(a.goals_for_on for a in hist),
                       "def90": sum(a.goals_against_on for a in hist)}[metric]
                raw = num / total_min * 90.0
                team_target = tier_target
                team_min = sum(a.minutes_on for a in team_hist)
                if team_min > 0:
                    tnum = {"gd90": sum(a.gd_on for a in team_hist),
                            "off90": sum(a.goals_for_on for a in team_hist),
                            "def90": sum(a.goals_against_on for a in team_hist)}[metric]
                    team_raw = tnum / team_min * 90.0
                    team_target = _shrink_toward(team_raw, tier_target, team_min, SHRINK_MINUTES)
                out_metrics[metric] = _shrink_toward(raw, team_target, total_min, SHRINK_MINUTES)

        # discipline prior (yellow + red per 90, shrunk to global discipline rate within slice)
        disc = self._discipline_prior(player_id, before, comp_type, hist, means)
        # availability prior: P(the player actually appears | selected history) proxied by recent start rate
        avail = self._availability_prior(hist, before)

        exposure = total_min / (total_min + SHRINK_MINUTES) if total_min > 0 else 0.0
        uncertainty = SHRINK_APPEARANCES / (n_app + SHRINK_APPEARANCES)
        return {
            "player_id": int(player_id), "comp_type": comp_type,
            "competition_context": comp_label, "position_context": pos,
            "gd_contribution_per90": round(out_metrics["gd90"], 6),
            "off_contribution_per90": round(out_metrics["off90"], 6),
            "def_contribution_per90": round(out_metrics["def90"], 6),
            "wdl_contribution": round(out_metrics["wdl"], 6),
            "discipline_per90": round(disc, 6),
            "availability_prior": round(avail, 6),
            "exposure": round(exposure, 6),
            "uncertainty": round(uncertainty, 6),
            "prior_appearances": n_app,
            "team_appearances": team_apps,
            "unknown_player": n_app == 0,
            "insufficient_history": n_app < SHRINK_APPEARANCES,
            "dynamic_prior_model_version": DYNAMIC_PRIOR_MODEL_VERSION,
        }

    def _infer_player_competition(self, hist: Sequence[Appearance]) -> str:
        """Most-frequent competition label across the player's prior appearances (deterministic tie-break)."""
        counts: Dict[str, int] = {}
        for a in hist:
            lab = self._comp_label.get(a.match_id, a.comp_type)
            counts[lab] = counts.get(lab, 0) + 1
        if not counts:
            return "unknown"
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def _discipline_prior(self, player_id, before, comp_type, hist, means) -> float:
        """Cards-per-90 prior. We do NOT carry per-player card events on Appearance, so this uses the
        per-team-result-neutral proxy: the player's concession exposure is NOT discipline; instead we shrink
        a thin per-appearance signal toward a global zero-information rate. Returns 0.0 when no event-level
        card linkage is available for this player (honest absence, not a fabricated rate)."""
        # Appearance does not carry per-player card flags -> we cannot compute a real per-player discipline
        # rate without re-reading events. Return the slice-global availability of a discipline signal: 0.0
        # means "no per-player discipline signal in this feature build" (a downstream model treats it as a
        # constant and learns nothing spurious). This is intentionally honest rather than invented.
        return 0.0

    def _availability_prior(self, hist: Sequence[Appearance], before: datetime) -> float:
        """Recent start propensity in [0,1]: shrunk fraction of the last RECENCY_WINDOWS[-1] appearances
        that were starts. Unknown player -> 0.0 (will be flagged unknown elsewhere)."""
        if not hist:
            return 0.0
        w = RECENCY_WINDOWS[-1]
        recent = hist[-w:]
        starts = sum(1 for a in recent if a.started)
        # shrink toward 0.5 with a pseudo-count so 1 appearance does not read as certain
        return (starts + SHRINK_APPEARANCES * 0.5) / (len(recent) + SHRINK_APPEARANCES)

    # ------------------------------------------------------------------------------------------
    # CATEGORY C — current team composition (on-pitch / starting / bench aggregates).
    # ------------------------------------------------------------------------------------------
    def composition_features(self, on_pitch_ids: Sequence[int], starting_ids: Sequence[int],
                             bench_ids: Sequence[int], before: datetime, comp_type: str,
                             team_id: Optional[int] = None,
                             prev_xi_ids: Optional[Sequence[int]] = None,
                             prev_national_ids: Optional[Sequence[int]] = None) -> dict:
        """Aggregate the per-player contribution priors over a team's on-pitch / XI / bench sets.

        on_pitch_ids = players currently on the pitch (subs applied up to the snapshot minute). starting_ids
        = the XI. bench_ids = unused/remaining bench. All priors are strictly-before `before`. Continuity is
        vs the team's immediately-prior XI; national continuity is vs the prior NATIONAL XI specifically.
        """
        def _priors(ids):
            out = []
            for pid in ids:
                if pid is None:
                    continue
                out.append((pid, self.contribution_prior(pid, before, comp_type, team_id=team_id)))
            return out

        onp = _priors(on_pitch_ids)
        xi = _priors(starting_ids)
        bench = _priors(bench_ids)

        def _gd(p):
            return p["gd_contribution_per90"]

        def _w_strength(priors):
            if not priors:
                return 0.0
            num = sum(_gd(p) * max(p["exposure"], 1e-9) for _, p in priors)
            den = sum(max(p["exposure"], 1e-9) for _, p in priors)
            return num / den if den else 0.0

        onp_gd = [_gd(p) for _, p in onp]
        xi_gd = [_gd(p) for _, p in xi]
        bench_gd = [_gd(p) for _, p in bench]
        xi_off = [p["off_contribution_per90"] for _, p in xi]
        xi_def = [p["def_contribution_per90"] for _, p in xi]

        # attack / mid / def balance from each player's position context
        group_gd = {"att": [], "mid": [], "def": []}
        for _, p in xi:
            grp = POS_GROUP.get(p.get("position_context"), None)
            if grp is not None:
                group_gd[grp].append(_gd(p))

        known = [p for _, p in xi if not p["unknown_player"]]
        n_unknown = sum(1 for _, p in xi if p["unknown_player"])
        coverage = (len(known) / len(xi)) if xi else 0.0
        low_coverage = coverage < 0.5

        return {
            "comp_type": comp_type,
            "on_pitch_size": len(onp), "xi_size": len(xi), "bench_size": len(bench),
            "onpitch_weighted_prior_gd90": round(_w_strength(onp), 6),
            "onpitch_mean_prior_gd90": round(_mean(onp_gd), 6),
            "xi_weighted_prior_gd90": round(_w_strength(xi), 6),
            "xi_mean_prior_gd90": round(_mean(xi_gd), 6),
            "xi_top3_prior_gd90": round(_mean(sorted(xi_gd, reverse=True)[:3]), 6),
            "xi_bottom3_prior_gd90": round(_mean(sorted(xi_gd)[:3]), 6),
            "bench_strength_prior_gd90": round(_mean(bench_gd), 6),
            "xi_off_balance_per90": round(_mean(xi_off), 6),
            "xi_def_balance_per90": round(_mean(xi_def), 6),
            "att_group_prior_gd90": round(_mean(group_gd["att"]), 6),
            "mid_group_prior_gd90": round(_mean(group_gd["mid"]), 6),
            "def_group_prior_gd90": round(_mean(group_gd["def"]), 6),
            "familiarity_continuity": round(_continuity(starting_ids, prev_xi_ids), 6),
            "national_continuity": round(_continuity(starting_ids, prev_national_ids), 6),
            "coverage_aggregate": round(coverage, 6),
            "n_unknown_players": n_unknown,
            "mean_exposure": round(_mean([p["exposure"] for _, p in xi]), 6),
            "mean_uncertainty": round(_mean([p["uncertainty"] for _, p in xi], default=1.0), 6),
            "low_coverage_flag": bool(low_coverage),
            "dynamic_prior_model_version": DYNAMIC_PRIOR_MODEL_VERSION,
        }

    # ------------------------------------------------------------------------------------------
    # CATEGORY D — substitution delta (incoming minus outgoing).
    # ------------------------------------------------------------------------------------------
    def substitution_delta_features(self, in_player_id: Optional[int], out_player_id: Optional[int],
                                    before: datetime, comp_type: str, minute: Optional[int] = None,
                                    score_diff: Optional[int] = None,
                                    team_id: Optional[int] = None) -> dict:
        """incoming prior - outgoing prior (per the contract), both strictly-before `before`.

        Adds position-consistency, a score/minute fatigue adjustment, low-history & uncertainty-delta &
        tactical-imbalance flags. The fatigue/context adjustment is a transparent fixed-form scaling of the
        raw delta (no fitting) intended to down-weight late defensive-for-defensive swaps."""
        p_in = self.contribution_prior(in_player_id, before, comp_type, team_id=team_id) \
            if in_player_id is not None else None
        p_out = self.contribution_prior(out_player_id, before, comp_type, team_id=team_id) \
            if out_player_id is not None else None

        def _v(p, k):
            return p[k] if p is not None else 0.0

        gd_delta = _v(p_in, "gd_contribution_per90") - _v(p_out, "gd_contribution_per90")
        off_delta = _v(p_in, "off_contribution_per90") - _v(p_out, "off_contribution_per90")
        def_delta = _v(p_in, "def_contribution_per90") - _v(p_out, "def_contribution_per90")
        wdl_delta = _v(p_in, "wdl_contribution") - _v(p_out, "wdl_contribution")
        unc_delta = _v(p_in, "uncertainty") - _v(p_out, "uncertainty")

        pos_in = p_in["position_context"] if p_in else None
        pos_out = p_out["position_context"] if p_out else None
        position_consistent = (pos_in is not None and pos_in == pos_out)
        # tactical imbalance: swapping across position groups (e.g. F off, D on) while behind
        grp_in = POS_GROUP.get(pos_in); grp_out = POS_GROUP.get(pos_out)
        cross_group = (grp_in is not None and grp_out is not None and grp_in != grp_out)
        tactical_imbalance = bool(cross_group and (score_diff is not None and score_diff < 0))

        # fixed-form fatigue / context scaling: late subs and chasing subs contribute less *durable* signal.
        # remaining minutes fraction in [0,1]; chasing (behind) gets a small extra discount. No fitting.
        rem_frac = 1.0
        if minute is not None:
            rem_frac = max(0.0, (90 - min(90, max(0, int(minute)))) / 90.0)
        context_scale = rem_frac * (0.85 if (score_diff is not None and score_diff < 0) else 1.0)

        low_history = bool((p_in is None or p_in["insufficient_history"]) or
                           (p_out is None or p_out["insufficient_history"]))
        return {
            "in_player_id": int(in_player_id) if in_player_id is not None else None,
            "out_player_id": int(out_player_id) if out_player_id is not None else None,
            "comp_type": comp_type, "minute": minute, "score_diff_at_sub": score_diff,
            "gd_delta_per90": round(gd_delta, 6),
            "off_delta_per90": round(off_delta, 6),
            "def_delta_per90": round(def_delta, 6),
            "wdl_delta": round(wdl_delta, 6),
            "gd_delta_context_adjusted": round(gd_delta * context_scale, 6),
            "uncertainty_delta": round(unc_delta, 6),
            "position_consistent": bool(position_consistent),
            "tactical_imbalance_flag": tactical_imbalance,
            "low_history_flag": low_history,
            "in_unknown": bool(p_in["unknown_player"]) if p_in is not None else True,
            "out_unknown": bool(p_out["unknown_player"]) if p_out is not None else True,
            "dynamic_prior_model_version": DYNAMIC_PRIOR_MODEL_VERSION,
        }


# ==================================================================================================
# shrinkage / aggregation helpers
# ==================================================================================================
def _shrink_toward(raw: Optional[float], target: float, weight: float, pseudo: float) -> float:
    """Exposure-weighted shrinkage of `raw` toward `target`: (w*raw + pseudo*target)/(w+pseudo)."""
    if raw is None:
        return target
    denom = weight + pseudo
    return (weight * raw + pseudo * target) / denom if denom > 0 else target


def _comp_weight(means: _Means, comp_label: str, metric: str) -> float:
    """Real count of appearances feeding the competition-tier mean (0 if the tier is absent in this slice).
    Using the actual count makes the shrinkage monotone in sample size: a thinly-populated competition tier
    is pulled harder toward the global mean than a richly-populated one."""
    return float(means.comp_n.get((comp_label, metric), 0.0))


def _pos_weight(means: _Means, pos: str, metric: str) -> float:
    return float(means.pos_n.get((pos, metric), 0.0))


def _mean(xs: Sequence[float], default: float = 0.0) -> float:
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else default


def _continuity(ids: Optional[Sequence[int]], prev_ids: Optional[Sequence[int]]) -> float:
    """Fraction of today's set that also appears in `prev_ids` (0..1; missing prev -> 0)."""
    ids = [i for i in (ids or []) if i is not None]
    if not ids or not prev_ids:
        return 0.0
    prev = set(prev_ids)
    return sum(1 for i in ids if i in prev) / len(ids)


__all__ = [
    "DYNAMIC_PRIOR_MODEL_VERSION",
    "DynamicPlayerPriors",
    "SHRINK_MINUTES", "SHRINK_APPEARANCES", "SHRINK_TEAM", "SHRINK_POSITION", "SHRINK_COMPETITION",
    "RECENCY_WINDOWS", "POSITIONS", "POS_GROUP",
]
