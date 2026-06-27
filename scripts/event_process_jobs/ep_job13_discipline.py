"""EPJOB13 -- DISCIPLINE hazard family y0-y2 (binary: a sending-off by either side strictly AFTER the
snapshot minute, within regulation). y0 is the TRAIN base-rate hazard; y1/y2 are logistic hazards that
are PREREGISTERED-GATED on >=150 positive TRAIN examples (a sending-off is rare). When the gate is not
met -- which is expected on a 58-match international sample -- y1/y2 are HONESTLY skipped and the job
emits data_insufficient for the candidate heads (NOT a fabricated metric), reporting only the y0 base
rate and the positive count so the gap is auditable.

LOCO over international competitions. Honest data_insufficient if the joined intl rows are absent.
2026 WC excluded by the loader. research_only / experimental. No network/API.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import eval as E, models as M
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"EP eval/models import failed: {e!r}")
    raise SystemExit(0)

TARGET = "sendoff_after"
REFERENCE = "research.discipline.y0"


def _factory(train, target_key=TARGET):
    """Adapt discipline_predictors (returns dict with predictors+gate) into loco_binary's {name: fn}."""
    return M.discipline_predictors(train, target_key=target_key)["predictors"]


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"discipline LOCO not possible: {d}")
        return
    rows = data["snapshot_rows"]
    n_pos = sum(int(r[TARGET]) for r in rows)
    base_rate = n_pos / max(1, len(rows))
    gate = M.discipline_predictors(rows, target_key=TARGET)
    gate_open = gate["gate_open"]

    res = E.loco_binary(rows, _factory, TARGET)
    pmb = res["per_model_match_brier"]
    candidates = [m for m in res["pooled"].keys() if m != REFERENCE]
    boots = {c: E.paired_bootstrap_delta(pmb, c, REFERENCE) for c in candidates}

    out = {
        "target": TARGET, "n_positives_full": n_pos, "base_rate": round(base_rate, 6),
        "gate_threshold": M.DISCIPLINE_POSITIVE_GATE, "gate_open": gate_open,
        "reference": REFERENCE, "n_folds": res["n_folds"],
        "pooled": {m: {k: (round(v, 6) if v is not None else None) for k, v in d.items()}
                   for m, d in res["pooled"].items()},
        "candidate_vs_y0_bootstrap": boots, "folds": res["folds"],
        "n_rows": len(rows), "n_matches": data["n_matches"], "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    }
    L.write_json("ep_discipline_loco.json", out)

    if not gate_open:
        # y1/y2 are honestly not fit; y0 base-rate reported. This is data_insufficient for the candidates,
        # NOT a false completion -- the sending-off signal is too sparse to fit a hazard model.
        L.emit("data_insufficient",
               reason=f"discipline y1/y2 GATED OFF: n_positives={n_pos} < {M.DISCIPLINE_POSITIVE_GATE}; "
                      f"only y0 base-rate hazard reported (base_rate={round(base_rate,5)}). Honest skip.",
               state_updates={"discipline_positives": n_pos, "discipline_gate_open": False})
        return
    favored = [c for c, b in boots.items() if b.get("favors_candidate")]
    L.emit("complete",
           reason=f"discipline LOCO folds={res['n_folds']} n_positives={n_pos} gate_open=True "
                  f"favored={favored or 'none'}",
           state_updates={"discipline_positives": n_pos, "discipline_gate_open": True,
                          "discipline_favored": len(favored)})


main()
