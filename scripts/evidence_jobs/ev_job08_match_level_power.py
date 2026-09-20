"""EV_JOB08 -- match-level statistical power.

Runs the REAL match-level power analysis (scripts/run_match_level_power_analysis.py), whose independent
unit is the MATCH (snapshots of a match form one cluster) and whose noise template is calibrated to the
observed per-match paired RPS deltas from the 58-match residual LOCO eval. Records: current power at
M=58 for a grid of target absolute-RPS improvements, matches/tournaments needed for 60/80/90% power, and
the "more snapshots, same 58 matches" clustering-ceiling demonstration. Deterministic (fixed master seed).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    res = _ev.run_builder("scripts/run_match_level_power_analysis.py")
    power = _ev.read_ref_json("match_level_power_analysis.json")
    if power is None:
        _ev.emit("data_insufficient",
                 reason=f"power analysis not produced (rc={res['returncode']}): {res['stderr_tail']}")
        return
    unit = power.get("unit_of_independence")
    cur = power.get("current_power_at_58_matches", {})
    needed = power.get("matches_and_tournaments_needed", {})
    n_obs = (power.get("data_provenance", {}) or {}).get("n_matches_observed")
    # honest guard: the power model must be match-clustered, not row-level
    match_clustered = bool(unit and "match" in str(unit).lower())
    _ev.write_json("ev_match_level_power_summary.json", {
        "builder_returncode": res["returncode"],
        "unit_of_independence": unit, "match_clustered": match_clustered,
        "n_matches_observed": n_obs,
        "current_power_at_58": cur,
        "matches_and_tournaments_needed": needed,
        "more_snapshots_same_matches": power.get("more_snapshots_same_matches", {}).get("by_inflation"),
        "seeds": power.get("seeds"),
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    if not match_clustered:
        _ev.emit("failed",
                 reason=f"power analysis unit is not match-clustered: unit={unit}")
        return
    _ev.emit("complete",
             reason=f"match-level power computed (unit={unit}); power@58={cur}",
             state_updates={"power_unit": unit, "power_at_58": cur,
                            "power_match_clustered": match_clustered})


main()
