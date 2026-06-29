"""PHASE 2 — Audit the result reconciliation output (read-only).

Verifies: every predicted-universe fixture has a verified-final result, no Odds API was called, outcome
orientation is internally consistent, and no non-final result is marked verified. Exits non-zero on a
hard discrepancy. Writes a small audit JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "prospective_harvest"))
from _harvest_common import PRED_LEDGER, SCORING_ROOT, stamp_labels, write_json  # noqa: E402
from refresh_prospective_final_results import RECON_JSON, RESULTS_CSV  # noqa: E402

AUDIT = SCORING_ROOT / "results" / "reconciliation_audit.json"


def main():
    preds = pd.read_csv(PRED_LEDGER)
    universe = set(preds["match_id"].unique())
    res = pd.read_csv(RESULTS_CSV)
    manifest = json.loads(RECON_JSON.read_text())

    vf = res[res.reconciliation_status == "verified_final"]
    vf_ids = set(vf.canonical_fixture_id.dropna())
    missing = sorted(universe - vf_ids)

    # outcome orientation consistency: home-orientation vs team_a-orientation must agree with goals
    bad_orientation = []
    for r in vf.itertuples():
        hg, ag = r.home_regulation_goals, r.away_regulation_goals
        exp_home = "HOME" if hg > ag else ("DRAW" if hg == ag else "AWAY")
        if r.final_1x2_outcome_home_orientation != exp_home:
            bad_orientation.append(r.canonical_fixture_id)

    # no verified-final without numeric goals
    bad_verified = vf[vf[["home_regulation_goals", "away_regulation_goals"]].isna().any(axis=1)]

    checks = {
        "odds_api_called": bool(manifest.get("odds_api_called", True)),
        "all_universe_verified_final": len(missing) == 0,
        "n_universe": len(universe), "n_verified_in_universe": len(universe & vf_ids),
        "missing_universe_fixtures": missing,
        "orientation_consistent": len(bad_orientation) == 0,
        "no_verified_without_goals": len(bad_verified) == 0,
    }
    checks["all_ok"] = (not checks["odds_api_called"] and checks["all_universe_verified_final"]
                        and checks["orientation_consistent"] and checks["no_verified_without_goals"])
    write_json(AUDIT, stamp_labels(checks))
    print(f"RECON AUDIT | all_ok={checks['all_ok']} verified_in_universe={checks['n_verified_in_universe']}/{checks['n_universe']} "
          f"odds_api_called={checks['odds_api_called']} orientation_ok={checks['orientation_consistent']}")
    if not checks["all_ok"]:
        print("  DISCREPANCY:", {k: v for k, v in checks.items() if v not in (True, [], 0) and k != "n_universe"})
        sys.exit(2)


if __name__ == "__main__":
    main()
