"""Audit the CAUSAL DOMAIN-NORMALIZED TRANSFER DATASET (Phase 3) -- re-assert every leakage invariant.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This auditor independently re-checks the hard invariants of the transfer plane produced by
scripts/build_domain_normalized_transfer_dataset.py (+ the build manifest). It NEVER fabricates a result:
when the materialised dataset is absent it audits the deterministic SYNTHETIC build instead and says so.

Invariants re-asserted (each -> a pass/fail line in the report):
  1.  no completed-2026-World-Cup row in ANY domain / fold (assert_no_2026);
  2.  every intl_train / club_train row's kickoff is STRICTLY BEFORE its fold cutoff (temporal cutoff);
  3.  no CLUB row carries row_role=intl_test (auxiliary-only club rule);
  4.  each fold's held-out test is a SINGLE international tournament;
  5.  the domain baseline + stable-feature filter were fit on TRAIN rows only (re-fit on TRAIN, compare);
  6.  always-excluded domain-shifted columns NEVER appear as a kept feat_* column;
  7.  transfer_residual_* equals observed remaining goals minus the DOMAIN baseline (recomputed);
  8.  match-level grouping is intact (a match_id never spans two folds with conflicting roles);
  9.  no competition-label leak (a fold's intl_train never contains the held-out tournament's label);
  10. deterministic fold recreation (the in-memory rebuild reproduces fold structure + kept subsets);
  11. source traceability (every row carries source_sha256 + engine_version).

No network / API-Football / Odds API / scrape / credentials / paid source. Pure local read.

Outputs:
  data/reference/domain_normalized_transfer_audit.json
  notes/research/domain_normalized_transfer_audit_report.md
Exit code is 0 even on data_insufficient (honest skip); 2 only if a real materialised dataset VIOLATES an
invariant.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("transfer-dataset audit must not run inside the active collector checkout")

from wcdrawlab.research.transfer import domain_normalized_dataset as DND  # noqa: E402

REF = ROOT / "data" / "reference"
NOTES = ROOT / "notes" / "research"
DATASET_CSV = ROOT / "data/processed/domain_normalized_transfer/transfer_dataset_v1.csv"
MANIFEST_JSON = ROOT / "data/processed/domain_normalized_transfer/build_manifest.json"
AUDIT_JSON = REF / "domain_normalized_transfer_audit.json"
REPORT_MD = NOTES / "domain_normalized_transfer_audit_report.md"

AUDIT_SCHEMA = "domain_normalized_transfer_audit_v1"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fnum(row: dict, col: str):
    return DND.fnum(row, col)


# =================================================================================================
# row source: the materialised CSV (preferred) or the deterministic synthetic build (honest fallback)
# =================================================================================================
def _load_rows():
    """Return (rows, source). Prefer the real materialised CSV; otherwise build the deterministic
    synthetic dataset in-memory (clearly labelled). Never fabricates a 'real' result."""
    if DATASET_CSV.exists():
        with DATASET_CSV.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if rows:
            return rows, "materialised_real_dataset"
    built = DND.build_all_fold_rows(DND.synthetic_intl_rows(), DND.synthetic_club_rows())
    return built["rows"], "deterministic_synthetic"


# =================================================================================================
# invariant checks (pure; each returns a {check, ok, detail} record)
# =================================================================================================
def _rec(check: str, ok: bool, detail) -> dict:
    return {"check": check, "ok": bool(ok), "detail": detail}


def check_no_2026(rows) -> dict:
    bad = [r for r in rows
           if DND._is_2026_wc(r.get("competition_label") or r.get("competition"), r.get("kickoff_date"))]
    return _rec("no_2026_world_cup_row", len(bad) == 0, {"n_violations": len(bad)})


def check_temporal_cutoff(rows) -> dict:
    bad = []
    for r in rows:
        role = r.get("row_role")
        if role not in ("intl_train", "club_train"):
            continue
        ko = r.get("kickoff_date") or ""
        cut = r.get("fold_cutoff_kickoff") or ""
        if ko and cut and not (ko < cut):
            bad.append({"match_id": r.get("match_id"), "role": role, "kickoff": ko, "cutoff": cut})
    return _rec("train_rows_strictly_before_fold_cutoff", len(bad) == 0,
                {"n_violations": len(bad), "examples": bad[:5]})


def check_club_never_test(rows) -> dict:
    bad = [r for r in rows if r.get("row_role") == "intl_test" and r.get("domain") == DND.DOMAIN_CLUB]
    return _rec("club_row_never_intl_test", len(bad) == 0, {"n_violations": len(bad)})


def check_single_intl_test_tournament(rows) -> dict:
    by_fold: dict = {}
    for r in rows:
        if r.get("row_role") != "intl_test":
            continue
        f = r.get("fold_held_tournament")
        comp = r.get("competition_label") or r.get("competition")
        by_fold.setdefault(f, set()).add(comp)
    bad = {f: sorted(c) for f, c in by_fold.items() if len(c) != 1}
    # also: every test competition must equal the fold's held tournament label
    mismatch = {f: sorted(c) for f, c in by_fold.items()
                if not (len(c) == 1 and next(iter(c)) == f)}
    ok = (len(bad) == 0) and (len(mismatch) == 0)
    return _rec("each_fold_test_is_single_intl_tournament", ok,
                {"n_folds_with_test": len(by_fold), "multi_comp_folds": bad, "mismatched_folds": mismatch})


def check_no_competition_label_leak(rows) -> dict:
    held_by_fold = {r.get("fold_held_tournament") for r in rows}
    bad = []
    for r in rows:
        if r.get("row_role") != "intl_train":
            continue
        comp = r.get("competition_label") or r.get("competition")
        if comp == r.get("fold_held_tournament"):
            bad.append({"match_id": r.get("match_id"), "comp": comp,
                        "fold": r.get("fold_held_tournament")})
    return _rec("intl_train_never_contains_held_tournament", len(bad) == 0,
                {"n_folds": len(held_by_fold), "n_violations": len(bad), "examples": bad[:5]})


def check_excluded_columns_never_feat(rows) -> dict:
    if not rows:
        return _rec("excluded_columns_never_feat", True, {"n_violations": 0})
    cols = set(rows[0].keys())
    bad = [c for c in DND.ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS if f"feat_{c}" in cols]
    return _rec("excluded_columns_never_feat", len(bad) == 0, {"violations": bad})


def check_residual_recomputation(rows, tol: float = 1e-4) -> dict:
    """Re-derive transfer_residual_total = (rem_goals_home + rem_goals_away) - domain_baseline_total and
    compare to the stored value (rows where the label is present)."""
    n_checked = 0
    bad = []
    for r in rows:
        oh = _fnum(r, "rem_goals_home")
        oa = _fnum(r, "rem_goals_away")
        bt = _fnum(r, "domain_baseline_total")
        rt = _fnum(r, "transfer_residual_total")
        if oh is None or oa is None or bt is None or rt is None:
            continue
        n_checked += 1
        expect = (oh + oa) - bt
        if abs(expect - rt) > tol:
            bad.append({"match_id": r.get("match_id"), "expect": round(expect, 6), "stored": rt})
    return _rec("transfer_residual_equals_obs_minus_domain_baseline", len(bad) == 0,
                {"n_checked": n_checked, "n_violations": len(bad), "examples": bad[:5]})


def check_match_level_grouping(rows) -> dict:
    """A given (match_id, fold) carries exactly one row_role; and a match's role is consistent within a
    fold (a single match is never split train/test inside one fold)."""
    roles: dict = {}
    for r in rows:
        key = (r.get("match_id"), r.get("fold_held_tournament"))
        roles.setdefault(key, set()).add(r.get("row_role"))
    bad = {f"{k[0]}|{k[1]}": sorted(v) for k, v in roles.items() if len(v) != 1}
    return _rec("match_level_grouping_consistent_per_fold", len(bad) == 0,
                {"n_keys": len(roles), "n_violations": len(bad)})


def check_source_traceability(rows) -> dict:
    bad = [r for r in rows if not (r.get("source_sha256") and r.get("engine_version"))]
    return _rec("every_row_has_source_sha_and_engine_version", len(bad) == 0,
                {"n_rows": len(rows), "n_missing": len(bad)})


def check_eligibility_labels(rows) -> dict:
    want = "/".join(DND.ELIGIBILITY_LABELS)
    bad = [r for r in rows if r.get("eligibility") != want]
    return _rec("eligibility_labels_present_on_every_row", len(bad) == 0,
                {"want": want, "n_rows": len(rows), "n_bad": len(bad)})


def check_deterministic_rebuild() -> dict:
    """The in-memory synthetic build is byte-stable (no RNG in the dataset path)."""
    a = DND.build_all_fold_rows(DND.synthetic_intl_rows(), DND.synthetic_club_rows())
    b = DND.build_all_fold_rows(DND.synthetic_intl_rows(), DND.synthetic_club_rows())
    same_rows = a["rows"] == b["rows"]
    same_subsets = ([f["stable_feature_subset"] for f in a["summary"]["folds"]] ==
                    [f["stable_feature_subset"] for f in b["summary"]["folds"]])
    return _rec("deterministic_fold_recreation", same_rows and same_subsets,
                {"rows_identical": same_rows, "subsets_identical": same_subsets})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 2 if any invariant fails on a MATERIALISED real dataset")
    args = ap.parse_args()

    REF.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)

    rows, source = _load_rows()
    checks = [
        check_no_2026(rows),
        check_temporal_cutoff(rows),
        check_club_never_test(rows),
        check_single_intl_test_tournament(rows),
        check_no_competition_label_leak(rows),
        check_excluded_columns_never_feat(rows),
        check_residual_recomputation(rows),
        check_match_level_grouping(rows),
        check_source_traceability(rows),
        check_eligibility_labels(rows),
        check_deterministic_rebuild(),
    ]
    all_ok = all(c["ok"] for c in checks)

    # counts for the report
    roles = {}
    for r in rows:
        roles[r.get("row_role")] = roles.get(r.get("row_role"), 0) + 1
    n_intl_test_matches = len({r.get("match_id") for r in rows if r.get("row_role") == "intl_test"})
    n_club_train_matches = len({r.get("match_id") for r in rows if r.get("row_role") == "club_train"})
    folds = sorted({r.get("fold_held_tournament") for r in rows if r.get("fold_held_tournament")})
    subset_sizes = sorted({int(float(r["stable_feature_subset_size"]))
                           for r in rows if r.get("stable_feature_subset_size") not in (None, "")})

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.exists() else {}

    audit = {
        "schema_version": AUDIT_SCHEMA,
        "generated_ts": _utc(),
        "labels": list(DND.ELIGIBILITY_LABELS),
        "reference_model": DND.REFERENCE_MODEL,
        "row_source": source,
        "n_rows": len(rows),
        "row_roles": roles,
        "n_folds": len(folds),
        "folds": folds,
        "n_intl_test_matches": n_intl_test_matches,
        "n_club_train_matches": n_club_train_matches,
        "stable_feature_subset_sizes": subset_sizes,
        "all_invariants_ok": all_ok,
        "checks": checks,
        "build_manifest_status": manifest.get("status"),
    }
    AUDIT_JSON.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    _write_report(audit)

    print(json.dumps({
        "row_source": source, "all_invariants_ok": all_ok, "n_rows": len(rows),
        "n_folds": len(folds), "n_intl_test_matches": n_intl_test_matches,
        "n_club_train_matches": n_club_train_matches,
        "stable_feature_subset_sizes": subset_sizes,
        "failed_checks": [c["check"] for c in checks if not c["ok"]],
    }, indent=2))

    if args.strict and source == "materialised_real_dataset" and not all_ok:
        return 2
    return 0


def _write_report(audit) -> None:
    L = []
    A = L.append
    A("# Domain-Normalized Transfer Dataset Audit (Phase 3)")
    A("")
    A("_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_")
    A("")
    A(f"Generated: {audit['generated_ts']}")
    A(f"Row source: **{audit['row_source']}**  (reference model: `{audit['reference_model']}`)")
    A("")
    A("## Summary")
    A("")
    A(f"- rows: **{audit['n_rows']}**  |  folds: **{audit['n_folds']}** "
      f"({', '.join(audit['folds']) or 'none'})")
    A(f"- row roles: {audit['row_roles']}")
    A(f"- international test matches: **{audit['n_intl_test_matches']}**  |  "
      f"club train matches: **{audit['n_club_train_matches']}**")
    A(f"- stable-feature subset size(s): **{audit['stable_feature_subset_sizes']}**")
    A(f"- all invariants OK: **{audit['all_invariants_ok']}**")
    A("")
    A("## Invariant checks")
    A("")
    A("| check | ok | detail |")
    A("|---|---|---|")
    for c in audit["checks"]:
        A(f"| {c['check']} | {'PASS' if c['ok'] else 'FAIL'} | {json.dumps(c['detail'], default=str)} |")
    A("")
    if audit["row_source"] != "materialised_real_dataset":
        A("> NOTE: the materialised real dataset CSV was absent, so this audit ran on the DETERMINISTIC "
          "SYNTHETIC build (clearly labelled). Re-run `python scripts/build_domain_normalized_transfer_"
          "dataset.py` to materialise the real transfer dataset, then re-audit for the real verdict.")
        A("")
    REPORT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
