"""RG_JOB03 -- availability gate + interpretable regimes + feature catalog.

For the REAL panel this job records, per feature column: family, source-availability coverage (fraction of
rows where the cell is genuinely present -- never zero-filled), and whether the deterministic gate would
DROP it as everywhere-unavailable. It also records the interpretable regime distribution (game-state x
evidence-tier; a causal classifier on availability/state, NOT an outcome model) and the per-family
coverage. The feature catalog is mirrored to data/reference/residual_goal_intensity/.

This is the gate that guarantees an everywhere-unavailable feature (e.g. xG on a no-xG match) can never
feed a model head; the audit here makes that property auditable on the real data.

research_only / experimental. Honest data_insufficient if the panel is absent.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg


def main():
    try:
        bundle = _rg.load_rows()
    except Exception as e:
        from wcdrawlab.research.residual_intensity import datasets as DS
        if isinstance(e, DS.DataInsufficient):
            _rg.emit("data_insufficient", reason=f"residual panel unavailable: {e}")
            return
        _rg.emit("failed", reason=f"load error: {e!r}")
        return

    rows = list(bundle["rows"])
    from wcdrawlab.research.residual_intensity import (availability as AV, regimes as RG,
                                                       features as F, quality as Q)

    cols = list(F.ALL_FEATURE_COLS)
    cov = AV.coverage_report(rows, cols)               # {col: fraction present}
    gated = set(AV.gate_columns(rows, cols))           # cols the gate would KEEP (>0 coverage)
    av_audit = Q.availability_audit(rows)
    regime_cov = RG.regime_coverage(rows)

    catalog = []
    for c in cols:
        fam = F.family_of(c)
        coverage = round(float(cov.get(c, 0.0)), 4)
        catalog.append({
            "column": c, "family": fam,
            "source_coverage": coverage,
            "gate_keeps": c in gated,
            "everywhere_unavailable": coverage <= 0.0,
            "leakage_rule": "value uses only events with clock-minute <= snapshot_minute (regulation only)",
            "missing_policy": "FLAGGED not imputed (gate drops everywhere-unavailable; FeatureSpace marks per-row unknown)",
        })

    # per-family coverage summary
    fam_cov = {}
    for fam in F.FEATURE_FAMILIES:
        fcols = [c for c in F.FEATURE_FAMILIES[fam]]
        vals = [float(cov.get(c, 0.0)) for c in fcols if c in cov]
        fam_cov[fam] = {"n_cols": len(fcols),
                        "mean_coverage": round(sum(vals) / len(vals), 4) if vals else 0.0,
                        "min_coverage": round(min(vals), 4) if vals else 0.0}

    _rg.write_json("rg_feature_catalog.json", {
        "n_feature_cols": len(catalog), "columns": catalog,
        "family_coverage": fam_cov,
        "availability_audit": av_audit,
        "everywhere_unavailable_cols": av_audit.get("everywhere_unavailable_cols", []),
        "regime_coverage": regime_cov,
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })

    # mirror a flat CSV under data/reference/residual_goal_intensity/
    _rg.RES_REF.mkdir(parents=True, exist_ok=True)
    fields = ["column", "family", "source_coverage", "gate_keeps", "everywhere_unavailable"]
    with (_rg.RES_REF / "feature_catalog.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in catalog:
            w.writerow(r)

    n_dropped = sum(1 for c in catalog if c["everywhere_unavailable"])
    n_regimes = len(regime_cov.get("rows_per_regime", {})) if isinstance(regime_cov, dict) else 0
    _rg.emit("complete",
             reason=f"feature_catalog={len(catalog)} cols ({n_dropped} everywhere-unavailable -> gate-dropped); "
                    f"{n_regimes} interpretable regimes; per-family coverage recorded; "
                    f"missing flagged-not-imputed",
             state_updates={"n_feature_cols": len(catalog), "n_gate_dropped": n_dropped,
                            "n_regimes": n_regimes})


main()
