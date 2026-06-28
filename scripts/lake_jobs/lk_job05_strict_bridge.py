"""LK_JOB05 -- expanded STRICT exact bridge (official catalog -> local exact international fixtures).

Invokes the EXISTING real builder scripts/bridge_official_international_matches.py, which applies the
STRICT key (competition + season + match_date + normalized team-set + regulation-result agreement) with
NO fuzzy / NO forced bridge. Ambiguous rows are dropped and never enter evaluation. The output is the
expanded_international_bridge_manifest.{csv,json} + report.

This job records the classification counts (exact / score_mismatch / date_mismatch / ...) and the exact
bridge count. It needs the official catalog (JOB03) as input; if the catalog is absent it emits
`data_insufficient` (honest) rather than fabricating a bridge. The canonical exact bridge that actually
gates the cohort is the immutable L.load_exact_bridge() -- this job NEVER mutates it; it only produces the
official<->local classification view.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk

CATALOG_JSON = _lk.REF / "official_modern_international_catalog.json"
MANIFEST_JSON = _lk.REF / "expanded_international_bridge_manifest.json"


def main():
    if not CATALOG_JSON.exists():
        _lk.emit("data_insufficient",
                 reason="official catalog absent (JOB03 not complete) -- cannot build strict bridge; "
                        "no fabrication")
        return

    res = _lk.run_builder("scripts/bridge_official_international_matches.py")
    last = res.get("last_json") or {}

    man = _lk.read_ref_json("expanded_international_bridge_manifest.json")
    counts = (man or {}).get("classification_counts") or last.get("classification_counts") or {}
    exact_n = (man or {}).get("exact_bridge_count")
    if exact_n is None:
        exact_n = last.get("exact_bridge_count")

    # the canonical immutable exact bridge (gates the cohort; never mutated here)
    canonical_exact = None
    try:
        L = _lk.lake_engine()
        canonical_exact = len(L.load_exact_bridge())
    except Exception:
        canonical_exact = None

    out = {
        "builder_ok": res["ok"], "builder_returncode": res["returncode"],
        "official_catalog_matches": (man or {}).get("official_catalog_matches") or last.get("official_catalog_matches"),
        "local_exact_fixtures": (man or {}).get("local_exact_fixtures") or last.get("local_exact_fixtures"),
        "classification_counts": counts,
        "expanded_exact_bridge_count": exact_n,
        "canonical_exact_bridge_count": canonical_exact,
        "manifest_present": MANIFEST_JSON.exists(),
        "policy": "strict_exact_only_no_fuzzy_no_forced; ambiguous never enters evaluation",
        "builder_stderr_tail": res.get("stderr_tail"),
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_strict_bridge.json", out)

    if MANIFEST_JSON.exists():
        _lk.emit("complete",
                 reason=f"strict bridge: exact={exact_n} canonical_exact={canonical_exact} "
                        f"classification={counts} no_fuzzy_no_forced=True",
                 state_updates={"strict_bridge_done": True, "expanded_exact_bridge_count": exact_n,
                                "canonical_exact_bridge_count": canonical_exact})
        return

    _lk.emit("data_insufficient",
             reason=f"strict bridge manifest not produced (rc={res['returncode']}); "
                    f"stderr={res.get('stderr_tail')}")


main()
