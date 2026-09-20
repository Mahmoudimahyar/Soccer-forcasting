"""LK_JOB08 -- build the frozen cohort + exclusion ledger + causal datasets (Phase 4).

Invokes the EXISTING real builder scripts/build_international_event_lake_cohort.py, which is the SINGLE
source of truth for which senior men's international matches enter evaluation. It reads event JSON ONLY
from the persistent content-addressed lake (every object hash-verified), reuses the locked event_process
engine for regulation-only causal snapshots, applies the strict EXACT-bridge gate, enforces NO 2026 WORLD
CUP in any cohort, runs a real leakage self-test on produced rows, and writes:
  international_event_lake_cohort_manifest.{csv,json}, _cohort_exclusions.csv, _cohort_report.md.

This job records the cohort match count, exclusion counts, sub-cohort counts, total snapshots, and the
leakage self-test verdict. It is RAW-BACKED (counts come from the lake). FAIL CLOSED if the leakage
self-test fails or a 2026 WC row leaks (the builder itself raises in that case).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk

MANIFEST_JSON = _lk.REF / "international_event_lake_cohort_manifest.json"


def main():
    L = _lk.lake_engine()
    try:
        lake = L.Lake.resolve()
        n_index = len(L.read_index(lake))
    except Exception as e:
        _lk.emit("failed", reason=f"lake_resolve_failed: {e!r}")
        return

    if n_index == 0:
        _lk.emit("data_insufficient",
                 reason="lake is empty (no objects restored/acquired) -- cannot build a cohort")
        return

    res = _lk.run_builder("scripts/build_international_event_lake_cohort.py")
    last = res.get("last_json") or {}
    man = _lk.read_ref_json("international_event_lake_cohort_manifest.json") or {}

    n_cohort = man.get("n_cohort_matches", last.get("n_cohort_matches"))
    n_excluded = man.get("n_excluded", last.get("n_excluded"))
    n_snaps = man.get("n_total_snapshots", last.get("n_total_snapshots"))
    sub = man.get("subcohort_counts") or last.get("subcohort_counts") or {}
    leak = man.get("leakage_self_test") or {}
    leak_all_ok = leak.get("all_ok", last.get("leakage_all_ok"))
    no_2026 = man.get("no_2026_wc_guarantee")

    out = {
        "builder_ok": res["ok"], "builder_returncode": res["returncode"],
        "lake_index_objects": n_index,
        "n_cohort_matches": n_cohort, "n_excluded": n_excluded, "n_total_snapshots": n_snaps,
        "subcohort_counts": sub,
        "leakage_self_test_all_ok": leak_all_ok, "leakage_n_sampled": leak.get("n_sampled"),
        "no_2026_wc_guarantee": no_2026,
        "wdl_distribution": man.get("wdl_distribution"),
        "matches_by_competition": man.get("matches_by_competition"),
        "manifest_present": MANIFEST_JSON.exists(),
        "builder_stderr_tail": res.get("stderr_tail"),
        "raw_backed": True, "hash_verified": True,
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_cohort.json", out)

    if not MANIFEST_JSON.exists() or not res["ok"]:
        _lk.emit("failed",
                 reason=f"cohort builder failed (rc={res['returncode']}); manifest_present="
                        f"{MANIFEST_JSON.exists()}; stderr={res.get('stderr_tail')}")
        return
    # FAIL CLOSED on leakage (the builder raises on a 2026 leak; defence in depth here on the self-test)
    if leak_all_ok is False:
        _lk.emit("failed", reason="cohort leakage self-test FAILED on real rows -- fail closed")
        return

    _lk.emit("complete",
             reason=f"cohort built raw-backed: matches={n_cohort} excluded={n_excluded} "
                    f"snapshots={n_snaps} leakage_all_ok={leak_all_ok} no_2026_wc={no_2026} "
                    f"subcohorts={sub}",
             state_updates={"cohort_matches": n_cohort, "cohort_excluded": n_excluded,
                            "cohort_total_snapshots": n_snaps, "cohort_subcohorts": sub,
                            "cohort_leakage_all_ok": leak_all_ok})


main()
