"""LK_JOB03 -- official senior men's international catalog + selection manifest.

Invokes the EXISTING real builder scripts/build_official_modern_international_catalog.py, which fetches
the OFFICIAL StatsBomb Open Data competitions.json + per-(competition,season) match lists for the senior
men's international competitions ONLY (FIFA World Cup, UEFA Euro, Copa America, African Cup of Nations,
from allowed_competitions) and writes the catalog + selection manifest + report. A 2026 FIFA World Cup
season, if it ever appears in open data, is EXCLUDED there (never enters any cohort).

External retrieval = OFFICIAL StatsBomb Open Data ONLY (engine/builder-owned). This job reads the
builder's LAST JSON line and records counts. If the official source is unreachable AND no prior catalog
exists on disk, this job emits `waiting_for_official_source` (honest -- no fabrication). If a prior valid
catalog exists, the job reuses it and reports that the network step was skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk

CATALOG_JSON = _lk.REF / "official_modern_international_catalog.json"
SELECTION_JSON = _lk.REF / "official_modern_international_selection_manifest.json"


def _summarize_existing():
    cat = _lk.read_ref_json("official_modern_international_catalog.json")
    sel = _lk.read_ref_json("official_modern_international_selection_manifest.json")
    n_matches = len(cat.get("matches", cat) if isinstance(cat, dict) else cat) if cat else None
    if isinstance(cat, dict) and "n_matches" in cat:
        n_matches = cat["n_matches"]
    return cat, sel, n_matches


def main():
    pre_exists = CATALOG_JSON.exists()
    res = _lk.run_builder("scripts/build_official_modern_international_catalog.py")
    last = res.get("last_json") or {}

    cat, sel, n_matches = _summarize_existing()
    catalog_present = CATALOG_JSON.exists()
    selection_present = SELECTION_JSON.exists()

    out = {
        "builder_ok": res["ok"], "builder_returncode": res["returncode"],
        "builder_last_json": last, "builder_stderr_tail": res.get("stderr_tail"),
        "catalog_present": catalog_present, "selection_present": selection_present,
        "catalog_pre_existed": pre_exists,
        "n_catalog_matches": last.get("n_matches", n_matches),
        "n_selected_comp_seasons": last.get("n_comp_seasons") or last.get("n_selected"),
        "allowed_competitions": last.get("allowed_competitions"),
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_official_catalog.json", out)

    if catalog_present and selection_present:
        # real product on disk (freshly built or reused) -> complete
        reused = (not res["ok"]) and pre_exists
        _lk.emit("complete",
                 reason=(f"official_catalog {'reused_prior(network_skipped)' if reused else 'built'} "
                         f"n_matches={out['n_catalog_matches']} "
                         f"comp_seasons={out['n_selected_comp_seasons']} official_source_only=True"),
                 state_updates={"catalog_present": True,
                                "n_catalog_matches": out["n_catalog_matches"]})
        return

    # builder could not run AND no prior catalog -> genuinely waiting for the official source
    if not catalog_present:
        _lk.emit("waiting_for_official_source",
                 reason=f"official catalog unavailable (builder rc={res['returncode']}); "
                        f"no prior catalog on disk; will retry on resume. "
                        f"stderr={res.get('stderr_tail')}")
        return

    _lk.emit("data_insufficient",
             reason="catalog present but selection manifest missing; rerun builder")


main()
