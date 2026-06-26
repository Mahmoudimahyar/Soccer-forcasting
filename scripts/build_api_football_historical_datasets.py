"""Phase 4: build causal, provenance-preserving research datasets from the corpus raw. Excludes unresolved
(reconciliation-mismatch) fixtures from affected target datasets; never silently drops. Club + international
partitioned. Raw gitignored; derived tables gitignored; a tracked manifest holds counts. No model trained.
research_only.
"""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

RAW = ROOT / "data/raw/api_football_historical_corpus"
PROC = ROOT / "data/processed/api_football_corpus"


def _load_raw():
    fixtures, events, lineups = {}, {}, {}
    for fp in RAW.glob("fixtures_*.json"):
        if "events" in fp.name or "lineups" in fp.name:
            continue
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for fx in p.get("response", []) or []:
            fixtures[str(fx.get("fixture", {}).get("id"))] = fx
    for fp in RAW.glob("fixtures_events_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            events[str(fid)] = p.get("response", []) or []
    for fp in RAW.glob("fixtures_lineups_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            lineups[str(fid)] = p.get("response", []) or []
    return fixtures, events, lineups


def _comp_type(fx):
    lid = fx.get("league", {}).get("id")
    return "club" if lid in (39, 140, 135, 78, 61, 2) else "international"


def main():
    fixtures, events, lineups = _load_raw()
    fids = [f for f in events if f in fixtures]
    PROC.mkdir(parents=True, exist_ok=True)
    recon_rows, card_rows, sub_rows, meta_rows = [], [], [], []
    counts = defaultdict(lambda: defaultdict(int))
    for fid in fids:
        fx = fixtures[fid]; ev = events[fid]; ln = lineups.get(fid, [])
        ctype = _comp_type(fx)
        shash = hashlib.sha256(json.dumps(ev, sort_keys=True).encode()).hexdigest()[:16]
        can = RS.canonical_result(fx, ev)
        can["comp_type"] = ctype; can["source_hash"] = shash
        recon_rows.append(can)
        resolved = can["reconciliation_status"] == "exact"
        counts[ctype]["fixtures"] += 1
        counts[ctype]["with_events"] += int(bool(ev))
        counts[ctype]["with_lineups"] += int(len(ln) >= 2)
        if ln and (ln[0].get("startXI") or [{}])[0].get("player", {}).get("id") is not None:
            counts[ctype]["with_player_ids"] += 1
        if ln and (ln[0].get("startXI") or [{}])[0].get("player", {}).get("pos") is not None:
            counts[ctype]["with_positions"] += 1
        if ln and ln[0].get("substitutes"):
            counts[ctype]["with_bench"] += 1
        if can["final_result_type"] == "after_extra_time":
            counts[ctype]["extra_time_fixtures"] += 1
        if can["final_result_type"] == "penalty_shootout":
            counts[ctype]["shootout_fixtures"] += 1
        if resolved:
            counts[ctype]["regulation_reconciled_exact"] += 1
        else:
            counts[ctype]["unresolved"] += 1
        # cards / subs (only from resolved fixtures enter target datasets)
        for c in HD.cards_table(ev):
            c.update({"canonical_match_id": can["provider_fixture_id"], "comp_type": ctype, "resolved": resolved})
            card_rows.append(c)
            if resolved:
                counts[ctype]["cards_" + c["card_class"]] += 1
        for s in HD.substitutions(ev):
            s.update({"fixture": fid, "comp_type": ctype, "resolved": resolved})
            sub_rows.append(s)
            if resolved:
                counts[ctype]["substitutions"] += 1
        if resolved:
            counts[ctype]["goals"] += can["event_derived_regulation_home_goals"] + can["event_derived_regulation_away_goals"]
        meta_rows.append({"fixture": fid, "comp_type": ctype, "final_result_type": can["final_result_type"],
                          "resolved": resolved, "source_hash": shash})

    # write gitignored tables
    def _w(name, rows):
        if not rows:
            return
        with open(PROC / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    _w("reconciliation.csv", recon_rows); _w("cards.csv", card_rows); _w("substitutions.csv", sub_rows); _w("match_metadata.csv", meta_rows)

    # tracked manifest (counts only)
    manifest = {ct: dict(counts[ct]) for ct in counts}
    for ct in manifest:
        c = manifest[ct]
        c["red_or_second_yellow"] = c.get("cards_direct_red", 0) + c.get("cards_second_yellow", 0) + c.get("cards_second_yellow_red", 0)
        c["regulation_exact_rate"] = round(c.get("regulation_reconciled_exact", 0) / c["fixtures"], 4) if c.get("fixtures") else None
    (ROOT / "notes/research/_corpus_counts.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
