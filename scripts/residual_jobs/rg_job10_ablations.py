"""RG_JOB10 -- mandatory ablations on the residual W/D/L correction (LOCO).

Isolates WHERE any signal lives by ablating one feature family at a time from the intensity GLM (r1) and
re-scoring OUT-OF-SAMPLE against the W2 reference (r0). Families:
  reference_state | recent_chance | possession_territory | transition | set_pieces | quality_availability

Two ablation axes:
  (A) leave-one-family-OUT  -- drop each family, keep the rest; large RPS rise => that family carried signal;
  (B) only-one-family-IN    -- keep just each family (+ reference_state anchor); isolates marginal value.

Also an AVAILABILITY-GATE ablation: gate ON (canonical) vs gate OFF (force ALL candidate cols, letting the
FeatureSpace zero/mean-fill unavailable cells) -- quantifies how much the gate's "never feed an
everywhere-unavailable feature" rule matters. r0 (parameter-free) is the constant reference throughout.

research_only / experimental. No network/API. Honest data_insufficient if the panel is absent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

WDL = ["H", "D", "A"]
FAMILIES = ["reference_state", "recent_chance", "possession_territory", "transition",
            "set_pieces", "quality_availability"]


def _loco_rps(rows, build_predict, DS):
    """build_predict(train_rows) -> predict_one. Returns pooled OOS RPS + n."""
    tot = 0.0
    n = 0
    for held, train, test in DS.loco_folds(rows):
        try:
            fn = build_predict(train)
        except Exception:
            continue
        for r in test:
            y = r.get("target_wdl")
            if y not in WDL:
                continue
            tot += _rg.rps_wdl(fn(r), y); n += 1
    return (round(tot / n, 5) if n else None), n


def main():
    try:
        bundle = _rg.load_rows()
    except Exception as e:
        from wcdrawlab.research.residual_intensity import datasets as DS
        if isinstance(e, DS.DataInsufficient):
            _rg.emit("data_insufficient", reason=f"panel unavailable: {e}")
            return
        _rg.emit("failed", reason=f"load error: {e!r}")
        return

    import wcdrawlab.research.residual_intensity as RI
    from wcdrawlab.research.residual_intensity import datasets as DS, features as F, availability as AV
    from wcdrawlab.research import dynamic_models as DM
    from wcdrawlab.research.event_process import models as EPM

    rows = list(bundle["rows"])

    # reference r0 (constant) + full r1
    ref_rps, _ = _loco_rps(rows, lambda tr: RI.w2_reference_r0, DS)
    full_cols = F.columns_for(["recent_chance", "possession_territory", "transition", "set_pieces"])
    full_rps, full_n = _loco_rps(rows, lambda tr: RI.build_intensity_glm_r1(tr, full_cols).predict_one, DS)

    # (A) leave-one-family-out
    loo = {}
    for fam in FAMILIES:
        cols = F.columns_for([x for x in ["recent_chance", "possession_territory", "transition",
                                          "set_pieces", "quality_availability"] if x != fam])
        if not cols:
            cols = list(F.REFERENCE_STATE_COLS)
        rps, n = _loco_rps(rows, lambda tr, c=cols: RI.build_intensity_glm_r1(tr, c).predict_one, DS)
        loo[fam] = {"rps_without_family": rps,
                    "delta_vs_full": (round(rps - full_rps, 5) if (rps is not None and full_rps is not None) else None)}

    # (B) only-one-family-in (+ reference_state anchor)
    oneonly = {}
    for fam in FAMILIES:
        cols = F.columns_for(["reference_state", fam])
        rps, n = _loco_rps(rows, lambda tr, c=cols: RI.build_intensity_glm_r1(tr, c).predict_one, DS)
        oneonly[fam] = {"rps_only_family": rps,
                        "delta_vs_reference": (round(rps - ref_rps, 5)
                                               if (rps is not None and ref_rps is not None) else None)}

    # availability-gate ablation: ON (canonical gate_columns) vs OFF (force all candidate cols)
    def gate_on(tr):
        return RI.build_intensity_glm_r1(tr, full_cols).predict_one

    def gate_off(tr):
        # bypass availability gate: feed ALL candidate cols directly to the intensity heads
        return EPM.IntensityWDL(list(full_cols), with_anchor=True, l2=1.0).fit(
            tr, target_key="target_wdl").predict_one

    gon, _ = _loco_rps(rows, gate_on, DS)
    goff, _ = _loco_rps(rows, gate_off, DS)

    _rg.write_json("rg_ablations.json", {
        "reference_r0_rps": ref_rps, "full_r1_rps": full_rps, "full_n_test_rows": full_n,
        "leave_one_family_out": loo, "only_one_family_in": oneonly,
        "availability_gate_ablation": {"gate_on_rps": gon, "gate_off_rps": goff,
            "gate_helps": (gon is not None and goff is not None and gon <= goff)},
        "interpretation": "delta>0 vs full means dropping that family HURT (it carried signal); "
                          "delta<0 vs reference means that family alone improved on r0.",
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    _rg.emit("complete",
             reason=f"ablations: r0={ref_rps} full_r1={full_rps}; LOO+only-one-in over {len(FAMILIES)} "
                    f"families; gate_on={gon} vs gate_off={goff}",
             state_updates={"ablation_full_rps": full_rps, "ablation_ref_rps": ref_rps,
                            "ablation_gate_on_rps": gon, "ablation_gate_off_rps": goff})


main()
