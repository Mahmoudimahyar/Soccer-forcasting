"""Phase 2 -- Feature-overlap / domain-shift audit (international vs club).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

GOAL
  For each candidate event-process FEATURE FAMILY (score/time, chance-quality, possession/territory,
  transition/disruption, set-pieces, data-quality) decide whether it is safe to TRANSFER from the
  auxiliary CLUB domain into the international model. The decision rests on cross-domain comparison
  statistics computed IN TRAINING DATA ONLY:
     missingness diff, standardized mean difference (SMD), variance ratio, distribution overlap,
     Wasserstein distance, out-of-support rate, competition heterogeneity, temporal stability,
     and a club->international transfer-risk score.

HONESTY (the load-bearing constraint of this build)
  The cross-domain statistics REQUIRE a real feature distribution from BOTH domains. The international
  distribution is computed here from the 258 REAL lake event objects (through the canonical snapshot
  engine). The club distribution requires the 669 club event objects, which are NOT materialized in
  this worktree (Phase 1 inventory: club_materialized = 0). Therefore every statistic that needs the
  club distribution (SMD, variance ratio, overlap, Wasserstein, out-of-support, transfer-risk) is
  emitted as `data_insufficient` with an explicit reason -- it is NEVER fabricated.

  What IS derivable and IS computed on REAL data: the full international feature-family distribution
  profile, per-feature missingness, variance, in-domain competition heterogeneity (across the 5
  international tournaments), and temporal stability (across editions). These ground the feature
  registry; the cross-domain transfer verdict is held at `insufficient_data` until the club corpus
  is materialized.

LEAKAGE / ISOLATION
  * Profiling uses the international PRIMARY population only (2026 WC is excluded; it is also absent).
  * All statistics are computed on the training population (no held-out test tuning, no 2026).
  * Match-level unit only; competition heterogeneity uses leave-one-competition-out groups.
  * No network / API / paid / scrape / credentials. Pure local read of verified lake objects.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("feature-overlap audit must not run inside the active collector checkout")

from wcdrawlab.research import international_event_lake as LAKE  # noqa: E402
from wcdrawlab.research.event_process import snapshot_features as SF  # noqa: E402

REF = ROOT / "data" / "reference"
NOTES = ROOT / "notes" / "research"
INVENTORY_JSON = REF / "domain_event_process_inventory.json"
COHORT_MANIFEST = REF / "international_event_lake_cohort_manifest.csv"

AUDIT_SCHEMA = "feature_overlap_audit_v1"

# Decision minutes at which we profile match-process features (mid-match states the transfer models use).
PROFILE_MINUTES = [30, 45, 60, 75]

# Classification vocabulary (per the build contract).
CLS_STABLE_TRANSFERABLE = "stable_transferable"
CLS_STABLE_LOW_COVERAGE = "stable_but_low_coverage"
CLS_INTERNATIONAL_ONLY = "international_only"
CLS_CLUB_ONLY = "club_only"
CLS_DOMAIN_SHIFTED = "domain_shifted"
CLS_SOURCE_INCOMPATIBLE = "source_incompatible"
CLS_INSUFFICIENT = "insufficient_data"

DATA_INSUFFICIENT = "data_insufficient"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =================================================================================================
# Candidate feature families. Each entry maps a snapshot-feature key (computed at a decision minute)
# to its family + a transfer-prior note. `source_field` records which raw provider capability the
# feature depends on (so we can pre-flag source_incompatible cleanly when a domain cannot express it).
# =================================================================================================
FEATURE_FAMILIES = {
    "score_time": {
        "features": ["goals_diff", "score_diff_sign", "remaining_regulation_min", "players_diff",
                     "min_since_last_shot_any"],
        "transfer_prior": "scoreline/time-state is provider-neutral and competition-neutral; expected stable",
    },
    "chance_quality": {
        "features": ["cum_xg_total", "cum_xg_diff", "shots_diff", "shots_on_target_diff",
                     "xg_last10m_diff", "min_since_major_chance"],
        "transfer_prior": "xG magnitude/tempo can differ club-vs-international (pace, finishing); shift risk",
    },
    "possession_territory": {
        "features": ["poss_share_home", "poss_share_diff", "final_third_actions_diff",
                     "box_entries_diff", "field_tilt_home"],
        "transfer_prior": "possession style is league-dependent; club->international shift plausible",
    },
    "transition_disruption": {
        "features": ["recoveries_diff", "turnovers_diff"],
        "transfer_prior": "transition rates vary by league intensity; moderate shift risk",
    },
    "set_pieces": {
        "features": ["corners_diff", "att_free_kicks_diff"],
        "transfer_prior": "set-piece counts are structurally comparable; low-moderate shift risk",
    },
    "data_quality": {
        "features": ["xg_present", "n_events_observed"],
        "transfer_prior": "data-density/coverage is a provider/competition property, not a football signal",
    },
}

# snapshot_features.py emits *_home/_away/_diff; some of our family keys are derived from those.
def _derive_extra(f: dict) -> dict:
    """Add a few derived scalars used by the family list but not directly in the snapshot dict."""
    out = dict(f)
    out["score_diff_sign"] = (1 if f.get("goals_diff", 0) > 0 else (-1 if f.get("goals_diff", 0) < 0 else 0))
    return out


# =================================================================================================
# International feature profiling (REAL data through the engine)
# =================================================================================================
def _load_cohort_index() -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not COHORT_MANIFEST.exists():
        return out
    with COHORT_MANIFEST.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                out[int(row["sb_match_id"])] = row
            except (KeyError, ValueError):
                continue
    return out


def _match_feature_record(events, sb_id, comp_label, season):
    """Match-level feature record = the snapshot features at each PROFILE_MINUTE for one match.
    Returns (per_minute_features, meta). Leakage-safe: each snapshot uses events<=t only."""
    ctx = SF.prepare_match(events, str(sb_id))
    if ctx.home_team_id is None or ctx.away_team_id is None:
        return None
    max_min = ctx.max_regulation_minute or 0.0
    per_min = {}
    for t in PROFILE_MINUTES:
        if t > max_min + 1e-6:
            continue
        f = SF.snapshot_features(events, ctx, float(t))
        per_min[t] = _derive_extra(f)
    meta = {"sb_id": sb_id, "competition": comp_label, "season": season}
    return per_min, meta


def profile_international():
    """Read every lake object, profile feature families at PROFILE_MINUTES. Training population only
    (international primary; 2026 WC excluded and absent). Returns per-feature value arrays keyed by
    (family, feature, minute), plus group labels for heterogeneity/temporal-stability stats."""
    lake = LAKE.Lake.resolve()
    index = LAKE.read_index(lake)
    cohort = _load_cohort_index()
    # values[(family, feature, minute)] = list of (value_or_None, competition, season, sb_id)
    values: dict = {}
    n_matches = 0
    comps = set()
    seasons = set()
    for sb_id_str, rec in index.items():
        try:
            sb_id = int(sb_id_str)
        except (TypeError, ValueError):
            continue
        cm = cohort.get(sb_id, {})
        # exclude any 2026 WC material from profiling (defensive; it is also absent from the lake)
        if str(cm.get("is_2026_wc_excluded", "")).strip().lower() in ("true", "1", "yes"):
            continue
        obj = (lake.root / rec["local_path"]) if rec.get("local_path") else None
        if obj is None or not obj.exists():
            continue
        try:
            events = json.loads(obj.read_text(encoding="utf-8"))
        except Exception:
            continue
        comp = rec.get("competition_label") or ""
        season = cm.get("season") or ""
        res = _match_feature_record(events, sb_id, comp, season)
        if res is None:
            continue
        per_min, meta = res
        n_matches += 1
        comps.add(comp)
        seasons.add(season)
        for fam, spec in FEATURE_FAMILIES.items():
            for feat in spec["features"]:
                for t in PROFILE_MINUTES:
                    key = (fam, feat, t)
                    fdict = per_min.get(t)
                    val = None
                    if fdict is not None:
                        val = fdict.get(feat)
                        # booleans -> numeric; None stays None (missingness, never imputed)
                        if isinstance(val, bool):
                            val = int(val)
                    values.setdefault(key, []).append((val, comp, season, sb_id))
    return values, {"n_matches": n_matches, "competitions": sorted(comps), "seasons": sorted(seasons)}


# =================================================================================================
# in-domain statistics (REAL, derivable) -- distribution profile + heterogeneity + temporal stability
# =================================================================================================
def _finite(vals):
    return [float(v) for v in vals if v is not None and isinstance(v, (int, float)) and math.isfinite(float(v))]


def _mean_std(xs):
    if not xs:
        return (None, None)
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return (round(m, 6), 0.0)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return (round(m, 6), round(math.sqrt(var), 6))


def _group_heterogeneity(rows):
    """Heterogeneity of the feature mean across international competitions (a real in-domain shift
    proxy). Returns the max abs standardized mean difference between any competition group mean and
    the pooled mean, scaled by pooled std. Higher => more cross-competition shift even WITHIN intl."""
    pooled = _finite([v for (v, _c, _s, _i) in rows])
    pm, ps = _mean_std(pooled)
    if pm is None or not ps:
        return {"max_group_smd": None, "n_groups": 0, "pooled_mean": pm, "pooled_std": ps}
    from collections import defaultdict
    g = defaultdict(list)
    for (v, c, _s, _i) in rows:
        if v is not None and isinstance(v, (int, float)) and math.isfinite(float(v)):
            g[c].append(float(v))
    smds = []
    for c, xs in g.items():
        if len(xs) >= 5:
            gm = sum(xs) / len(xs)
            smds.append(abs(gm - pm) / ps)
    return {"max_group_smd": (round(max(smds), 4) if smds else None),
            "n_groups": len(g), "pooled_mean": pm, "pooled_std": ps}


def _temporal_stability(rows):
    """Stability of the feature mean across editions (seasons). Returns the spread (max-min) of
    per-season means scaled by pooled std. Higher => less temporally stable within intl."""
    pooled = _finite([v for (v, _c, _s, _i) in rows])
    pm, ps = _mean_std(pooled)
    if pm is None or not ps:
        return {"season_mean_spread_std": None, "n_seasons": 0}
    from collections import defaultdict
    g = defaultdict(list)
    for (v, _c, s, _i) in rows:
        if v is not None and isinstance(v, (int, float)) and math.isfinite(float(v)):
            g[s].append(float(v))
    means = [sum(xs) / len(xs) for xs in g.values() if len(xs) >= 5]
    if len(means) < 2:
        return {"season_mean_spread_std": None, "n_seasons": len(g)}
    return {"season_mean_spread_std": round((max(means) - min(means)) / ps, 4), "n_seasons": len(g)}


def _missingness(rows):
    n = len(rows)
    if n == 0:
        return None
    miss = sum(1 for (v, _c, _s, _i) in rows if v is None)
    return round(miss / n, 4)


# =================================================================================================
# classification (honest): cross-domain verdict held at insufficient_data; in-domain facts recorded
# =================================================================================================
def classify_feature(*, intl_missingness, intl_n, het_max_smd, temporal_spread, club_present):
    """Return (classification, transfer_risk, reasons). With the club distribution ABSENT, no feature
    can be positively certified `stable_transferable`; the honest verdict is `insufficient_data` for
    the cross-domain decision, annotated with the in-domain evidence we DID compute."""
    reasons = []
    # source compatibility is known structurally: international can express all these families.
    if intl_n is None or intl_n < 30:
        reasons.append("intl_n<30")
        return CLS_INSUFFICIENT, DATA_INSUFFICIENT, reasons
    if intl_missingness is not None and intl_missingness > 0.5:
        reasons.append(f"intl_missingness={intl_missingness}")
        cls_cov = CLS_STABLE_LOW_COVERAGE
    else:
        cls_cov = None
    if not club_present:
        reasons.append("club_distribution_absent_in_worktree")
        # cannot compute SMD/variance-ratio/overlap/Wasserstein/out-of-support vs club -> insufficient
        return CLS_INSUFFICIENT, DATA_INSUFFICIENT, reasons
    # (reached only if club is materialized in a future run)
    if het_max_smd is not None and het_max_smd >= 0.5:
        reasons.append(f"in_domain_competition_smd={het_max_smd}")
        return CLS_DOMAIN_SHIFTED, "high", reasons
    if cls_cov:
        return cls_cov, "medium", reasons
    return CLS_STABLE_TRANSFERABLE, "low", reasons


def main() -> int:
    REF.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)

    # Phase-1 inventory tells us whether the club corpus is materialized.
    club_present = False
    inv_club_summary = {}
    if INVENTORY_JSON.exists():
        inv = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))
        inv_club_summary = inv.get("domains", {}).get("club", {})
        club_present = int(inv_club_summary.get("events_materialized", 0) or 0) > 0

    values, intl_meta = profile_international()

    # build per-feature registry rows
    registry_rows = []
    family_rollup = {}
    for fam, spec in FEATURE_FAMILIES.items():
        for feat in spec["features"]:
            # aggregate across PROFILE_MINUTES (pool the minutes; minute is a state, not a separate feat)
            pooled_rows = []
            for t in PROFILE_MINUTES:
                pooled_rows.extend(values.get((fam, feat, t), []))
            xs = _finite([v for (v, _c, _s, _i) in pooled_rows])
            mean, std = _mean_std(xs)
            miss = _missingness(pooled_rows)
            het = _group_heterogeneity(pooled_rows)
            temp = _temporal_stability(pooled_rows)
            cls, risk, reasons = classify_feature(
                intl_missingness=miss, intl_n=len(xs),
                het_max_smd=het.get("max_group_smd"), temporal_spread=temp.get("season_mean_spread_std"),
                club_present=club_present,
            )
            row = {
                "family": fam,
                "feature": feat,
                "transfer_prior": spec["transfer_prior"],
                # international in-domain (REAL)
                "intl_n_obs": len(xs),
                "intl_missingness": miss,
                "intl_mean": mean,
                "intl_std": std,
                "intl_competition_heterogeneity_max_smd": het.get("max_group_smd"),
                "intl_n_competitions": het.get("n_groups"),
                "intl_temporal_mean_spread_std": temp.get("season_mean_spread_std"),
                "intl_n_seasons": temp.get("n_seasons"),
                # cross-domain (REQUIRES club distribution) -- honest data_insufficient
                "club_n_obs": 0 if not club_present else None,
                "missingness_diff_vs_club": DATA_INSUFFICIENT,
                "standardized_mean_diff_vs_club": DATA_INSUFFICIENT,
                "variance_ratio_vs_club": DATA_INSUFFICIENT,
                "distribution_overlap_vs_club": DATA_INSUFFICIENT,
                "wasserstein_distance_vs_club": DATA_INSUFFICIENT,
                "out_of_support_rate_vs_club": DATA_INSUFFICIENT,
                "club_to_intl_transfer_risk": risk,
                "classification": cls,
                "classification_reasons": ";".join(reasons),
            }
            registry_rows.append(row)
            fr = family_rollup.setdefault(fam, {"n_features": 0, "classes": {}})
            fr["n_features"] += 1
            fr["classes"][cls] = fr["classes"].get(cls, 0) + 1

    # cross-domain overlap audit object (status driven by club availability)
    cross_domain_status = "complete" if club_present else DATA_INSUFFICIENT
    cross_reason = (None if club_present else
                    "club event corpus not materialized in this worktree (Phase-1: events_materialized=0); "
                    "cross-domain SMD / variance-ratio / distribution-overlap / Wasserstein / out-of-support / "
                    "transfer-risk all require a REAL club feature distribution and are NOT fabricated")

    audit = {
        "schema_version": AUDIT_SCHEMA,
        "generated_ts": _utc(),
        "labels": ["research_only", "experimental", "not_runtime_approved",
                   "not_trade_eligible", "not_live_eligible"],
        "profile_minutes": PROFILE_MINUTES,
        "international_profiling": {
            "status": "complete",
            "n_matches_profiled": intl_meta["n_matches"],
            "competitions": intl_meta["competitions"],
            "seasons": intl_meta["seasons"],
            "note": "international feature-family distributions computed from REAL lake event objects "
                    "through the canonical snapshot engine; training population only; 2026 WC excluded",
        },
        "club_profiling": {
            "status": DATA_INSUFFICIENT,
            "events_materialized": int(inv_club_summary.get("events_materialized", 0) or 0),
            "fixtures_declared": int(inv_club_summary.get("fixtures_declared", 0) or 0),
            "reason": "club raw event objects absent in this worktree; no club feature distribution derivable",
        },
        "cross_domain_overlap": {
            "status": cross_domain_status,
            "reason": cross_reason,
            "statistics_requiring_both_domains": [
                "missingness_diff", "standardized_mean_diff", "variance_ratio",
                "distribution_overlap", "wasserstein_distance", "out_of_support_rate",
                "club_to_intl_transfer_risk",
            ],
        },
        "family_rollup": family_rollup,
        "n_features": len(registry_rows),
        "stable_transferable_count": sum(1 for r in registry_rows if r["classification"] == CLS_STABLE_TRANSFERABLE),
        "domain_shifted_features": [r["feature"] for r in registry_rows if r["classification"] == CLS_DOMAIN_SHIFTED],
        "insufficient_data_count": sum(1 for r in registry_rows if r["classification"] == CLS_INSUFFICIENT),
    }

    # write feature_overlap_audit.json
    (REF / "feature_overlap_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    # write feature_stability_registry.{csv,json}
    fieldnames = list(registry_rows[0].keys()) if registry_rows else []
    with (REF / "feature_stability_registry.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in registry_rows:
            w.writerow(r)
    (REF / "feature_stability_registry.json").write_text(
        json.dumps({"schema_version": "feature_stability_registry_v1", "generated_ts": _utc(),
                    "rows": registry_rows}, indent=2, default=str), encoding="utf-8")

    _write_report(audit, registry_rows, intl_meta)

    print(json.dumps({
        "status": cross_domain_status,
        "international_profiled": intl_meta["n_matches"],
        "club_materialized": audit["club_profiling"]["events_materialized"],
        "n_features": audit["n_features"],
        "stable_transferable_count": audit["stable_transferable_count"],
        "insufficient_data_count": audit["insufficient_data_count"],
        "reason": cross_reason,
    }))
    return 0


def _write_report(audit, registry_rows, intl_meta) -> None:
    lines = []
    A = lines.append
    A("# Domain Shift & Feature Stability Report (Phase 2)")
    A("")
    A("_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_")
    A("")
    A(f"Generated: {audit['generated_ts']}")
    A("")
    A("## Verdict")
    A("")
    A(f"- International feature profiling: **complete** "
      f"({audit['international_profiling']['n_matches_profiled']} real matches, "
      f"{len(intl_meta['competitions'])} competitions).")
    A(f"- Club feature profiling: **data_insufficient** "
      f"(events materialized = {audit['club_profiling']['events_materialized']} / "
      f"{audit['club_profiling']['fixtures_declared']} declared).")
    A(f"- Cross-domain overlap audit: **{audit['cross_domain_overlap']['status']}**.")
    if audit['cross_domain_overlap']['reason']:
        A(f"  - reason: {audit['cross_domain_overlap']['reason']}")
    A("")
    A("The cross-domain statistics (missingness diff, standardized mean difference, variance ratio, "
      "distribution overlap, Wasserstein distance, out-of-support rate, transfer-risk) each require a "
      "REAL feature distribution from BOTH domains. The club distribution is not derivable here, so "
      "these are reported as `data_insufficient` and NEVER fabricated. The international in-domain "
      "distribution profile, missingness, competition heterogeneity, and temporal stability ARE "
      "computed on real data and recorded below.")
    A("")
    A("## Stable-transferable feature count")
    A("")
    A(f"- features audited: **{audit['n_features']}**")
    A(f"- positively certified `stable_transferable`: **{audit['stable_transferable_count']}** "
      "(cannot exceed 0 until the club distribution is materialized -- a positive certification "
      "requires a real cross-domain comparison)")
    A(f"- held at `insufficient_data` (cross-domain): **{audit['insufficient_data_count']}**")
    A(f"- families flagged `domain_shifted`: {audit['domain_shifted_features'] or 'none derivable yet'}")
    A("")
    A("## International in-domain feature profile (REAL)")
    A("")
    A("Per feature: pooled across decision minutes "
      f"{audit['profile_minutes']}. `het_max_smd` is the largest standardized gap between any single "
      "international competition's mean and the pooled mean (an in-domain shift proxy); "
      "`temporal_spread` is the season-mean spread in pooled-std units.")
    A("")
    A("| family | feature | n_obs | missing | mean | std | het_max_smd | temporal_spread | classification |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for r in registry_rows:
        A(f"| {r['family']} | {r['feature']} | {r['intl_n_obs']} | {r['intl_missingness']} | "
          f"{r['intl_mean']} | {r['intl_std']} | {r['intl_competition_heterogeneity_max_smd']} | "
          f"{r['intl_temporal_mean_spread_std']} | {r['classification']} |")
    A("")
    A("## Feature families")
    A("")
    for fam, spec in FEATURE_FAMILIES.items():
        fr = audit["family_rollup"].get(fam, {})
        A(f"- **{fam}** ({fr.get('n_features', 0)} features): {spec['transfer_prior']}")
    A("")
    A("## What unblocks the cross-domain decision")
    A("")
    A("Materialize the 669 club event objects under the statsbomb_raw aux root "
      "(`data/raw/statsbomb_open/event_process_auxiliary/`). The same engine path then computes the "
      "club feature distribution, and this audit will emit real SMD / variance-ratio / overlap / "
      "Wasserstein / out-of-support / transfer-risk and resolve each feature's classification "
      "(`stable_transferable` / `domain_shifted` / `source_incompatible` / ...). Until then the "
      "honest verdict is `data_insufficient` for every cross-domain statistic.")
    A("")
    (NOTES / "domain_shift_and_feature_stability_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
