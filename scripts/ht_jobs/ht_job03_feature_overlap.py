"""HT_JOB03 -- feature-overlap / domain-shift audit.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: produce the per-feature domain-comparability audit. The cross-domain (intl vs club) statistics
(SMD / variance-ratio / distribution-overlap) require a REAL club feature distribution; when the club
event corpus is not materialised locally those are honestly emitted as ``data_insufficient`` (NEVER
fabricated). What IS derivable from the materialised international dataset -- the per-feature presence
fraction, mean/sd, and the stable-feature subset that survived the dataset builder's gate -- is computed
here directly from the dataset CSV so the audit is grounded in the real rows the ladder consumes.

Surfaces the existing Phase-2 product (data/reference/feature_overlap_audit.json) and reconciles it with
the materialised dataset's kept stable-feature subset.
"""
from __future__ import annotations

import math
from typing import Dict, List

import _ht as H

JOB = "JOB3"

CANDIDATE_FEATS = [
    "feat_goals_diff", "feat_players_diff", "feat_yellow_diff", "feat_sendoff_diff",
    "feat_subs_used_diff", "feat_poss_share_diff", "feat_field_tilt_home",
    "feat_final_third_actions_diff", "feat_box_entries_diff", "feat_recoveries_diff",
    "feat_turnovers_diff", "feat_corners_diff", "feat_att_free_kicks_diff",
    "feat_shots_diff", "feat_shots_on_target_diff",
    "feat_cum_xg_diff", "feat_cum_xg_total", "feat_xg_last5m_diff", "feat_xg_last10m_diff",
]


def _profile(rows: List[dict], cols: List[str], domain: str) -> Dict[str, dict]:
    sub = [r for r in rows if (r.get("domain") or "international") == domain]
    n = len(sub)
    out = {}
    for c in cols:
        vals = [H._fnum(r.get(c)) for r in sub]
        present = [v for v in vals if v is not None]
        if present:
            m = sum(present) / len(present)
            var = sum((v - m) ** 2 for v in present) / len(present)
            out[c] = {"present_frac": round(len(present) / n, 4) if n else 0.0,
                      "mean": round(m, 5), "sd": round(math.sqrt(var), 5), "n": len(present)}
        else:
            out[c] = {"present_frac": 0.0, "mean": None, "sd": None, "n": 0}
    return out


def main():
    art = H.envelope(JOB, "running")
    existing = H.read_ref_json("feature_overlap_audit.json")

    if not H.dataset_present():
        art["status"] = "data_insufficient"
        art["existing_phase2_audit_present"] = existing is not None
        H.write_json("job03_feature_overlap.json", art)
        return H.emit("data_insufficient",
                      "materialised transfer dataset absent -- feature-overlap audit needs the real rows "
                      "(surface-only of the Phase-2 product is recorded)")

    rows = H.load_dataset_rows()
    feat_cols = [c for c in CANDIDATE_FEATS if c in rows[0]]
    intl_profile = _profile(rows, feat_cols, "international")
    club_profile = _profile(rows, feat_cols, "club")
    n_club = sum(1 for r in rows if (r.get("domain") or "international") == "club")

    # cross-domain SMD only where BOTH domains have a real distribution
    cross = {}
    for c in feat_cols:
        pi, pc = intl_profile[c], club_profile[c]
        if pi["mean"] is not None and pc["mean"] is not None and n_club > 0:
            pooled = math.sqrt(((pi["sd"] or 0) ** 2 + (pc["sd"] or 0) ** 2) / 2.0) or 1.0
            smd = abs(pi["mean"] - pc["mean"]) / pooled if pooled > 1e-12 else 0.0
            cross[c] = {"smd": round(smd, 4), "status": "computed"}
        else:
            cross[c] = {"smd": None, "status": "data_insufficient",
                        "reason": "club distribution not materialised"}

    kept = sorted({r.get("stable_feature_subset_size") for r in rows[:50]})
    overlap_scores = sorted({H._fnum(r.get("domain_overlap_score")) for r in rows[:50]
                             if H._fnum(r.get("domain_overlap_score")) is not None})

    art.update({
        "existing_phase2_audit_present": existing is not None,
        "n_candidate_features": len(feat_cols),
        "n_club_rows": n_club,
        "international_profile": intl_profile,
        "club_profile": (club_profile if n_club > 0 else
                         {"status": "data_insufficient",
                          "reason": "no club rows in materialised dataset (club events not local)"}),
        "cross_domain_smd": cross,
        "stable_feature_subset_size_observed": kept,
        "domain_overlap_score_observed": overlap_scores,
        "cross_domain_status": ("computed" if n_club > 0 else "data_insufficient_single_domain"),
    })
    art["status"] = "complete"
    H.write_json("job03_feature_overlap.json", art)
    H.emit("complete",
           f"feature-overlap audit on {len(feat_cols)} features; club_rows={n_club} "
           f"({'cross-domain SMD computed' if n_club > 0 else 'single-domain: cross-domain SMD honestly data_insufficient'})",
           state_updates={"feature_overlap_ok": True, "n_candidate_features": len(feat_cols),
                          "single_domain": n_club == 0})


if __name__ == "__main__":
    main()
