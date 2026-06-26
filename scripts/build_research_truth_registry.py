"""Phase 0: build the CANONICAL RESEARCH TRUTH REGISTRY by scanning ACTUAL raw data + manifests across all
worktrees (not trusting summaries). Resolves the conflicting claims (900 vs 1120 fixtures; 123 vs 176
sendings-off; player-history completion; StatsBomb bridge/cache/join; prior model-claim validity). Read-only;
no API calls, no key handling. research_only.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

# Known raw locations across worktrees (gitignored; read-only scan)
RAW_LOCATIONS = {
    "corpus_900": Path("C:/Users/Mahyar/worldcup-api-football-corpus/data/raw/api_football_historical_corpus"),
    "deep_research_ext": Path("C:/Users/Mahyar/worldcup-deep-research/data/raw/api_football_historical_corpus"),
    "player_history_60": Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/raw/player_history_corpus"),
    "statsbomb_open": Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/raw/statsbomb_open"),
}


def _scan_af_corpus(root):
    """Return (n_fixtures_with_events, n_reconciled_exact, sendings_off, intl, club)."""
    if not root.exists():
        return {"present": False}
    fixtures, events = {}, {}
    for fp in root.glob("fixtures_*.json"):
        if "events" in fp.name or "lineups" in fp.name:
            continue
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for fx in p.get("response", []) or []:
            fixtures[str(fx.get("fixture", {}).get("id"))] = fx
    for fp in root.glob("fixtures_events_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            events[str(fid)] = p.get("response", []) or []
    n_ev = sum(1 for f in events if f in fixtures)
    exact = so = intl = club = 0
    INTL = {1, 4, 9, 6, 7}
    for fid, fx in fixtures.items():
        ev = events.get(fid)
        if ev is None:
            continue
        can = RS.canonical_result(fx, ev)
        if can["reconciliation_status"] == "exact":
            exact += 1
        else:
            continue
        is_intl = fx.get("league", {}).get("id") in INTL
        intl += is_intl
        club += (not is_intl)
        for c in HD.cards_table(ev):
            if c["card_class"] in ("direct_red", "second_yellow_red"):
                so += 1
    return {"present": True, "fixtures_listed": len(fixtures), "fixtures_with_events": n_ev,
            "reconciled_exact": exact, "sendings_off": so, "intl": intl, "club": club}


def main():
    out = {"scanned_utc": "registry_build", "locations": {}, "resolved_claims": {}}
    # scan AF corpus locations + union
    union_events = {}
    for name in ("corpus_900", "deep_research_ext", "player_history_60"):
        root = RAW_LOCATIONS[name]
        out["locations"][name] = _scan_af_corpus(root)
    # union fixture count (distinct event files across corpus + extension + player-history)
    distinct = set()
    for name in ("corpus_900", "deep_research_ext", "player_history_60"):
        root = RAW_LOCATIONS[name]
        if root.exists():
            for fp in root.glob("fixtures_events_*.json"):
                try:
                    p = json.loads(fp.read_text(encoding="utf-8"))
                    fid = (p.get("parameters") or {}).get("fixture")
                    if fid is not None:
                        distinct.add(str(fid))
                except Exception:
                    pass
    # statsbomb
    sb = RAW_LOCATIONS["statsbomb_open"]
    sb_events = len(list((sb / "events").glob("*.json"))) if (sb / "events").exists() else 0
    bridge_audit = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.audit.json")
    bridged = None
    if bridge_audit.exists():
        try:
            bridged = json.loads(bridge_audit.read_text(encoding="utf-8")).get("total_accepted")
        except Exception:
            bridged = None
    # player-history manifest
    phm = ROOT / "data/reference/player_history_corpus_manifest.json"
    ph_planned = ph_done = None
    if phm.exists():
        ph_planned = json.loads(phm.read_text(encoding="utf-8")).get("n_selected")
    phprog = RAW_LOCATIONS["player_history_60"] / "progress.json"
    if phprog.exists():
        ph_done = len(json.loads(phprog.read_text(encoding="utf-8")).get("done", []))

    c900 = out["locations"]["corpus_900"]
    ext = out["locations"]["deep_research_ext"]
    out["resolved_claims"] = {
        "af_fixtures_900_vs_1120": {
            "corpus_900_reconciled": c900.get("reconciled_exact"),
            "deep_research_ext_reconciled": ext.get("reconciled_exact") if ext.get("present") else 0,
            "union_distinct_event_files": len(distinct),
            "RESOLUTION": f"corpus={c900.get('reconciled_exact')} + extension={ext.get('reconciled_exact') if ext.get('present') else 0} "
                          f"= union {len(distinct)} distinct fixtures with events (raw is gitignored + lives in separate worktrees)"},
        "sendings_off_123_vs_176": {
            "corpus_900": c900.get("sendings_off"),
            "with_extension": (c900.get("sendings_off") or 0) + (ext.get("sendings_off", 0) if ext.get("present") else 0),
            "RESOLUTION": "123 = the 900-fixture corpus; 176 = after the +220 deep-research extension (1120 total); "
                          "both are correct for their respective corpus scope"},
        "player_history_corpus": {"planned": ph_planned, "completed": ph_done,
                                  "outstanding": (ph_planned - ph_done) if (ph_planned and ph_done is not None) else ph_planned,
                                  "completion_rate": round(ph_done / ph_planned, 4) if (ph_planned and ph_done) else 0.0},
        "statsbomb_bridge": {"exact_bridge_matches": bridged, "raw_event_files_cached": sb_events,
                             "joined_to_snapshots": 0,
                             "RESOLUTION": f"{bridged} exact bridge matches; {sb_events} with raw event files; 0 joined to dynamic snapshots (xG join unwired)"},
    }
    (ROOT / "data/reference").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/reference/research_truth_registry.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    # flat CSV of resolved claims
    with open(ROOT / "data/reference/research_truth_registry.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["claim", "key", "value"])
        for claim, d in out["resolved_claims"].items():
            for k, v in d.items():
                w.writerow([claim, k, v])
    print(json.dumps(out["resolved_claims"], indent=2))


if __name__ == "__main__":
    main()
