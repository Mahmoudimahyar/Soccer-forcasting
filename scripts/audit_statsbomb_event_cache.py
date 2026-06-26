"""Audit the StatsBomb event cache: compute the VALID EXACT-BRIDGE completion rate across registered roots.
A file counts only if it parses, events are ordered, and team identity matches the bridge. Gate = ceil(0.90*258).
Do NOT call the cache complete merely because files exist. research_only."""
import csv, glob, json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR
import importlib.util
spec = importlib.util.spec_from_file_location("cache_mod", ROOT / "scripts/complete_statsbomb_event_cache.py")
CM = importlib.util.module_from_spec(spec); spec.loader.exec_module(CM)

def main():
    rows = CM._bridge_rows()
    by_id = {str(r["sb_match_id"]): r for r in rows}
    # locate each bridge match's event file across registered roots
    files = {}
    for rn in ("statsbomb_raw", "statsbomb_raw_prior"):
        try:
            for fp in glob.glob(str(DR.get_root(rn) / "events" / "*.json")):
                p = Path(fp); files.setdefault(p.stem, fp)
        except Exception: pass
    valid = 0; xg_ok = 0; per = []
    for sbid, row in by_id.items():
        fp = files.get(sbid)
        if not fp:
            per.append({"sb_match_id": sbid, "status": "missing"}); continue
        try:
            raw = Path(fp).read_bytes(); ok, info = CM._validate(raw, row)
        except Exception:
            per.append({"sb_match_id": sbid, "status": "read_error"}); continue
        if ok:
            valid += 1; xg_ok += 1 if info.get("xg_field_available") else 0
            per.append({"sb_match_id": sbid, "status": "valid", "events": info["event_count"],
                        "xg": info["xg_field_available"]})
        else:
            per.append({"sb_match_id": sbid, "status": "invalid", **info})
    total = len(rows); gate = math.ceil(0.90 * total)
    rate = round(valid / total, 4)
    out = {"total_exact_bridge": total, "valid_cached": valid, "xg_field_available": xg_ok,
           "completion_rate": rate, "hard_gate_count": gate, "gate_90pct_met": valid >= gate,
           "missing_or_invalid": total - valid}
    (ROOT / "data/reference/statsbomb_cache_audit.json").write_text(
        json.dumps({**out, "per_match": per}, indent=2), encoding="utf-8")
    print(json.dumps(out))

if __name__ == "__main__":
    main()
