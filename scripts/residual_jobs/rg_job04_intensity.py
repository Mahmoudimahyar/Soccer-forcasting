"""RG_JOB04 -- side-specific remaining-goal INTENSITY family I0-I3 (leave-one-competition-out).

W2 (i0) is the REFERENCE INTENSITY: both sides at the league base rate scaled by remaining regulation
time. The candidates estimate an event-process correction to those side rates and must beat i0 OUT-OF-
SAMPLE on the intensity targets rem_goals_home/rem_goals_away (Poisson deviance + MAE), or they are
reference-tier.

  i0 research.intensity.w2_home_away_i0          -- parameter-free W2 home/away reference (anchor)
  i1 research.intensity.event_residual_home_away_i1 -- ridge intensity heads on availability-gated state
  i2 research.intensity.regime_specific_i2       -- regime-conditioned multiplicative correction of i0,
                                                    fit IN-TRAIN per interpretable regime (alpha=1 -> i0)
  i3 research.intensity.club_transfer_i3         -- i1 + frozen club-trained transfer scalar (club rows
                                                    NEVER test rows); honest skip if no club aux rows

Protocol: LOCO over competitions; train each candidate on the held-OUT-of-competition rows, predict the
held competition. Per-side Poisson deviance (lower better) is the headline; MAE is reported alongside.
research_only / experimental. No network/API. Honest data_insufficient if labels/panel absent.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

I0 = "research.intensity.w2_home_away_i0"
I1 = "research.intensity.event_residual_home_away_i1"
I2 = "research.intensity.regime_specific_i2"
I3 = "research.intensity.club_transfer_i3"


def _poisson_dev(lam, y):
    lam = max(1e-9, float(lam))
    y = max(0.0, float(y))
    if y <= 0:
        return 2.0 * lam
    return 2.0 * (y * math.log(y / lam) - (y - lam))


def _labeled(rows):
    return [r for r in rows if r.get("rem_goals_home") is not None and r.get("rem_goals_away") is not None]


def _regime_multipliers(train_rows):
    """IN-TRAIN regime-conditioned multiplicative correction of the W2 side rates. For each regime g,
    factor_g = mean(observed rem goals in g) / mean(W2 lam in g), shrunk toward 1.0. Degenerates to i0
    (factor 1) when a regime has no train support."""
    import wcdrawlab.research.residual_intensity as RI
    agg = {}
    for r in _labeled(train_rows):
        g = r.get("ri_regime", "unknown")
        lh, la = RI.w2_intensities(r)
        d = agg.setdefault(g, {"w2": 0.0, "obs": 0.0, "n": 0})
        d["w2"] += lh + la
        d["obs"] += float(r["rem_goals_home"]) + float(r["rem_goals_away"])
        d["n"] += 1
    mult = {}
    for g, d in agg.items():
        if d["w2"] <= 1e-9 or d["n"] < 20:
            mult[g] = 1.0
            continue
        raw = d["obs"] / d["w2"]
        # shrink toward 1.0 by train support (more rows -> trust the ratio more)
        w = d["n"] / (d["n"] + 50.0)
        mult[g] = w * raw + (1.0 - w) * 1.0
    return mult


def _eval_intensity(test_rows, side_rate_fn):
    """side_rate_fn(row) -> (lam_home, lam_away). Returns per-side pooled Poisson deviance + MAE."""
    dev_h = dev_a = mae_h = mae_a = 0.0
    n = 0
    for r in _labeled(test_rows):
        lh, la = side_rate_fn(r)
        yh = float(r["rem_goals_home"]); ya = float(r["rem_goals_away"])
        dev_h += _poisson_dev(lh, yh); dev_a += _poisson_dev(la, ya)
        mae_h += abs(lh - yh); mae_a += abs(la - ya)
        n += 1
    if n == 0:
        return None
    return {"n": n, "poisson_dev_home": dev_h / n, "poisson_dev_away": dev_a / n,
            "poisson_dev_mean": (dev_h + dev_a) / (2 * n),
            "mae_home": mae_h / n, "mae_away": mae_a / n, "mae_mean": (mae_h + mae_a) / (2 * n)}


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
    if len(_labeled(rows)) < 50:
        _rg.emit("data_insufficient",
                 reason=f"only {len(_labeled(rows))} rows carry rem_goals labels (<50); cannot score intensity")
        return

    club = _rg.load_club_rows()

    # accumulate per-side deviance pooled across LOCO folds
    acc = {m: {"dev_h": 0.0, "dev_a": 0.0, "mae_h": 0.0, "mae_a": 0.0, "n": 0, "folds": 0}
           for m in (I0, I1, I2, I3)}
    fold_records = []
    n_folds = 0
    for held, train, test in DS.loco_folds(rows):
        n_folds += 1
        # build candidates on TRAIN only
        i1_pred = RI.intensity_heads_r1(train)
        mult = _regime_multipliers(train)

        def i0_fn(r):
            return RI.w2_intensities(r)

        def i1_fn(r, _p=i1_pred):
            d = _p(r); return d["lam_home"], d["lam_away"]

        def i2_fn(r, _m=mult):
            lh, la = RI.w2_intensities(r)
            f = _m.get(r.get("ri_regime", "unknown"), 1.0)
            return lh * f, la * f

        side_fns = {I0: i0_fn, I1: i1_fn, I2: i2_fn}
        if club:
            model_i3, rep = RI.build_club_auxiliary_transfer_r6(train, club)
            rep.annotate(test)  # attach frozen club scalar to TEST rows (representation is frozen)

            def i3_fn(r, _m=model_i3):
                lh, la = _m._raw_intensities(r); return lh, la
            side_fns[I3] = i3_fn

        rec = {"competition": held, "n_test": len(test)}
        for mid, fn in side_fns.items():
            res = _eval_intensity(test, fn)
            if res is None:
                continue
            a = acc[mid]
            a["dev_h"] += res["poisson_dev_home"] * res["n"]
            a["dev_a"] += res["poisson_dev_away"] * res["n"]
            a["mae_h"] += res["mae_home"] * res["n"]
            a["mae_a"] += res["mae_away"] * res["n"]
            a["n"] += res["n"]; a["folds"] += 1
            rec[mid] = {"poisson_dev_mean": round(res["poisson_dev_mean"], 5),
                        "mae_mean": round(res["mae_mean"], 5)}
        fold_records.append(rec)

    pooled = {}
    for mid, a in acc.items():
        if a["n"] == 0:
            pooled[mid] = None
            continue
        pooled[mid] = {"poisson_dev_home": round(a["dev_h"] / a["n"], 5),
                       "poisson_dev_away": round(a["dev_a"] / a["n"], 5),
                       "poisson_dev_mean": round((a["dev_h"] + a["dev_a"]) / (2 * a["n"]), 5),
                       "mae_mean": round((a["mae_h"] + a["mae_a"]) / (2 * a["n"]), 5),
                       "n_test_rows": a["n"], "n_folds": a["folds"]}

    ref = pooled.get(I0)
    ref_dev = ref["poisson_dev_mean"] if ref else None
    beats = {m: (pooled.get(m) is not None and ref_dev is not None
                 and pooled[m]["poisson_dev_mean"] < ref_dev) for m in (I1, I2, I3) if pooled.get(m)}

    _rg.write_json("rg_intensity_loco.json", {
        "protocol": "loco_intensity", "reference": I0,
        "metric": "side-specific Poisson deviance (lower better) + MAE",
        "pooled": pooled, "beats_reference": beats, "club_transfer_active": bool(club),
        "n_folds": n_folds, "folds": fold_records,
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    _rg.emit("complete",
             reason=f"intensity LOCO folds={n_folds}; ref(i0)_dev={ref_dev}; "
                    f"beats_ref={beats}; club_transfer={'on' if club else 'off (i3 skipped)'}",
             state_updates={"intensity_ref_dev": ref_dev, "intensity_beats_ref": beats,
                            "intensity_folds": n_folds})


main()
