"""Run the hierarchical transfer ladder (T0..T7) intl-only evaluation on the materialized Phase-3
domain-normalized transfer dataset, plus the preregistered ablations and the candidate rule.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Reads ONLY verified local data:
  data/processed/domain_normalized_transfer/transfer_dataset_v1.csv  (materialized real dataset)
Writes derived outputs (never raw / never the collector):
  outputs/research_runs/<run_id>/hierarchical_transfer/{ladder_eval.json, candidate_rule.json,
                                                         ablations.json, reliability.json, summary.md}
  data/reference/hierarchical_transfer_eval_audit.json   (latest-run pointer + headline metrics)

If the dataset is absent/empty it emits an honest data_insufficient status (never fabricates rows).
Self-test mode (--self-test) runs the whole pipeline on a deterministic synthetic 3-tournament dataset
(no disk) so the engine is provably runnable anywhere.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.hierarchical_transfer import LADDER, PRIMARY_CANDIDATE  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import eval as HE  # noqa: E402
from wcdrawlab.research.hierarchical_transfer import registry as REG  # noqa: E402
from wcdrawlab.research.transfer import domain_normalized_dataset as DS  # noqa: E402

DATASET_CSV = ROOT / "data/processed/domain_normalized_transfer/transfer_dataset_v1.csv"
AUDIT_OUT = ROOT / "data/reference/hierarchical_transfer_eval_audit.json"
ELIG = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("ht_%Y%m%dT%H%M%SZ")


def load_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---- synthetic dataset for --self-test (deterministic, 3 temporally-separated tournaments) ----------
def synthetic_dataset() -> List[dict]:
    rows = []
    tours = [("SynthCupA", "2016", "2016-06-14"), ("SynthCupB", "2018", "2018-06-14"),
             ("SynthCupC", "2022", "2022-11-20")]
    mid = 0
    for tour, season, base_ko in tours:
        for m in range(6):
            mid += 1
            reg_h = (mid * 2) % 4
            reg_a = (mid * 3) % 3
            tgt = "H" if reg_h > reg_a else ("A" if reg_a > reg_h else "D")
            has_xg = (m % 3 != 0)
            for t in (20.0, 45.0, 70.0):
                cur_h = int(round(reg_h * (t / 90.0)))
                cur_a = int(round(reg_a * (t / 90.0)))
                r = {"source_match_id": f"I{mid:03d}", "match_id": f"I{mid:03d}",
                     "competition_label": tour, "competition": tour, "season": season,
                     "comp_type": "international", "domain": "international",
                     "kickoff_date": base_ko[:8] + f"{14 + m:02d}", "snapshot_minute": t,
                     "snapshot_reason": "clock", "remaining_regulation_min": 90.0 - t,
                     "period": 1 if t < 45 else 2, "goals_home": cur_h, "goals_away": cur_a,
                     "goals_diff": cur_h - cur_a, "players_home": 11, "players_away": 11,
                     "players_diff": 0, "yellow_diff": (mid % 3) - 1, "sendoff_diff": 0,
                     "subs_used_diff": (mid % 4) - 2, "poss_share_diff": -0.1 + 0.02 * m,
                     "field_tilt_home": 0.45 + 0.01 * m, "final_third_actions_diff": (mid % 11) - 5,
                     "box_entries_diff": (mid % 7) - 3, "recoveries_diff": (mid % 9) - 4,
                     "turnovers_diff": (mid % 9) - 4, "corners_diff": (mid % 5) - 2,
                     "att_free_kicks_diff": (mid % 6) - 2, "shots_diff": (mid % 7) - 3,
                     "shots_on_target_diff": (mid % 5) - 2, "n_events_observed": 400 + mid,
                     "source_root": "lake_object", "source_sha256": f"sha_{mid}",
                     "engine_version": "synth", "rem_goals_home": float(max(0, reg_h - cur_h)),
                     "rem_goals_away": float(max(0, reg_a - cur_a)), "target_wdl": tgt}
                if has_xg:
                    r.update({"xg_present": "True", "cum_xg_diff": 0.2 * (cur_h - cur_a),
                              "cum_xg_total": 0.3 * (cur_h + cur_a) + 0.4,
                              "xg_last5m_diff": 0.05 * ((mid % 5) - 2),
                              "xg_last10m_diff": 0.08 * ((mid % 7) - 3)})
                else:
                    r["xg_present"] = "False"
                rows.append(r)
    club = DS.synthetic_club_rows(n_matches=8)
    out = DS.build_all_fold_rows(rows, club)
    return out["rows"]


# ---- ablation drivers -------------------------------------------------------------------------------
def _strip_models(loco: Dict, keep: Sequence[str]) -> Dict:
    """Trim a LOCO result to only the requested models (for a focused ablation table)."""
    keep = set(keep)
    out = {"protocol": loco["protocol"], "n_folds": loco["n_folds"], "folds": []}
    for f in loco["folds"]:
        out["folds"].append({**{k: v for k, v in f.items() if k != "models"},
                             "models": {k: v for k, v in f["models"].items() if k in keep}})
    out["per_model_match_rps"] = {k: v for k, v in loco.get("per_model_match_rps", {}).items() if k in keep}
    return out


def _pooled_rps(loco: Dict, sid: str) -> Optional[float]:
    import numpy as np
    vals = [f["models"][sid]["rps"] for f in loco["folds"]
            if f["models"].get(sid) and f["models"][sid].get("rps") is not None]
    return float(np.mean(vals)) if vals else None


def run_ablations(rows: List[dict], loco_full: Dict) -> Dict:
    """The preregistered contrast table. Each entry is a pair of pooled RPS values + delta (B - A)."""
    pairs = [
        ("T0", "T1"), ("T1", "T2"), ("T1", "T3"), ("T3", "T4"),
        ("T4", "T5"), ("T5", "T6"), ("T6", "T7"),
    ]
    contrasts = []
    for a, b in pairs:
        ra = _pooled_rps(loco_full, a)
        rb = _pooled_rps(loco_full, b)
        contrasts.append({"contrast": f"{a}->{b}", "rps_A": ra, "rps_B": rb,
                          "delta_B_minus_A": (None if (ra is None or rb is None) else rb - ra)})

    # T3-no-club: rebuild T3 on intl-only train (drop club rows) vs T3 on pooled
    intl_only_rows = [r for r in rows if r.get("domain", "international") == "international"]
    loco_no_club = HE.loco_eval(intl_only_rows, ids=("T0", "T3"))
    contrasts.append({"contrast": "T3_no_club_vs_T3",
                      "rps_T3_no_club": _pooled_rps(loco_no_club, "T3"),
                      "rps_T3_with_club": _pooled_rps(loco_full, "T3"),
                      "note": "club rows dropped from training" if any(
                          r.get("domain") == "club" for r in rows) else
                      "no club rows in dataset -> identical (vacuous)"})

    # stable subset families: xg / possession / transition / set-piece only (reported as availability)
    fam_subsets = {
        "xg_only": ["cum_xg_diff", "cum_xg_total", "xg_last5m_diff", "xg_last10m_diff"],
        "possession_only": ["poss_share_diff", "field_tilt_home", "final_third_actions_diff"],
        "transition_only": ["recoveries_diff", "turnovers_diff", "box_entries_diff"],
        "set_piece_only": ["corners_diff", "att_free_kicks_diff"],
    }
    fam_present = {}
    feat_cols = {k[len("feat_"):] for r in rows[:50] for k in r.keys() if k.startswith("feat_")}
    for fam, cols in fam_subsets.items():
        fam_present[fam] = sorted(c for c in cols if c in feat_cols)

    # high vs low overlap reliability already in reliability tables; report overlap distribution
    overlaps = sorted({r.get("domain_overlap_score") for r in rows if r.get("domain_overlap_score")})

    return {"primary_contrasts": contrasts,
            "T3_no_club": contrasts[-1] if contrasts else None,
            "stable_feature_family_presence": fam_present,
            "domain_overlap_values_present": overlaps,
            "note": "club-dependent ablations (T5-uniform-vs-overlap, T6-always-on-vs-selective, "
                    "club-family-removal) are vacuous when the materialized dataset has no club rows; "
                    "they are reported as such rather than fabricated."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="run on synthetic data (no disk read)")
    ap.add_argument("--dataset", default=str(DATASET_CSV))
    ap.add_argument("--out-root", default=str(ROOT / "outputs/research_runs"))
    ap.add_argument("--candidate", default=PRIMARY_CANDIDATE)
    args = ap.parse_args(argv)

    run_id = _run_id()
    out_dir = Path(args.out_root) / run_id / "hierarchical_transfer"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.self_test:
        rows = synthetic_dataset()
        source = "synthetic_self_test"
    else:
        rows = load_rows(Path(args.dataset))
        source = str(args.dataset)

    if not rows:
        payload = {"status": "data_insufficient", "reason": "transfer dataset absent/empty",
                   "dataset": source, "generated_ts": _now(), "eligibility": ELIG}
        (out_dir / "ladder_eval.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        AUDIT_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    # leakage guard + intl-only test population are asserted inside the eval drivers
    loco = HE.loco_eval(rows, ids=LADDER)
    fc = HE.forward_chain_eval(rows, ids=LADDER)

    if loco["n_folds"] < 2:
        payload = {"status": "data_insufficient", "reason": "fewer than 2 international folds available",
                   "n_folds": loco["n_folds"], "dataset": source, "generated_ts": _now(),
                   "eligibility": ELIG}
        (out_dir / "ladder_eval.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        AUDIT_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    ablations = run_ablations(rows, loco)
    cand_rule = HE.evaluate_candidate_rule(loco, args.candidate, reference="T0")

    # strip heavy rows_detail from reliability before serialization (keep aggregate tables only)
    reliability = loco.get("reliability", {})

    headline = {sid: {"pooled_rps": _pooled_rps(loco, sid)} for sid in LADDER}
    ladder_payload = {
        "eval_version": HE.EVAL_VERSION, "generated_ts": _now(), "run_id": run_id,
        "dataset": source, "eligibility": ELIG, "reference_model": "T0",
        "registry": REG.registry_summary(),
        "loco": {"protocol": "loco", "n_folds": loco["n_folds"],
                 "folds": [{k: v for k, v in f.items()} for f in loco["folds"]],
                 "headline_pooled_rps": headline},
        "forward_chain": {"protocol": "forward_chain", "n_folds": fc["n_folds"],
                          "tournament_order": fc["tournament_order"], "pooled": fc["pooled"]},
        "primary_candidate": args.candidate,
    }

    (out_dir / "ladder_eval.json").write_text(json.dumps(ladder_payload, indent=2, default=str),
                                              encoding="utf-8")
    (out_dir / "candidate_rule.json").write_text(json.dumps(cand_rule, indent=2, default=str),
                                                 encoding="utf-8")
    (out_dir / "ablations.json").write_text(json.dumps(ablations, indent=2, default=str), encoding="utf-8")
    (out_dir / "reliability.json").write_text(json.dumps(reliability, indent=2, default=str),
                                              encoding="utf-8")

    md = ["# Hierarchical transfer ladder — intl-only eval", "", f"_{ELIG}_", "",
          f"- run_id: `{run_id}`", f"- dataset: `{source}`", f"- LOCO folds: {loco['n_folds']}",
          f"- forward-chain folds: {fc['n_folds']}", "",
          "## Pooled RPS (lower better; reference = T0)", "", "| model | pooled RPS | vs T0 |", "|---|---|---|"]
    t0 = headline["T0"]["pooled_rps"]
    for sid in LADDER:
        r = headline[sid]["pooled_rps"]
        delta = (None if (r is None or t0 is None) else round(r - t0, 5))
        md.append(f"| {sid} ({REG.canonical_id(sid)}) | {None if r is None else round(r,5)} | {delta} |")
    md += ["", f"## Candidate rule ({args.candidate} vs T0)", "",
           f"- verdict: **{cand_rule['verdict']}**", f"- reason: {cand_rule['reason']}"]
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")

    audit = {"status": "complete", "generated_ts": _now(), "run_id": run_id, "dataset": source,
             "eligibility": ELIG, "n_loco_folds": loco["n_folds"], "n_forward_folds": fc["n_folds"],
             "headline_pooled_rps": headline, "candidate": args.candidate,
             "candidate_verdict": cand_rule["verdict"], "candidate_reason": cand_rule["reason"],
             "out_dir": str(out_dir)}
    AUDIT_OUT.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": "complete", "run_id": run_id, "n_loco_folds": loco["n_folds"],
                      "headline_pooled_rps": headline, "candidate_verdict": cand_rule["verdict"]},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
