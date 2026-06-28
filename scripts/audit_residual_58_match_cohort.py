"""Independent reconstruction + recomputation audit of the residual goal-intensity 58-match cohort.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

WHY THIS EXISTS
---------------
The residual goal-intensity W/D/L evaluation (rg_20260627_155623_run1) reports a 58-MATCH /
7376-snapshot international cohort across 5 tournaments (WC2018, Euro2020, WC2022, Copa2024,
Euro2024) and a pooled forward-chain reference RPS of 0.15263 for the parameter-free W2
remaining-time Poisson reference (research.residual.w2_reference_r0). This program audits, from
RAW manifests + already-validated local artifacts ONLY (no network, no provider, no scrape):

  1. the COUNT FUNNEL: bridge 258 (exact international) -> matches with cached StatsBomb events on
     disk -> residual-target-eligible -> per forward-chain fold + per LOCO fold, with the exact
     count-loss at every stage GROUPED BY REASON;
  2. an INDEPENDENT recomputation of the pooled W/D/L forward-chain RPS for the R0 reference,
     reimplementing the W2 remaining-time Poisson -> exact convolution -> RPS from scratch (NOT by
     importing the residual_intensity package), then COMPARING to the reported 0.15263.

It is read-only over source repos: the residual run lives in worldcup-residual-goal-intensity and
the exact bridge in worldcup-player-impact-xg; derived outputs are written under THIS workspace's
data/reference/. The active collector checkout (worldcup_draw_model_lab_FINAL) is never touched.

INDEPENDENCE NOTE
-----------------
R0 is parameter-free (no training): its per-row WDL probabilities depend only on the current
regulation score difference and the remaining-time-scaled league base rate (1.35 goals/team/90').
We therefore reconstruct it exactly from the snapshot CSV columns (goals_home, goals_away,
snapshot_minute/remaining_regulation_min) without invoking any project model code. This is the
"independent recompute": if our number matches the reported pooled RPS, the reported metric is
reproducible.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# -------------------------------------------------------------------------------------------------
# canonical roots (read-only source repos) + this workspace's output dir
# -------------------------------------------------------------------------------------------------
THIS_ROOT = Path("C:/Users/Mahyar/worldcup-evidence-power-consolidation")
RG_ROOT = Path("C:/Users/Mahyar/worldcup-residual-goal-intensity")
PIX_ROOT = Path("C:/Users/Mahyar/worldcup-player-impact-xg")

BRIDGE_CSV = PIX_ROOT / "data/processed/api_statsbomb_match_bridge_v1.csv"
BRIDGE_AUDIT = PIX_ROOT / "data/processed/api_statsbomb_match_bridge_v1.audit.json"
# StatsBomb event JSON caches the snapshot builder actually reads from (statsbomb_raw, then prior):
SB_EVENT_DIRS = [
    RG_ROOT / "data/raw/statsbomb_open/events",          # canonical (may be empty)
    PIX_ROOT / "data/raw/statsbomb_open/events",         # read-only prior 60-file pull
]

EP_DIR = RG_ROOT / "data/processed/event_process_snapshots"
SNAP_CSV = EP_DIR / "intl_event_process_snapshots.csv"
WDL_CSV = EP_DIR / "intl_targets_wdl.csv"
COMPLETENESS_CSV = EP_DIR / "match_completeness.csv"
EP_MANIFEST = EP_DIR / "build_manifest.json"

RES_BUILD_MANIFEST = RG_ROOT / "data/processed/residual_goal_intensity/build_manifest.json"
RUN_DIR = RG_ROOT / "outputs/research_runs/rg_20260627_155623_run1/residual_goal_intensity"
REPORTED_FC = RUN_DIR / "rg_wdl_forward_chain.json"
REPORTED_LOCO = RUN_DIR / "rg_wdl_loco.json"
REPORTED_DATASET = RUN_DIR / "rg_dataset_manifest.json"

OUT_JSON = THIS_ROOT / "data/reference/residual_58_match_audit.json"
OUT_COHORT_CSV = THIS_ROOT / "data/reference/residual_58_match_cohort.csv"

W2_BASE_RATE_PER90 = 1.35   # DM.R2_BASE -- the parameter-free league base rate used by R0
KMAX = 10                   # simulation.analytic_wdl passes kmax=10 to the convolution
WDL = ["H", "D", "A"]
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"


# =================================================================================================
# tiny IO helpers
# =================================================================================================
def _read_csv(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fnum(row, col):
    """Float of a CSV cell or None (never coerce missing -> 0)."""
    if col not in row:
        return None
    v = row.get(col)
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("none", "nan", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# =================================================================================================
# R0 reference -- reimplemented from scratch (independent of the residual_intensity package)
# =================================================================================================
def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def _norm3(pH, pD, pA):
    s = pH + pD + pA
    if s <= 0:
        return {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
    return {"H": pH / s, "D": pD / s, "A": pA / s}


def r0_wdl_from_row(row) -> "dict":
    """W2 reference WDL for one snapshot row, reconstructed ONLY from raw CSV columns.

    remaining fraction = clamp((90 - minute)/90, 0, 1); lam_home = lam_away = 1.35 * fraction;
    current_diff = round(goals_home - goals_away); exact independent-Poisson convolution to {H,D,A}.
    """
    rem = _fnum(row, "remaining_regulation_min")
    if rem is None:
        mn = _fnum(row, "snapshot_minute")
        rem = (90.0 - mn) if mn is not None else 90.0
    frac = max(0.0, min(1.0, rem / 90.0))
    lam = W2_BASE_RATE_PER90 * frac

    gd = _fnum(row, "goals_diff")
    if gd is None:
        gh, ga = _fnum(row, "goals_home"), _fnum(row, "goals_away")
        gd = (gh - ga) if (gh is not None and ga is not None) else 0.0
    cur = int(round(gd))

    pmf = [_poisson_pmf(k, lam) for k in range(KMAX + 1)]
    pH = pD = pA = 0.0
    for fh in range(KMAX + 1):
        for fa in range(KMAX + 1):
            p = pmf[fh] * pmf[fa]
            d = cur + fh - fa
            if d > 0:
                pH += p
            elif d == 0:
                pD += p
            else:
                pA += p
    return _norm3(pH, pD, pA)


def rps_wdl(p, y) -> float:
    cum_p = cum_o = s = 0.0
    for k in WDL:
        cum_p += float(p.get(k, 0.0))
        cum_o += 1.0 if k == y else 0.0
        s += (cum_p - cum_o) ** 2
    return s / (len(WDL) - 1)


def logloss_wdl(p, y, eps=1e-12) -> float:
    return -math.log(max(eps, float(p.get(y, 0.0))))


def brier_draw(p, y) -> float:
    return (float(p.get("D", 0.0)) - (1.0 if y == "D" else 0.0)) ** 2


# =================================================================================================
# STAGE 1 -- the count funnel: bridge 258 -> cached events -> residual eligible
# =================================================================================================
def build_funnel():
    funnel = {"stages": [], "by_competition": {}, "loss_by_reason": {}}

    bridge = _read_csv(BRIDGE_CSV)
    if bridge is None:
        return None, "bridge csv absent"
    exact_intl = [r for r in bridge
                  if r.get("bridge_confidence") == "exact" and r.get("comp_type") == "international"]
    comp_of = {r["sb_match_id"]: r.get("competition_label") for r in exact_intl}
    bridge_comp_counts = Counter(r.get("competition_label") for r in exact_intl)

    # which exact-bridge matches have a cached event JSON on disk (the builder's _find_intl_event_file)
    cached_ids, no_event_ids = [], []
    for r in exact_intl:
        sb = r["sb_match_id"]
        hit = any((d / f"{sb}.json").exists() for d in SB_EVENT_DIRS)
        (cached_ids if hit else no_event_ids).append(sb)
    cached_comp_counts = Counter(comp_of[i] for i in cached_ids)

    # residual-eligible = matches that actually produced snapshots + a W/D/L target (read the
    # already-built tables, independent of the builder run).
    snap_rows = _read_csv(SNAP_CSV) or []
    wdl_rows = _read_csv(WDL_CSV) or []
    snap_match_ids = sorted({r["source_match_id"] for r in snap_rows})
    wdl_match_ids = sorted({r["source_match_id"] for r in wdl_rows})
    eligible_ids = sorted(set(snap_match_ids) & set(wdl_match_ids))
    snap_comp_counts = Counter(r["competition_label"] for r in snap_rows
                               if r["source_match_id"] in set(eligible_ids))
    # de-dupe by match for per-competition match counts:
    elig_comp = {}
    for r in snap_rows:
        if r["source_match_id"] in set(eligible_ids):
            elig_comp[r["source_match_id"]] = r["competition_label"]
    eligible_comp_counts = Counter(elig_comp.values())

    funnel["stages"] = [
        {"stage": "exact_international_bridge", "n_matches": len(exact_intl),
         "by_competition": dict(bridge_comp_counts)},
        {"stage": "statsbomb_events_cached_on_disk", "n_matches": len(cached_ids),
         "by_competition": dict(cached_comp_counts)},
        {"stage": "residual_target_eligible_snapshots", "n_matches": len(eligible_ids),
         "n_snapshots": len([r for r in snap_rows if r["source_match_id"] in set(eligible_ids)]),
         "by_competition": dict(eligible_comp_counts)},
    ]
    funnel["loss_by_reason"] = {
        "bridge_exact_to_cached": {
            "n_lost": len(exact_intl) - len(cached_ids),
            "reason": "no StatsBomb event JSON present in any local cache "
                      "(statsbomb_raw/events or prior pull); builder counts as n_matches_no_events_present",
            "by_competition": {c: bridge_comp_counts[c] - cached_comp_counts.get(c, 0)
                               for c in bridge_comp_counts},
        },
        "cached_to_eligible": {
            "n_lost": len(cached_ids) - len(eligible_ids),
            "reason": "cached event file present but not in exact-intl bridge population "
                      "(home/away unresolved or rejected by bridge) -> no snapshot/target row",
            "cached_not_eligible_ids": sorted(set(cached_ids) - set(eligible_ids)),
        },
    }
    funnel["by_competition"] = {
        "bridge_exact": dict(bridge_comp_counts),
        "cached": dict(cached_comp_counts),
        "eligible": dict(eligible_comp_counts),
    }
    funnel["_eligible_ids"] = eligible_ids
    funnel["_no_event_ids"] = no_event_ids
    funnel["_comp_of"] = comp_of
    return funnel, None


# =================================================================================================
# STAGE 2 -- independent forward-chain + LOCO RPS recompute for R0
# =================================================================================================
def forward_chain_order(snap_rows):
    """Competitions ordered by earliest kickoff (forward-chaining order)."""
    first = {}
    for r in snap_rows:
        c = r.get("competition_label")
        k = r.get("kickoff_date") or ""
        if c is None:
            continue
        if c not in first or (k and k < first[c]):
            first[c] = k
    return [c for c, _ in sorted(first.items(), key=lambda kv: (kv[1] or "~", kv[0]))]


def attach_targets(snap_rows, wdl_rows):
    """Join each snapshot to its match-level W/D/L target (per-match target broadcast to all rows)."""
    tgt = {r["source_match_id"]: r.get("target_wdl") for r in wdl_rows}
    out = []
    for r in snap_rows:
        y = tgt.get(r["source_match_id"])
        if y in WDL:
            rr = dict(r)
            rr["target_wdl"] = y
            out.append(rr)
    return out


def recompute_forward_chain(rows):
    """Independent R0 forward-chain: competition c_k tested only when an EARLIER competition exists
    (N comps -> N-1 scorable folds). R0 is train-free so 'fit' is a no-op; we score every test row.
    Pooled RPS = mean over all test rows (matches the reported pooling: averaged over snapshot rows)."""
    order = forward_chain_order(rows)
    pooled = {"rps": 0.0, "ll": 0.0, "bd": 0.0, "n": 0}
    folds = []
    n_folds = 0
    for i in range(1, len(order)):
        held = order[i]
        train = [r for r in rows if r.get("competition_label") in set(order[:i])]
        test = [r for r in rows if r.get("competition_label") == held]
        if not train or not test:
            continue
        n_folds += 1
        frps = fll = 0.0
        cnt = 0
        for r in test:
            y = r["target_wdl"]
            p = r0_wdl_from_row(r)
            rp = rps_wdl(p, y)
            ll = logloss_wdl(p, y)
            pooled["rps"] += rp; pooled["ll"] += ll
            pooled["bd"] += brier_draw(p, y); pooled["n"] += 1
            frps += rp; fll += ll; cnt += 1
        folds.append({"competition": held, "n_train": len(train), "n_test": len(test),
                      "r0_rps": round(frps / cnt, 5), "r0_logloss": round(fll / cnt, 5)})
    pooled_out = {"rps": round(pooled["rps"] / pooled["n"], 5),
                  "logloss": round(pooled["ll"] / pooled["n"], 5),
                  "draw_brier": round(pooled["bd"] / pooled["n"], 5),
                  "n_test_rows": pooled["n"]}
    return {"competition_order": order, "n_folds": n_folds, "pooled": pooled_out, "folds": folds}


def recompute_loco_pooled_and_per_match(rows):
    """Independent R0 LOCO: every competition is a test fold once. Returns pooled (over rows) + a
    match-clustered per-match mean RPS list (the statistically-honest unit = MATCH)."""
    comps = sorted({r.get("competition_label") for r in rows})
    pooled = {"rps": 0.0, "ll": 0.0, "bd": 0.0, "n": 0}
    per_match = {}
    per_match_comp = {}
    for held in comps:
        test = [r for r in rows if r.get("competition_label") == held]
        for r in test:
            y = r["target_wdl"]
            p = r0_wdl_from_row(r)
            rp = rps_wdl(p, y)
            pooled["rps"] += rp; pooled["ll"] += logloss_wdl(p, y)
            pooled["bd"] += brier_draw(p, y); pooled["n"] += 1
            mid = r["source_match_id"]
            per_match.setdefault(mid, []).append(rp)
            per_match_comp[mid] = held
    pooled_out = {"rps": round(pooled["rps"] / pooled["n"], 5),
                  "logloss": round(pooled["ll"] / pooled["n"], 5),
                  "draw_brier": round(pooled["bd"] / pooled["n"], 5),
                  "n_test_rows": pooled["n"]}
    pm_means = {m: sum(v) / len(v) for m, v in per_match.items()}
    return pooled_out, pm_means, per_match_comp


def match_bootstrap_ci(per_match_values, n=2000, seed=12345):
    """Match-level (cluster) bootstrap CI of the mean per-match RPS. The resampling UNIT is the
    match, preserving all snapshots of a match together (the honest independent unit)."""
    import random
    vals = list(per_match_values)
    if not vals:
        return (None, None)
    rng = random.Random(seed)
    k = len(vals)
    means = []
    for _ in range(n):
        s = [vals[rng.randrange(k)] for _ in range(k)]
        means.append(sum(s) / k)
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[int(0.975 * n)]
    return (round(lo, 5), round(hi, 5))


# =================================================================================================
# main
# =================================================================================================
def main():
    funnel, err = build_funnel()
    audit = {
        "audit": "residual_58_match_cohort_reconstruction",
        "utc": datetime.now(timezone.utc).isoformat(),
        "labels": LABELS,
        "sources": {
            "bridge_csv": str(BRIDGE_CSV), "bridge_audit": str(BRIDGE_AUDIT),
            "event_process_manifest": str(EP_MANIFEST),
            "residual_build_manifest": str(RES_BUILD_MANIFEST),
            "reported_forward_chain": str(REPORTED_FC),
            "reported_loco": str(REPORTED_LOCO),
            "reported_dataset_manifest": str(REPORTED_DATASET),
            "statsbomb_event_dirs": [str(d) for d in SB_EVENT_DIRS],
        },
    }
    if err:
        audit["status"] = "data_insufficient"
        audit["reason"] = err
        OUT_JSON.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(json.dumps({"status": "data_insufficient", "reason": err}))
        return

    eligible_ids = funnel.pop("_eligible_ids")
    no_event_ids = funnel.pop("_no_event_ids")
    comp_of = funnel.pop("_comp_of")
    audit["funnel"] = funnel

    snap_rows = _read_csv(SNAP_CSV) or []
    wdl_rows = _read_csv(WDL_CSV) or []
    rows = attach_targets(snap_rows, wdl_rows)

    # write the reconstructed cohort CSV (one row per match)
    comp_rows = _read_csv(COMPLETENESS_CSV) or []
    comp_lookup = {r["source_match_id"]: r for r in comp_rows}
    wdl_lookup = {r["source_match_id"]: r for r in wdl_rows}
    rows_per_match = Counter(r["source_match_id"] for r in rows)
    OUT_COHORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_COHORT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_match_id", "competition_label", "kickoff_date",
                    "target_wdl", "reg_home_goals", "reg_away_goals",
                    "n_snapshots", "n_events", "in_cohort"])
        for mid in eligible_ids:
            wr = wdl_lookup.get(mid, {})
            cr = comp_lookup.get(mid, {})
            w.writerow([mid, wr.get("competition_label", ""), wr.get("kickoff_date", ""),
                        wr.get("target_wdl", ""), wr.get("reg_home_goals", ""),
                        wr.get("reg_away_goals", ""), rows_per_match.get(mid, 0),
                        cr.get("n_events", ""), 1])

    # ---- independent recomputes ----
    fc = recompute_forward_chain(rows)
    loco_pooled, pm_means, pm_comp = recompute_loco_pooled_and_per_match(rows)
    pm_list = list(pm_means.values())
    boot = match_bootstrap_ci(pm_list)

    # ---- comparison vs reported ----
    rep_fc = _read_json(REPORTED_FC) or {}
    rep_loco = _read_json(REPORTED_LOCO) or {}
    rep_ds = _read_json(REPORTED_DATASET) or {}
    rep_fc_r0 = ((rep_fc.get("pooled") or {}).get("research.residual.w2_reference_r0") or {})
    rep_loco_r0 = ((rep_loco.get("pooled") or {}).get("research.residual.w2_reference_r0") or {})

    def _cmp(name, recomputed, reported, tol=5e-4):
        if reported is None:
            return {"metric": name, "recomputed": recomputed, "reported": None,
                    "abs_diff": None, "match": None}
        d = abs(recomputed - reported)
        return {"metric": name, "recomputed": recomputed, "reported": reported,
                "abs_diff": round(d, 6), "match": d <= tol}

    audit["recompute_forward_chain"] = fc
    audit["recompute_loco_pooled"] = loco_pooled
    audit["match_level"] = {
        "n_matches_clustered": len(pm_list),
        "mean_per_match_rps": round(sum(pm_list) / len(pm_list), 5) if pm_list else None,
        "match_bootstrap_ci_95": boot,
        "note": "honest independent unit = MATCH; CI is cluster bootstrap over matches",
    }
    audit["comparison"] = {
        "forward_chain_pooled_rps": _cmp("fc_pooled_rps_r0",
                                         fc["pooled"]["rps"], rep_fc_r0.get("rps")),
        "forward_chain_pooled_n": {"recomputed": fc["pooled"]["n_test_rows"],
                                   "reported": rep_fc_r0.get("n_test_rows")},
        "forward_chain_pooled_logloss": _cmp("fc_pooled_logloss_r0",
                                             fc["pooled"]["logloss"], rep_fc_r0.get("logloss"), tol=2e-3),
        "forward_chain_pooled_draw_brier": _cmp("fc_pooled_draw_brier_r0",
                                                fc["pooled"]["draw_brier"], rep_fc_r0.get("draw_brier")),
        "loco_pooled_rps": _cmp("loco_pooled_rps_r0", loco_pooled["rps"], rep_loco_r0.get("rps")),
        "loco_pooled_n": {"recomputed": loco_pooled["n_test_rows"],
                          "reported": rep_loco_r0.get("n_test_rows")},
        "n_matches": {"recomputed": len(eligible_ids),
                      "reported_dataset_manifest": rep_ds.get("n_matches"),
                      "reported_fc": rep_fc.get("n_matches"),
                      "reported_loco": rep_loco.get("n_matches")},
        "n_rows": {"recomputed": len(rows),
                   "reported_dataset_manifest": rep_ds.get("n_rows")},
    }

    # per-fold comparison (forward chain)
    rep_folds = {f["competition"]: f for f in (rep_fc.get("folds") or [])}
    fold_cmp = []
    for f in fc["folds"]:
        rf = rep_folds.get(f["competition"], {})
        rep_r0 = (rf.get("models") or {}).get("research.residual.w2_reference_r0", {})
        fold_cmp.append({
            "competition": f["competition"],
            "recomputed_rps": f["r0_rps"], "reported_rps": rep_r0.get("rps"),
            "abs_diff": round(abs(f["r0_rps"] - rep_r0["rps"]), 6) if rep_r0.get("rps") is not None else None,
            "recomputed_n_test": f["n_test"], "reported_n_test": rf.get("n_test"),
        })
    audit["forward_chain_fold_comparison"] = fold_cmp

    # ---- verdict ----
    fc_match = audit["comparison"]["forward_chain_pooled_rps"]["match"]
    loco_match = audit["comparison"]["loco_pooled_rps"]["match"]
    n_match_ok = (len(eligible_ids) == 58 and rep_ds.get("n_matches") == 58)
    audit["verdict"] = {
        "cohort_reconstructed_to_58": n_match_ok,
        "forward_chain_rps_reproduced": bool(fc_match),
        "loco_rps_reproduced": bool(loco_match),
        "all_folds_reproduced": all(
            (fc["abs_diff"] is not None and fc["abs_diff"] <= 5e-4) for fc in fold_cmp),
        "status": "complete" if (n_match_ok and fc_match) else "needs_review",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": audit["verdict"]["status"],
        "n_matches_recomputed": len(eligible_ids),
        "fc_pooled_rps_recomputed": fc["pooled"]["rps"],
        "fc_pooled_rps_reported": rep_fc_r0.get("rps"),
        "fc_match": fc_match,
        "loco_pooled_rps_recomputed": loco_pooled["rps"],
        "loco_pooled_rps_reported": rep_loco_r0.get("rps"),
        "loco_match": loco_match,
        "funnel_258_to_58": [s["n_matches"] for s in funnel["stages"]],
    }, indent=2))


if __name__ == "__main__":
    main()
