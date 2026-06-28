"""Phase 3 -- CAUSAL DOMAIN-NORMALIZED TRANSFER DATASETS (no test-tournament leak).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module assembles, for each OUTER TEMPORAL FOLD, the leakage-safe transfer rows the hierarchical
partial-pooling ladder (T0..T7) consumes. It NEVER fits a model that enters the held-out test fold; the
only quantities it fits are (a) the per-DOMAIN score/time reference-intensity BASELINE and (b) the
stable-feature filter -- and BOTH are fit on TRAINING ROWS ONLY for the fold (intl-train + club-aux-train),
then APPLIED to the held-out international test rows. The TRANSFER TARGET on every row is the event-process
RESIDUAL beyond that domain's OWN baseline:

    transfer_target = observed_remaining_goals(side)  -  domain_baseline_intensity(side | state)

where ``domain_baseline_intensity`` is a parameter-free-shaped reference (a function of score-state, time,
remaining fraction, orientation, numerical-state and a per-DOMAIN INTERCEPT) calibrated on the fold's
training rows. The T0 reference (``w2_reference_t0``) is the common, domain-AGNOSTIC anchor; the domain
baseline is the per-domain shift the residual is taken relative to.

HARD invariants (re-asserted by the audit script + tests):
  * outer fold training = matches kicking off STRICTLY BEFORE the held-out international tournament's
    first kickoff (no future-tournament event ever trains a fold);
  * the held-out test fold is a SINGLE international tournament; CLUB rows NEVER appear as test rows;
  * domain baselines + the stable-feature filter are fit on TRAINING rows only (no test-fold leakage);
  * snapshot features at minute t use only events with match-clock minute <= t (enforced upstream by the
    event_process engine; re-asserted via n_events_observed monotonicity in the audit);
  * no completed-2026-World-Cup match in ANY domain / fold (assert_no_2026);
  * domain-shifted / source-incompatible feature columns are EXCLUDED from the transfer model space
    (the stable-feature subset is the intersection that survives the per-domain availability + shift gate);
  * deterministic: identical inputs -> identical rows/folds (no RNG in the dataset path).

The module is import-clean WITHOUT touching disk. The real rows are produced by
``scripts/build_domain_normalized_transfer_dataset.py`` (which feeds this module lake-resolved snapshot
rows). A deterministic SYNTHETIC generator (no files) makes the self-tests run anywhere.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from . import (
    DOMAIN_CLUB,
    DOMAIN_INTERNATIONAL,
    ELIGIBILITY_LABELS,
    REFERENCE_MODEL,
)
from . import w2_reference_t0 as T0

DATASET_VERSION = "domain_normalized_transfer_dataset_v1"


class DataInsufficient(Exception):
    """Raised when a required local product is absent/empty so a job can emit an honest skip (never
    fabricates rows)."""


# =================================================================================================
# numeric helpers (preserve missingness; never coerce a missing cell to 0)
# =================================================================================================
def fnum(row: dict, col: str) -> Optional[float]:
    if col not in row:
        return None
    v = row.get(col)
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("none", "nan", "null"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_2026_wc(label: Optional[str], kickoff: Optional[str]) -> bool:
    lab = (label or "").lower()
    if "2026" in lab and ("world cup" in lab or "worldcup" in lab or "fifa" in lab):
        return True
    if (kickoff or "").startswith("2026") and "world cup" in lab:
        return True
    return False


def assert_no_2026(rows: Sequence[dict]) -> None:
    bad = [r for r in rows
           if _is_2026_wc(r.get("competition_label") or r.get("competition"), r.get("kickoff_date"))]
    if bad:
        raise AssertionError(f"2026 World Cup rows present in transfer population ({len(bad)}) -- forbidden")


# =================================================================================================
# Domain-normalized STATE features (the only columns the transfer baseline / shift gate consider).
# These are the CAUSAL, domain-comparable state variables: score-state, time, remaining, orientation,
# numerical-state. Domain-shifted / source-incompatible raw event-process columns are NOT here; they are
# offered to the stable-feature filter separately and only survive if they pass the per-domain gate.
# =================================================================================================
# state design columns used by the per-domain baseline (parameter-free shape + domain intercept)
BASELINE_STATE_COLS: List[str] = [
    "score_diff_signed",     # current home-away regulation goal diff (orientation-aware)
    "remaining_fraction",    # (90 - t)/90  in [0,1]
    "minute_fraction",       # t/90 in [0,1]
    "players_diff",          # numerical-state (home - away on pitch); +ve => home advantage
    "is_second_half",        # period == 2
]

# candidate transfer features offered to the STABLE-FEATURE FILTER. Each is a domain-comparable,
# leakage-safe event-process state column. The filter (fit on TRAIN only) keeps the subset that is
# (a) populated in BOTH domains' training rows and (b) not domain-shifted beyond tolerance.
CANDIDATE_TRANSFER_FEATURE_COLS: List[str] = [
    "goals_diff", "players_diff", "yellow_diff", "sendoff_diff", "subs_used_diff",
    "poss_share_diff", "field_tilt_home", "final_third_actions_diff",
    "box_entries_diff", "recoveries_diff", "turnovers_diff",
    "corners_diff", "att_free_kicks_diff",
    "shots_diff", "shots_on_target_diff",
    "cum_xg_diff", "cum_xg_total", "xg_last5m_diff", "xg_last10m_diff",
]

# columns that are KNOWN to be domain-incompatible / source-shifted and are ALWAYS excluded from the
# transfer model space regardless of the gate (e.g. raw possession-action COUNTS scale with a league's
# event-logging density, not with goal pressure). Kept here as an explicit, auditable exclusion list.
ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS: List[str] = [
    "poss_actions_home", "poss_actions_away",   # raw action counts: logging-density dependent
    "n_events_observed",                        # leakage budget proxy: provenance, not a feature
]


def _orientation_sign(row: dict) -> int:
    """+1 if the row is stored in home-attacking orientation (default), -1 if explicitly flipped. The
    event-process snapshots are always home-minus-away, so this is +1 unless an explicit orientation
    flag says otherwise. Kept explicit so a future flipped source cannot silently invert the residual."""
    o = row.get("orientation")
    if o is None:
        return 1
    s = str(o).strip().lower()
    if s in ("flipped", "away", "-1", "reverse", "reversed"):
        return -1
    return 1


def derive_state(row: dict) -> Dict[str, float]:
    """Derive the domain-comparable causal state columns for a snapshot row. Pure; leakage-free."""
    sign = _orientation_sign(row)
    gd = fnum(row, "goals_diff")
    if gd is None:
        gh, ga = fnum(row, "goals_home"), fnum(row, "goals_away")
        gd = (gh - ga) if (gh is not None and ga is not None) else 0.0
    rem_frac = T0.remaining_fraction(row)
    mn = fnum(row, "snapshot_minute")
    min_frac = max(0.0, min(1.0, (mn / 90.0))) if mn is not None else (1.0 - rem_frac)
    pdf = fnum(row, "players_diff")
    period = fnum(row, "period")
    return {
        "score_diff_signed": float(sign) * float(gd),
        "remaining_fraction": rem_frac,
        "minute_fraction": min_frac,
        "players_diff": (float(sign) * pdf) if pdf is not None else 0.0,
        "is_second_half": 1.0 if (period is not None and period >= 2) else 0.0,
    }


# =================================================================================================
# DOMAIN BASELINE -- per-domain remaining-goal reference intensity (fit on TRAINING rows only).
#
# Shape: lambda_side = T0_intensity(state) * exp(beta_domain) where beta_domain is a per-domain log
# intercept fit so the domain baseline's MEAN remaining-goals matches the domain's TRAIN mean (a
# parameter-free-shaped, monotone-safe, closed-form calibration). The residual target is then taken
# relative to this domain-shifted baseline. NO test row participates in the fit.
# =================================================================================================
@dataclass
class DomainBaseline:
    """Per-domain remaining-goal reference-intensity baseline (the residual is taken relative to this).

    ``log_intercept[domain]`` shifts the symmetric T0 intensity to that domain's training mean. The
    baseline is a function of (score-state, time, remaining, orientation, numerical-state) + the domain
    intercept ONLY; it never reads a test row or a future event."""

    log_intercept: Dict[str, float] = field(default_factory=dict)
    train_mean_rem: Dict[str, float] = field(default_factory=dict)
    n_train_rows: Dict[str, int] = field(default_factory=dict)
    base_rate_per90: float = T0.BASE_RATE_PER90
    fitted_on: str = "train_rows_only"

    def intensity(self, row: dict, side: str, domain: Optional[str] = None) -> float:
        """Domain baseline expected REMAINING goals for ``side`` ('home'/'away') under this domain."""
        dom = domain or row.get("domain") or DOMAIN_INTERNATIONAL
        ref = T0.reference_intensity(row)
        lam = ref["t0_lam_home"] if side == "home" else ref["t0_lam_away"]
        b = self.log_intercept.get(dom, 0.0)
        # numerical-state nudge: a team a man up gets a small positive shift, scaled by remaining time
        st = derive_state(row)
        man_adv = st["players_diff"] if side == "home" else -st["players_diff"]
        nudge = 0.0
        if man_adv:
            nudge = 0.10 * man_adv * st["remaining_fraction"]
        return max(0.0, lam * math.exp(b) + nudge)


def fit_domain_baseline(train_rows: Sequence[dict]) -> DomainBaseline:
    """Fit the per-domain log intercept so each domain's baseline MEAN total remaining-goals equals that
    domain's TRAIN mean observed total remaining-goals. TRAIN ROWS ONLY. Deterministic closed form."""
    by_dom_obs: Dict[str, List[float]] = {}
    by_dom_ref: Dict[str, List[float]] = {}
    for r in train_rows:
        dom = r.get("domain") or DOMAIN_INTERNATIONAL
        oh = fnum(r, "rem_goals_home")
        oa = fnum(r, "rem_goals_away")
        if oh is None or oa is None:
            continue
        ref = T0.reference_intensity(r)
        by_dom_obs.setdefault(dom, []).append(oh + oa)
        by_dom_ref.setdefault(dom, []).append(ref["t0_lam_total"])
    bl = DomainBaseline()
    for dom, obs in by_dom_obs.items():
        ref = by_dom_ref[dom]
        mean_obs = sum(obs) / len(obs) if obs else 0.0
        mean_ref = sum(ref) / len(ref) if ref else 0.0
        # exp(beta) = mean_obs / mean_ref  (matches the domain baseline's mean to the train mean)
        if mean_ref > 1e-9 and mean_obs > 1e-9:
            bl.log_intercept[dom] = math.log(mean_obs / mean_ref)
        else:
            bl.log_intercept[dom] = 0.0
        bl.train_mean_rem[dom] = mean_obs
        bl.n_train_rows[dom] = len(obs)
    return bl


def residual_targets(row: dict, baseline: DomainBaseline, domain: Optional[str] = None) -> Dict[str, float]:
    """The TRANSFER TARGET on a row: observed remaining goals MINUS this domain's baseline intensity, per
    side and total. Returns None-valued residuals if the observed remaining-goal label is absent (never
    fabricates)."""
    dom = domain or row.get("domain") or DOMAIN_INTERNATIONAL
    oh = fnum(row, "rem_goals_home")
    oa = fnum(row, "rem_goals_away")
    bh = baseline.intensity(row, "home", dom)
    ba = baseline.intensity(row, "away", dom)
    out: Dict[str, float] = {
        "domain_baseline_home": round(bh, 6),
        "domain_baseline_away": round(ba, 6),
        "domain_baseline_total": round(bh + ba, 6),
    }
    if oh is None or oa is None:
        out.update({"transfer_residual_home": None, "transfer_residual_away": None,
                    "transfer_residual_total": None})
    else:
        out.update({
            "transfer_residual_home": round(oh - bh, 6),
            "transfer_residual_away": round(oa - ba, 6),
            "transfer_residual_total": round((oh + oa) - (bh + ba), 6),
        })
    return out


# =================================================================================================
# STABLE-FEATURE FILTER -- fit on TRAINING rows only. A candidate transfer feature survives iff it is
# (a) populated on >= min_present_frac of BOTH domains' training rows AND (b) the standardized mean
# difference between domains' training distributions is <= max_smd (not domain-shifted beyond tolerance).
# Always-excluded domain-shifted columns never survive. NO test row participates.
# =================================================================================================
@dataclass
class StableFeatureFilter:
    kept: List[str] = field(default_factory=list)
    dropped: Dict[str, str] = field(default_factory=dict)   # col -> reason
    per_feature: Dict[str, dict] = field(default_factory=dict)
    min_present_frac: float = 0.5
    max_smd: float = 1.0
    single_domain: bool = False
    fitted_on: str = "train_rows_only"

    def subset_size(self) -> int:
        return len(self.kept)


def _present_frac(rows: Sequence[dict], col: str) -> float:
    n = len(rows)
    if not n:
        return 0.0
    return sum(1 for r in rows if fnum(r, col) is not None) / n


def _mean_std(rows: Sequence[dict], col: str) -> Tuple[Optional[float], float, int]:
    vals = [fnum(r, col) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, 0.0, 0
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    return m, math.sqrt(var), len(vals)


def fit_stable_feature_filter(train_rows: Sequence[dict],
                              candidate_cols: Optional[Sequence[str]] = None,
                              min_present_frac: float = 0.5,
                              max_smd: float = 1.0) -> StableFeatureFilter:
    """Decide the stable-feature subset using TRAINING rows only. A feature is kept iff it is populated
    in both domains' training rows and not domain-shifted beyond ``max_smd`` (standardized mean diff).
    When only one domain is present in training, the cross-domain shift test is vacuous and a feature is
    kept on the availability test alone (single_domain=True is recorded)."""
    cols = list(candidate_cols if candidate_cols is not None else CANDIDATE_TRANSFER_FEATURE_COLS)
    intl = [r for r in train_rows if (r.get("domain") or DOMAIN_INTERNATIONAL) == DOMAIN_INTERNATIONAL]
    club = [r for r in train_rows if (r.get("domain") or DOMAIN_INTERNATIONAL) == DOMAIN_CLUB]
    single_domain = (len(club) == 0) or (len(intl) == 0)
    filt = StableFeatureFilter(min_present_frac=min_present_frac, max_smd=max_smd,
                               single_domain=single_domain)
    for c in cols:
        if c in ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS:
            filt.dropped[c] = "always_excluded_domain_shifted"
            filt.per_feature[c] = {"reason": "always_excluded_domain_shifted"}
            continue
        fi = _present_frac(intl, c) if intl else 0.0
        fc = _present_frac(club, c) if club else 0.0
        mi, si, ni = _mean_std(intl, c) if intl else (None, 0.0, 0)
        mc, sc, nc = _mean_std(club, c) if club else (None, 0.0, 0)
        info = {"present_frac_intl": round(fi, 4), "present_frac_club": round(fc, 4),
                "mean_intl": (round(mi, 5) if mi is not None else None),
                "mean_club": (round(mc, 5) if mc is not None else None)}
        # availability gate
        if single_domain:
            present_ok = (fi >= min_present_frac) if intl else (fc >= min_present_frac)
        else:
            present_ok = (fi >= min_present_frac) and (fc >= min_present_frac)
        if not present_ok:
            filt.dropped[c] = "insufficient_presence"
            filt.per_feature[c] = {**info, "reason": "insufficient_presence"}
            continue
        # cross-domain shift gate (only when both domains present)
        if not single_domain and mi is not None and mc is not None:
            pooled_sd = math.sqrt(((si ** 2) + (sc ** 2)) / 2.0) or 1.0
            smd = abs(mi - mc) / pooled_sd if pooled_sd > 1e-12 else 0.0
            info["smd"] = round(smd, 4)
            if smd > max_smd:
                filt.dropped[c] = "domain_shifted"
                filt.per_feature[c] = {**info, "reason": "domain_shifted"}
                continue
        filt.kept.append(c)
        filt.per_feature[c] = {**info, "reason": "kept"}
    return filt


# =================================================================================================
# OUTER TEMPORAL FOLDS -- one per held-out international tournament. Training = matches kicking off
# STRICTLY BEFORE the held-out tournament's first kickoff (intl-train) + ALL club-aux rows whose
# kickoff is before that boundary (temporal cutoff respected for the auxiliary domain too). Test = the
# held-out international tournament's matches (club rows NEVER appear in test).
# =================================================================================================
@dataclass
class OuterFold:
    held_tournament: str
    cutoff_kickoff: str
    intl_train_rows: List[dict]
    club_train_rows: List[dict]
    intl_test_rows: List[dict]

    @property
    def train_rows(self) -> List[dict]:
        return list(self.intl_train_rows) + list(self.club_train_rows)

    def n_intl_test_matches(self) -> int:
        return len({r.get("match_id") for r in self.intl_test_rows})

    def n_club_train_matches(self) -> int:
        return len({r.get("match_id") for r in self.club_train_rows})


def _tournament_first_kickoff(intl_rows: Sequence[dict]) -> Dict[str, str]:
    first: Dict[str, str] = {}
    for r in intl_rows:
        comp = r.get("competition_label") or r.get("competition")
        ko = r.get("kickoff_date") or ""
        if comp is None or not ko:
            continue
        if comp not in first or ko < first[comp]:
            first[comp] = ko
    return first


def outer_temporal_folds(intl_rows: Sequence[dict],
                         club_rows: Optional[Sequence[dict]] = None) -> List[OuterFold]:
    """Build the outer temporal folds. Each held-out international tournament becomes one fold; training
    is every match (intl + club aux) kicking off STRICTLY BEFORE that tournament's first kickoff. A
    tournament with no earlier international training data is skipped (no fold can be fit). Deterministic
    (ordered by cutoff kickoff)."""
    assert_no_2026(intl_rows)
    club_rows = list(club_rows or [])
    if club_rows:
        assert_no_2026(club_rows)
    firsts = _tournament_first_kickoff(intl_rows)
    folds: List[OuterFold] = []
    for tour, cutoff in sorted(firsts.items(), key=lambda kv: (kv[1], kv[0])):
        intl_train = [r for r in intl_rows
                      if (r.get("kickoff_date") or "") and (r.get("kickoff_date") < cutoff)]
        intl_test = [r for r in intl_rows
                     if (r.get("competition_label") or r.get("competition")) == tour]
        club_train = [r for r in club_rows
                      if (r.get("kickoff_date") or "") and (r.get("kickoff_date") < cutoff)]
        if not intl_train or not intl_test:
            continue  # cannot fit a fold with no earlier intl training data
        for r in intl_train:
            r.setdefault("domain", DOMAIN_INTERNATIONAL)
        for r in intl_test:
            r.setdefault("domain", DOMAIN_INTERNATIONAL)
        for r in club_train:
            r["domain"] = DOMAIN_CLUB
        folds.append(OuterFold(held_tournament=tour, cutoff_kickoff=cutoff,
                               intl_train_rows=intl_train, club_train_rows=club_train,
                               intl_test_rows=intl_test))
    return folds


# =================================================================================================
# ROW ASSEMBLY -- materialize the transfer rows for a fold. Each emitted row carries the domain,
# competition, season, match-id, time, baseline-intensity, residual-target, the stable-feature subset
# values, source-quality, overlap-score, availability, fold-marker, eligibility. Baselines + filter are
# fit on the fold's TRAINING rows; the eligibility row-set distinguishes train vs test.
# =================================================================================================
def _domain_overlap_score(filt: StableFeatureFilter) -> float:
    """A simple, auditable domain-overlap score in [0,1]: fraction of candidate transfer features that
    survive the stable-feature gate (higher == the two domains share more usable signal)."""
    n_cand = len([c for c in CANDIDATE_TRANSFER_FEATURE_COLS
                  if c not in ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS])
    return round(len(filt.kept) / n_cand, 6) if n_cand else 0.0


def _availability_label(row: dict, kept: Sequence[str]) -> str:
    """Per-row availability over the kept stable-feature subset: verified (all present), partial (some),
    unavailable (none)."""
    if not kept:
        return "unavailable"
    present = sum(1 for c in kept if fnum(row, c) is not None)
    if present == len(kept):
        return "available_verified"
    if present == 0:
        return "unavailable"
    return "available_partial"


def assemble_fold_rows(fold: OuterFold,
                       baseline: DomainBaseline,
                       filt: StableFeatureFilter) -> List[dict]:
    """Produce the per-snapshot transfer rows for a fold (train rows from both domains + held-out intl
    test rows). The domain baseline + stable-feature filter MUST already be fit on ``fold.train_rows``.
    Each row carries the required Phase-3 fields; targets/residuals are separate keys (never features)."""
    overlap = _domain_overlap_score(filt)
    rows_out: List[dict] = []

    def _emit(src: dict, eligibility_set: str):
        dom = src.get("domain") or DOMAIN_INTERNATIONAL
        st = derive_state(src)
        res = residual_targets(src, baseline, dom)
        ref_int = T0.reference_intensity(src)
        ref_wdl = T0.reference_wdl(src)
        row: dict = {
            "dataset_version": DATASET_VERSION,
            "reference_model": REFERENCE_MODEL,
            "fold_held_tournament": fold.held_tournament,
            "fold_cutoff_kickoff": fold.cutoff_kickoff,
            "row_role": eligibility_set,                      # intl_train | club_train | intl_test
            "domain": dom,
            "competition_label": src.get("competition_label") or src.get("competition"),
            "season": src.get("season") or src.get("season_id") or src.get("competition_label")
            or src.get("competition"),
            "match_id": src.get("match_id") or src.get("source_match_id"),
            "source_match_id": src.get("source_match_id") or src.get("match_id"),
            "kickoff_date": src.get("kickoff_date"),
            "snapshot_minute": fnum(src, "snapshot_minute"),
            "snapshot_reason": src.get("snapshot_reason"),
            "remaining_regulation_min": fnum(src, "remaining_regulation_min"),
            "n_events_observed": fnum(src, "n_events_observed"),
            # T0 reference (domain-agnostic anchor)
            "t0_lam_home": round(ref_int["t0_lam_home"], 6),
            "t0_lam_away": round(ref_int["t0_lam_away"], 6),
            "t0_lam_total": round(ref_int["t0_lam_total"], 6),
            "t0_prob_H": round(ref_wdl["t0_prob_H"], 6),
            "t0_prob_D": round(ref_wdl["t0_prob_D"], 6),
            "t0_prob_A": round(ref_wdl["t0_prob_A"], 6),
            # domain baseline + residual transfer target
            "domain_baseline_home": res["domain_baseline_home"],
            "domain_baseline_away": res["domain_baseline_away"],
            "domain_baseline_total": res["domain_baseline_total"],
            "transfer_residual_home": res["transfer_residual_home"],
            "transfer_residual_away": res["transfer_residual_away"],
            "transfer_residual_total": res["transfer_residual_total"],
            # observed remaining-goal LABELS (never used as a feature; kept for fitting/eval traceability)
            "rem_goals_home": fnum(src, "rem_goals_home"),
            "rem_goals_away": fnum(src, "rem_goals_away"),
            "target_wdl": src.get("target_wdl"),
            # provenance / quality / overlap / availability
            "xg_present": src.get("xg_present"),
            "source_root": src.get("source_root"),
            "source_sha256": src.get("source_sha256"),
            "engine_version": src.get("engine_version"),
            "stable_feature_subset_size": filt.subset_size(),
            "domain_overlap_score": overlap,
            "availability": _availability_label(src, filt.kept),
            "eligibility": "/".join(ELIGIBILITY_LABELS),
        }
        # derived domain-comparable state columns
        for k, v in st.items():
            row[f"state_{k}"] = round(v, 6) if isinstance(v, float) else v
        # the kept stable-feature subset values (preserve missingness as empty)
        for c in filt.kept:
            v = fnum(src, c)
            row[f"feat_{c}"] = v
        return row

    for r in fold.intl_train_rows:
        rows_out.append(_emit(r, "intl_train"))
    for r in fold.club_train_rows:
        rows_out.append(_emit(r, "club_train"))
    for r in fold.intl_test_rows:
        rows_out.append(_emit(r, "intl_test"))
    return rows_out


def build_all_fold_rows(intl_rows: Sequence[dict],
                        club_rows: Optional[Sequence[dict]] = None,
                        min_present_frac: float = 0.5,
                        max_smd: float = 1.0) -> Dict[str, object]:
    """End-to-end (in-memory): build outer folds, fit per-fold domain baselines + stable-feature filter
    on TRAIN rows only, and assemble every transfer row. Returns {'rows', 'folds', 'summary'}.

    The fit-on-train-only invariant is structural: ``fit_domain_baseline`` and
    ``fit_stable_feature_filter`` are called with ``fold.train_rows`` (intl-train + club-train) and the
    held-out test rows are passed only to ``assemble_fold_rows`` for APPLICATION (never to a fit)."""
    folds = outer_temporal_folds(intl_rows, club_rows)
    if not folds:
        raise DataInsufficient("no outer temporal folds could be built (need >=1 tournament with "
                               "earlier international training data)")
    all_rows: List[dict] = []
    fold_summ: List[dict] = []
    for fold in folds:
        T0.annotate(fold.intl_train_rows)
        T0.annotate(fold.club_train_rows)
        T0.annotate(fold.intl_test_rows)
        baseline = fit_domain_baseline(fold.train_rows)          # TRAIN ONLY
        filt = fit_stable_feature_filter(fold.train_rows,         # TRAIN ONLY
                                         min_present_frac=min_present_frac, max_smd=max_smd)
        rows = assemble_fold_rows(fold, baseline, filt)
        all_rows.extend(rows)
        fold_summ.append({
            "held_tournament": fold.held_tournament,
            "cutoff_kickoff": fold.cutoff_kickoff,
            "n_intl_train_rows": len(fold.intl_train_rows),
            "n_club_train_rows": len(fold.club_train_rows),
            "n_intl_test_rows": len(fold.intl_test_rows),
            "n_intl_test_matches": fold.n_intl_test_matches(),
            "n_club_train_matches": fold.n_club_train_matches(),
            "stable_feature_subset_size": filt.subset_size(),
            "stable_feature_subset": list(filt.kept),
            "domain_overlap_score": _domain_overlap_score(filt),
            "domain_log_intercepts": dict(baseline.log_intercept),
            "single_domain_train": filt.single_domain,
        })
    n_intl_test_matches = len({r["match_id"] for r in all_rows if r["row_role"] == "intl_test"})
    n_club_train_matches = len({r["match_id"] for r in all_rows if r["row_role"] == "club_train"})
    subset_sizes = sorted({fs["stable_feature_subset_size"] for fs in fold_summ})
    summary = {
        "dataset_version": DATASET_VERSION,
        "n_folds": len(folds),
        "n_rows_total": len(all_rows),
        "n_intl_test_matches": n_intl_test_matches,
        "n_club_train_matches": n_club_train_matches,
        "stable_feature_subset_sizes_by_fold": subset_sizes,
        "reference_model": REFERENCE_MODEL,
        "folds": fold_summ,
        "eligibility": "/".join(ELIGIBILITY_LABELS),
    }
    return {"rows": all_rows, "folds": folds, "summary": summary}


# =================================================================================================
# Deterministic SYNTHETIC generator (no files) -- shaped like the real lake-derived snapshot rows so the
# self-tests exercise the WHOLE pipeline (folds + baseline + filter + residual) without disk/network.
# Two international "tournaments" (temporally separated) + one club "season"; includes rows with MISSING
# xG so the availability/stable-feature gates see real missingness. Targets present; never features.
# =================================================================================================
def synthetic_intl_rows(n_per_tour: int = 6) -> List[dict]:
    rows: List[dict] = []
    tours = [("SynthCup2018", "2018", "2018-06-14"), ("SynthCup2022", "2022", "2022-11-20")]
    mid = 0
    for tour, season, base_ko in tours:
        for m in range(n_per_tour):
            mid += 1
            reg_h = (mid * 2) % 4
            reg_a = (mid * 3) % 3
            tgt = "H" if reg_h > reg_a else ("A" if reg_a > reg_h else "D")
            has_xg = (m % 3 != 0)
            ko_day = 14 + m
            for t in (20.0, 45.0, 70.0):
                cur_h = int(round(reg_h * (t / 90.0)))
                cur_a = int(round(reg_a * (t / 90.0)))
                row: dict = {
                    "source_match_id": f"I{mid:03d}", "match_id": f"I{mid:03d}",
                    "competition_label": tour, "competition": tour, "season": season,
                    "comp_type": "international", "domain": DOMAIN_INTERNATIONAL,
                    "kickoff_date": f"{base_ko[:5]}{ko_day:02d}" if False else
                    (base_ko[:8] + f"{ko_day:02d}"),
                    "snapshot_minute": t, "snapshot_reason": "clock",
                    "remaining_regulation_min": 90.0 - t, "period": 1 if t < 45 else 2,
                    "goals_home": cur_h, "goals_away": cur_a, "goals_diff": cur_h - cur_a,
                    "players_home": 11, "players_away": 11, "players_diff": 0,
                    "yellow_diff": (mid % 3) - 1, "sendoff_diff": 0, "subs_used_diff": (mid % 4) - 2,
                    "poss_share_diff": -0.1 + 0.02 * m, "field_tilt_home": 0.45 + 0.01 * m,
                    "final_third_actions_diff": (mid % 11) - 5,
                    "box_entries_diff": (mid % 7) - 3, "recoveries_diff": (mid % 9) - 4,
                    "turnovers_diff": (mid % 9) - 4, "corners_diff": (mid % 5) - 2,
                    "att_free_kicks_diff": (mid % 6) - 2, "shots_diff": (mid % 7) - 3,
                    "shots_on_target_diff": (mid % 5) - 2,
                    "n_events_observed": 400 + mid,
                    "source_root": "lake_object", "source_sha256": f"sha_intl_{mid:03d}",
                    "engine_version": "event_process_snapshot_features_synth",
                    "rem_goals_home": float(max(0, reg_h - cur_h)),
                    "rem_goals_away": float(max(0, reg_a - cur_a)),
                    "target_wdl": tgt,
                }
                if has_xg:
                    row["xg_present"] = "True"
                    row["cum_xg_diff"] = 0.2 * (cur_h - cur_a)
                    row["cum_xg_total"] = 0.3 * (cur_h + cur_a) + 0.4
                    row["xg_last5m_diff"] = 0.05 * ((mid % 5) - 2)
                    row["xg_last10m_diff"] = 0.08 * ((mid % 7) - 3)
                else:
                    row["xg_present"] = "False"
                rows.append(row)
    return rows


def synthetic_club_rows(n_matches: int = 8) -> List[dict]:
    rows: List[dict] = []
    for m in range(n_matches):
        mid = m + 1
        reg_h = (mid * 5) % 5
        reg_a = (mid * 2) % 4
        has_xg = (m % 4 != 0)
        for t in (20.0, 45.0, 70.0):
            cur_h = int(round(reg_h * (t / 90.0)))
            cur_a = int(round(reg_a * (t / 90.0)))
            row: dict = {
                "source_match_id": f"C{mid:03d}", "match_id": f"C{mid:03d}",
                "competition_label": "SynthLeague", "competition": "SynthLeague",
                "season": "2016/2017", "comp_type": "club", "domain": DOMAIN_CLUB,
                "kickoff_date": f"2016-08-{10 + m:02d}",   # before both synthetic tournaments
                "snapshot_minute": t, "snapshot_reason": "clock",
                "remaining_regulation_min": 90.0 - t, "period": 1 if t < 45 else 2,
                "goals_home": cur_h, "goals_away": cur_a, "goals_diff": cur_h - cur_a,
                "players_home": 11, "players_away": 11, "players_diff": 0,
                "yellow_diff": (mid % 3) - 1, "sendoff_diff": 0, "subs_used_diff": (mid % 4) - 2,
                "poss_share_diff": 0.0 + 0.01 * m, "field_tilt_home": 0.5 + 0.005 * m,
                "final_third_actions_diff": (mid % 11) - 5, "box_entries_diff": (mid % 7) - 3,
                "recoveries_diff": (mid % 9) - 4, "turnovers_diff": (mid % 9) - 4,
                "corners_diff": (mid % 5) - 2, "att_free_kicks_diff": (mid % 6) - 2,
                "shots_diff": (mid % 7) - 3, "shots_on_target_diff": (mid % 5) - 2,
                "n_events_observed": 500 + mid,
                "source_root": "club_aux_object", "source_sha256": f"sha_club_{mid:03d}",
                "engine_version": "event_process_snapshot_features_synth",
                "rem_goals_home": float(max(0, reg_h - cur_h)),
                "rem_goals_away": float(max(0, reg_a - cur_a)),
                "target_wdl": "H" if reg_h > reg_a else ("A" if reg_a > reg_h else "D"),
            }
            if has_xg:
                row["xg_present"] = "True"
                row["cum_xg_diff"] = 0.2 * (cur_h - cur_a)
                row["cum_xg_total"] = 0.3 * (cur_h + cur_a) + 0.4
                row["xg_last5m_diff"] = 0.05 * ((mid % 5) - 2)
                row["xg_last10m_diff"] = 0.08 * ((mid % 7) - 3)
            else:
                row["xg_present"] = "False"
            rows.append(row)
    return rows
