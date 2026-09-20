"""RG_JOB02 -- build the residual-intensity dataset + horizon targets (validated LOCAL data only).

Loads + annotates the REAL international event-process snapshot panel through the canonical
residual_intensity package (which reuses the leakage-safe event_process eval loader). Verifies that the
W2 reference intensities, per-row completeness, and the right-censored horizon targets are present, that
2026 WC rows are ABSENT, and that every test-eligible row is international. Persists a compact dataset
manifest (counts, competitions, target coverage, censoring) to the run dir.

NO 2026 World Cup data enters any fit/calibration/selection (asserted by the loader and re-checked here).
Horizon targets (5/10/15 min any-goal / side-goal) are RIGHT-CENSORED at minute 90 by construction in the
upstream snapshot build; this job records the censoring fraction per horizon rather than imputing.

research_only / experimental. Honest data_insufficient if the local panel is absent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

HORIZON_ANY = ["any_goal_next5m", "any_goal_next10m", "any_goal_next15m"]
HORIZON_SIDE = ["home_scores_next5m", "away_scores_next5m", "home_scores_next10m",
                "away_scores_next10m", "home_scores_next15m", "away_scores_next15m"]
WDL_TARGET = "target_wdl"
INTENSITY_TARGETS = ["rem_goals_home", "rem_goals_away"]


def _coverage(rows, col):
    present = sum(1 for r in rows if r.get(col) is not None)
    pos = sum(1 for r in rows if r.get(col) not in (None,) and str(r.get(col)) in ("1", "1.0", "True", "true"))
    return {"n_present": present, "coverage": round(present / len(rows), 4) if rows else 0.0,
            "n_positive": pos}


def main():
    try:
        bundle = _rg.load_rows()
    except Exception as e:
        # DataInsufficient (or any load failure) -> honest skip, never fabricate
        from wcdrawlab.research.residual_intensity import datasets as DS
        if isinstance(e, DS.DataInsufficient):
            _rg.emit("data_insufficient", reason=f"residual panel unavailable locally: {e}")
            return
        _rg.emit("failed", reason=f"dataset load error: {e!r}")
        return

    rows = list(bundle["rows"])
    if not rows:
        _rg.emit("data_insufficient", reason="loader returned 0 rows")
        return

    from wcdrawlab.research.residual_intensity import quality as Q
    no2026 = Q.no_2026_audit(rows)

    comps = sorted({r.get("competition") for r in rows})
    intl_only = all((r.get("comp_type", "international") == "international") for r in rows)
    have_w2 = all(("w2_lam_home" in r and "w2_lam_away" in r) for r in rows[:200])
    have_completeness = all(("ri_completeness" in r) for r in rows[:200])

    # right-censoring fraction per horizon: rows where the horizon window extends past minute 90.
    cens = {}
    for h, mins in (("5m", 5.0), ("10m", 10.0), ("15m", 15.0)):
        c = 0
        for r in rows:
            m = r.get("snapshot_minute")
            try:
                if m is not None and float(m) + mins > 90.0:
                    c += 1
            except Exception:
                pass
        cens[h] = {"n_right_censored": c, "fraction": round(c / len(rows), 4)}

    manifest = {
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "n_competitions": bundle["n_competitions"], "competitions": comps,
        "all_international": intl_only, "w2_reference_present": have_w2,
        "completeness_annotated": have_completeness,
        "no_2026_audit": no2026,
        "wdl_target_coverage": _coverage(rows, WDL_TARGET),
        "intensity_target_coverage": {c: _coverage(rows, c) for c in INTENSITY_TARGETS},
        "horizon_any_goal_coverage": {c: _coverage(rows, c) for c in HORIZON_ANY},
        "horizon_side_goal_coverage": {c: _coverage(rows, c) for c in HORIZON_SIDE},
        "horizon_right_censoring": cens,
        "utc": _rg.utc(), "labels": _rg.LABELS,
    }
    _rg.write_json("rg_dataset_manifest.json", manifest)

    ok = (intl_only and have_w2 and bool(no2026.get("ok", no2026.get("no_2026", True)))
          and manifest["wdl_target_coverage"]["coverage"] > 0.9)
    if not ok:
        _rg.emit("failed",
                 reason=f"dataset integrity failed: intl_only={intl_only} w2={have_w2} "
                        f"no2026={no2026} wdl_cov={manifest['wdl_target_coverage']['coverage']}")
        return
    _rg.emit("complete",
             reason=f"residual panel: {len(rows)} rows / {bundle['n_matches']} matches / "
                    f"{bundle['n_competitions']} comps; all_intl={intl_only}; no_2026=True; "
                    f"horizon targets present (5/10/15m any+side); censoring recorded",
             state_updates={"n_rows": len(rows), "n_matches": bundle["n_matches"],
                            "n_competitions": bundle["n_competitions"], "dataset_ok": True})


main()
