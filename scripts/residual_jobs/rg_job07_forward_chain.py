"""RG_JOB07 -- PRIMARY forward-chaining W/D/L evaluation of the residual family R0-R6.

Forward-chaining over INTERNATIONAL competitions ordered by earliest kickoff: for competition c_k, fit on
all EARLIER competitions only, score on c_k. This is the primary out-of-sample protocol; r0 (the W2
remaining-time Poisson reference) is the anchor every richer residual model must beat. We record pooled +
per-fold RPS / logloss / draw-Brier for every canonical residual model.

A forward chain needs >= 1 competition with an earlier competition to train on; with N competitions there
are N-1 scorable folds. Honest data_insufficient if the ordered intl population is too small.
research_only / experimental. No network/API. 2026 WC excluded upstream.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

REF = "research.residual.w2_reference_r0"
WDL = ["H", "D", "A"]


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
    from wcdrawlab.research.residual_intensity import datasets as DS

    rows = list(bundle["rows"])
    club = _rg.load_club_rows()
    order = DS.forward_chain_order(rows)
    if len(order) < 2:
        _rg.emit("data_insufficient",
                 reason=f"forward chain needs >=2 ordered intl competitions; found {len(order)}: {order}")
        return

    pooled = {}
    folds = []
    n_folds = 0
    for i in range(1, len(order)):
        held = order[i]
        train = [r for r in rows if r.get("competition") in set(order[:i])
                 and r.get("comp_type", "international") == "international"]
        test = [r for r in rows if r.get("competition") == held
                and r.get("comp_type", "international") == "international"]
        if not train or not test:
            continue
        n_folds += 1
        try:
            preds = RI.residual_predictors(train, club_rows=club if club else None)
        except Exception as e:
            folds.append({"competition": held, "error": repr(e), "n_train": len(train), "n_test": len(test)})
            continue
        fold_rec = {"competition": held, "n_train": len(train), "n_test": len(test), "models": {}}
        for mid, fn in preds.items():
            agg = pooled.setdefault(mid, {"rps": 0.0, "ll": 0.0, "bd": 0.0, "n": 0})
            frps = fll = fn_ = 0.0
            cnt = 0
            for r in test:
                y = r.get("target_wdl")
                if y not in WDL:
                    continue
                p = fn(r)
                rp = _rg.rps_wdl(p, y)
                agg["rps"] += rp; agg["ll"] += _rg.logloss_wdl(p, y)
                agg["bd"] += _rg.brier_draw(p, y); agg["n"] += 1
                frps += rp; fll += _rg.logloss_wdl(p, y); cnt += 1
            if cnt:
                fold_rec["models"][mid] = {"rps": round(frps / cnt, 5), "logloss": round(fll / cnt, 5),
                                           "n": cnt}
        folds.append(fold_rec)

    pooled_out = {m: ({"rps": round(a["rps"] / a["n"], 5), "logloss": round(a["ll"] / a["n"], 5),
                       "draw_brier": round(a["bd"] / a["n"], 5), "n_test_rows": a["n"]} if a["n"] else None)
                  for m, a in pooled.items()}
    ref_rps = (pooled_out.get(REF) or {}).get("rps")
    beats = {m: (pooled_out.get(m) is not None and ref_rps is not None and pooled_out[m]["rps"] < ref_rps)
             for m in pooled_out if m != REF}
    any_beats = any(beats.values())

    _rg.write_json("rg_wdl_forward_chain.json", {
        "protocol": "forward_chain_wdl", "reference": REF,
        "competition_order": order, "n_folds": n_folds,
        "pooled": pooled_out, "beats_reference_pooled": beats,
        "folds": folds, "club_transfer_active": bool(club),
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    best = min(((m, v["rps"]) for m, v in pooled_out.items() if v), key=lambda kv: kv[1], default=(None, None))
    _rg.emit("complete",
             reason=f"forward-chain folds={n_folds} order={order} ref(r0)_rps={ref_rps} "
                    f"best={best[0]}({best[1]}) any_candidate_beats_r0={any_beats}",
             state_updates={"fc_folds": n_folds, "fc_ref_rps": ref_rps,
                            "fc_any_candidate_beats_ref": any_beats})


main()
