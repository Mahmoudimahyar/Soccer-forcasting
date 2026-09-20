"""JOB: COVERAGE audit of the International Event Lake against the legacy + modern bridges.

Runs the canonical fail-closed sentinel (L.run_sentinel) and then cross-checks lake coverage vs:
  - the legacy exact international bridge (L.load_exact_bridge)
  - the exact rows of the expanded modern bridge (expanded_international_bridge_manifest.json)

Reports integrity verdict, coverage (present / missing-from-lake), and a RAW-BACKED source-quality
rollup (xg/possession/location/shot/card/sub) re-derived from each lake object (hash-verified, never
claimed from id lists). Lists the match ids still to be acquired by JOB6.

Outputs:
  data/reference/international_event_lake_audit.json
  notes/research/international_event_lake_audit_report.md
research_only.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import _lakejob as J
import _lake_catalog_util as U  # noqa: F401
from wcdrawlab.research import international_event_lake as L


def _exact_modern_ids() -> set[int]:
    exp = J.REFERENCE / "expanded_international_bridge_manifest.json"
    out: set[int] = set()
    if exp.exists():
        try:
            for r in json.loads(exp.read_text(encoding="utf-8")).get("rows", []):
                if r.get("classification") == "exact" and r.get("local_sb_match_id") not in (None, ""):
                    out.add(int(r["local_sb_match_id"]))
        except Exception:
            pass
    return out


def _detect_fields(events: list) -> dict:
    has = {"xg": False, "possession": False, "location": False, "shot": False, "card": False, "sub": False}
    for e in events:
        if not isinstance(e, dict):
            continue
        if "location" in e:
            has["location"] = True
        if e.get("possession") is not None:
            has["possession"] = True
        t = (e.get("type") or {}).get("name")
        if t == "Shot":
            has["shot"] = True
            if (e.get("shot") or {}).get("statsbomb_xg") is not None:
                has["xg"] = True
        elif t == "Substitution":
            has["sub"] = True
        if (e.get("bad_behaviour") or {}).get("card") or (e.get("foul_committed") or {}).get("card"):
            has["card"] = True
    return has


def main(argv=None) -> int:
    lake = L.Lake.resolve()
    sentinel = L.run_sentinel(lake, write_report=True)
    index = L.read_index(lake)
    lake_ids = {int(k) for k in index.keys()}

    legacy_ids = set(L.load_exact_bridge().keys())
    modern_ids = _exact_modern_ids()
    eligible = legacy_ids | modern_ids
    present = eligible & lake_ids
    missing = eligible - lake_ids

    # RAW-BACKED source-quality rollup: re-derive from each hash-verified object.
    quality = defaultdict(int)
    for sid_str, rec in index.items():
        obj = lake.root / rec["local_path"]
        if not obj.exists():
            continue
        raw = obj.read_bytes()
        if L.sha256_bytes(raw) != rec.get("sha256"):
            continue  # fail-closed: do not count an object that does not hash-verify
        vr = L.validate_event_bytes(raw)
        if not vr.ok:
            continue
        try:
            events = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        f = _detect_fields(events)
        quality["objects_scanned"] += 1
        for k_short, k_long in (("xg", "xg_available"), ("possession", "possession_available"),
                                ("location", "location_available"), ("shot", "shot_available"),
                                ("card", "card_available"), ("sub", "substitution_available")):
            if f[k_short]:
                quality[k_long] += 1

    audit = {
        "schema_version": "international_event_lake_audit_v1",
        "built_ts": L._utc_now(),
        "integrity": sentinel.to_dict() | {"failures": sentinel.failures[:50]},
        "lake_objects": len(lake_ids),
        "legacy_bridge_ids": len(legacy_ids),
        "modern_exact_ids": len(modern_ids),
        "eligible_union": len(eligible),
        "present_in_lake": len(present),
        "missing_from_lake": len(missing),
        "missing_match_ids": sorted(missing),
        "source_quality": dict(quality),
    }
    J.write_json(J.REFERENCE / "international_event_lake_audit.json", audit)

    report = J.NOTES / "international_event_lake_audit_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# International Event Lake — Coverage Audit", "",
        f"built_ts: {L._utc_now()}", "",
        f"- integrity: **all_ok={sentinel.ok}** (checked {sentinel.checked}, "
        f"failures {len(sentinel.failures)})",
        f"- lake objects: **{len(lake_ids)}**",
        f"- legacy bridge ids: {len(legacy_ids)} | modern exact ids: {len(modern_ids)} "
        f"| eligible union: {len(eligible)}",
        f"- present in lake: **{len(present)}** | missing-from-lake (to acquire by JOB6): "
        f"**{len(missing)}**", "",
        "## Source-quality rollup (RAW-BACKED, hash-verified objects)", "",
        "| signal | count |", "| --- | --- |",
    ]
    for k in ("objects_scanned", "xg_available", "possession_available", "location_available",
              "shot_available", "card_available", "substitution_available"):
        lines.append(f"| {k} | {quality.get(k, 0)} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "integrity_all_ok": sentinel.ok,
        "lake_objects": len(lake_ids),
        "eligible_union": len(eligible),
        "present_in_lake": len(present),
        "missing_from_lake": len(missing),
    }))
    return 0 if sentinel.ok else 1


if __name__ == "__main__":
    sys.exit(main())
