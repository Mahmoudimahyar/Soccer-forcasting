"""RG_JOB05 -- near-term scoring HORIZON family H0-H4 (5/10/15 min, right-censored; LOCO).

Binary "any goal by either side within the next H minutes" at each snapshot. The window is RIGHT-CENSORED
at minute 90 (the upstream snapshot build truncates it); we score only rows whose target is defined and
report censoring. h0 is the parameter-free W2-implied baseline; richer heads add availability-gated
event-process state via a ridge logistic discrete-time hazard and must beat h0 OUT-OF-SAMPLE on Brier +
logloss, or they are reference-tier. h4 is a selective gate that, IN-TRAIN, picks per completeness band
whether to use a richer head or fall back to h0.

  h0 research.horizon.w2_implied_h0            -- 1 - exp(-(lam_h+lam_a)) over the horizon (anchor)
  h1 research.horizon.xg_residual_h1           -- + cumulative/rolling xG residual (gated)
  h2 research.horizon.possession_transition_h2 -- + possession/territory/transition state (gated)
  h3 research.horizon.full_event_process_h3    -- + full event-process state (gated)
  h4 research.horizon.selective_gate_h4        -- training-chosen gate over {h0, best-rich}; h0 fallback

research_only / experimental. No network/API. Honest data_insufficient if no horizon labels.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

HORIZONS = {"5m": ("any_goal_next5m", 5.0), "10m": ("any_goal_next10m", 10.0),
            "15m": ("any_goal_next15m", 15.0)}
H0 = "research.horizon.w2_implied_h0"
H1 = "research.horizon.xg_residual_h1"
H2 = "research.horizon.possession_transition_h2"
H3 = "research.horizon.full_event_process_h3"
H4 = "research.horizon.selective_gate_h4"


def _labeled(rows, tcol):
    out = []
    for r in rows:
        v = r.get(tcol)
        if v is None:
            continue
        try:
            out.append((r, int(float(v))))
        except Exception:
            pass
    return out


def _brier(p, y):
    return (p - y) ** 2


def _logloss(p, y, eps=1e-12):
    p = min(1 - eps, max(eps, p))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _h0_pred(row, hmin):
    import wcdrawlab.research.residual_intensity as RI
    return RI.w2_implied_h0(row, hmin)


def _gated_space(train_rows, cols):
    from wcdrawlab.research.residual_intensity import availability as AV
    from wcdrawlab.research import dynamic_models as DM
    keep = AV.gate_columns(train_rows, cols)
    if not keep:
        return None
    return DM.RidgeLogitBin(DM.FeatureSpace(keep))


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

    from wcdrawlab.research.residual_intensity import datasets as DS, features as F

    rows = list(bundle["rows"])
    xg_cols = F.columns_for(["recent_chance", "quality_availability"])
    poss_cols = F.columns_for(["possession_territory", "transition"])
    full_cols = F.columns_for(["recent_chance", "possession_territory", "transition", "set_pieces",
                               "quality_availability"])

    per_horizon = {}
    any_beats_any = False
    for hkey, (tcol, hmin) in HORIZONS.items():
        if len(_labeled(rows, tcol)) < 100:
            per_horizon[hkey] = {"status": "data_insufficient",
                                 "reason": f"only {len(_labeled(rows, tcol))} labeled rows (<100)"}
            continue
        acc = {m: {"brier": 0.0, "ll": 0.0, "n": 0, "folds": 0} for m in (H0, H1, H2, H3, H4)}
        censored = 0
        for held, train, test in DS.loco_folds(rows):
            tr = [r for r, _ in _labeled(train, tcol)]
            te = _labeled(test, tcol)
            if len(tr) < 50 or not te:
                continue
            h1m = _gated_space(tr, xg_cols)
            h2m = _gated_space(tr, poss_cols)
            h3m = _gated_space(tr, full_cols)
            for m in (h1m, h2m, h3m):
                if m is not None:
                    m.fit(tr, target_key=tcol)

            # h4 gate: choose IN-TRAIN whether the full head (h3) beats h0 on train logloss; if not,
            # the gate falls back to h0 everywhere (honest fallback, never worse than the anchor in-train)
            use_rich_h4 = False
            if h3m is not None:
                ll_h0 = sum(_logloss(_h0_pred(r, hmin), y) for r, y in _labeled(tr, tcol))
                ll_h3 = sum(_logloss(h3m.predict_one(r), y) for r, y in _labeled(tr, tcol))
                use_rich_h4 = ll_h3 < ll_h0

            for r, y in te:
                m = r.get("snapshot_minute")
                try:
                    if m is not None and float(m) + hmin > 90.0:
                        censored += 1
                except Exception:
                    pass
                preds = {H0: _h0_pred(r, hmin)}
                preds[H1] = h1m.predict_one(r) if h1m is not None else preds[H0]
                preds[H2] = h2m.predict_one(r) if h2m is not None else preds[H0]
                preds[H3] = h3m.predict_one(r) if h3m is not None else preds[H0]
                preds[H4] = (h3m.predict_one(r) if (use_rich_h4 and h3m is not None) else preds[H0])
                for mid, p in preds.items():
                    a = acc[mid]
                    a["brier"] += _brier(p, y); a["ll"] += _logloss(p, y); a["n"] += 1
            for mid in acc:
                acc[mid]["folds"] += 1

        pooled = {}
        for mid, a in acc.items():
            pooled[mid] = ({"brier": round(a["brier"] / a["n"], 5), "logloss": round(a["ll"] / a["n"], 5),
                            "n_test_rows": a["n"], "n_folds": a["folds"]} if a["n"] else None)
        ref_b = (pooled.get(H0) or {}).get("brier")
        beats = {m: (pooled.get(m) is not None and ref_b is not None and pooled[m]["brier"] < ref_b)
                 for m in (H1, H2, H3, H4)}
        any_beats_any = any_beats_any or any(beats.values())
        per_horizon[hkey] = {"status": "ok", "pooled": pooled, "beats_reference": beats,
                             "n_right_censored": censored,
                             "base_rate": round(sum(y for _, y in _labeled(rows, tcol)) /
                                                len(_labeled(rows, tcol)), 4)}

    _rg.write_json("rg_horizon_loco.json", {
        "protocol": "loco_horizon_right_censored", "reference": H0,
        "metric": "Brier (lower better) + logloss; binary any-goal in next H min",
        "per_horizon": per_horizon, "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    ok_h = [h for h, v in per_horizon.items() if v.get("status") == "ok"]
    _rg.emit("complete",
             reason=f"horizon LOCO over {ok_h}; any richer head beats h0 on Brier somewhere={any_beats_any}; "
                    f"right-censoring recorded per horizon",
             state_updates={"horizon_evaluated": ok_h, "horizon_any_beats_ref": any_beats_any})


main()
