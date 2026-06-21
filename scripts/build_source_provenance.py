"""Build data/processed/source_provenance.json: a registry of every external source used,
with content hash, coverage, license, and intended use. Implements the file-level provenance
required by Tier-1 (per-record envelope policy is in notes/research/provenance_policy.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED = "2026-06-20"

SOURCES = [
    {"source_name": "martj42_international_results", "kind": "open_dataset",
     "source_url": "https://raw.githubusercontent.com/martj42/international_results/master/results.csv",
     "local_path": "data/raw/international_results.csv", "license": "CC0 (public domain)",
     "coverage": "all men's internationals 1872-2026", "used_for": "Elo history, 2026 results",
     "leakage_note": "date-only; Elo uses strict <kickoff"},
    {"source_name": "jfjelstul_worldcup_matches", "kind": "open_dataset",
     "source_url": "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/matches.csv",
     "local_path": "data/raw/jf_worldcup_matches.csv", "license": "MIT",
     "coverage": "Men's+Women's WC 1930-2022, group labels", "used_for": "1998-2022 group structure+results",
     "leakage_note": "historical; features derived time-safely"},
    {"source_name": "jfjelstul_worldcup_tournaments", "kind": "open_dataset",
     "source_url": "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/tournaments.csv",
     "local_path": "data/raw/jf_worldcup_tournaments.csv", "license": "MIT",
     "coverage": "WC tournaments metadata 1930-2022", "used_for": "host lookup", "leakage_note": "winner field never used as feature"},
    {"source_name": "football_data_org_wc2026", "kind": "api_snapshot",
     "source_url": "https://api.football-data.org/v4/competitions/WC/matches",
     "local_path": "data/raw/footballdata_wc_2026.json", "license": "football-data.org ToS (keyed)",
     "coverage": "2026 WC group structure+matchday+results (authoritative, live)", "used_for": "2026 table + Elo supplement",
     "leakage_note": "only FINISHED results used for state/Elo"},
    {"source_name": "the_odds_api_2026_live", "kind": "api_snapshot",
     "source_url": "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds",
     "local_path": "data/raw/odds/odds_fifa_world_cup_2026-06-20.json", "license": "the-odds-api.com ToS (keyed)",
     "coverage": "live 2026 pre-match odds (40 events)", "used_for": "market features (B6), blend",
     "leakage_note": "snapshot_time <= kickoff"},
    {"source_name": "the_odds_api_historical", "kind": "api_snapshot",
     "source_url": "https://api.the-odds-api.com/v4/historical/sports/{sport}/odds",
     "local_path": "data/processed/intl_odds_raw.csv", "license": "the-odds-api.com ToS (paid)",
     "coverage": "intl pre-kickoff odds 2021-2025 (WC/Euro/Copa/AFCON/NL/quals); history starts 2020-06",
     "used_for": "beat-market validation", "leakage_note": "pre-kickoff snapshots (~T-90 and closing)"},
    {"source_name": "dato_futbol_fifa_ranking", "kind": "open_dataset",
     "source_url": "https://raw.githubusercontent.com/Dato-Futbol/fifa-ranking/master/ranking_fifa_historical.csv",
     "local_path": "data/raw/fifa_ranking_dato.csv", "license": "open (GitHub), Transfermarkt/FIFA-derived",
     "coverage": "FIFA ranking 1992-2024 monthly", "used_for": "B2 baseline + tested feature (rejected)",
     "leakage_note": "asof release_date <= kickoff"},
    {"source_name": "transfermarkt_dcaribou", "kind": "open_dataset",
     "source_url": "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.duckdb",
     "local_path": "data/raw/transfermarkt.duckdb", "license": "dcaribou/transfermarkt-datasets (CC-BY-NC-SA per repo)",
     "coverage": "players, valuations (time-stamped), lineups; NT comps Copa/AFCON/AsianCup (no WC/Euro lineups)",
     "used_for": "squad-strength feature test (rejected, redundant)", "leakage_note": "valuation date <= match date (ASOF)"},
    {"source_name": "wikipedia_2026_format", "kind": "reference",
     "source_url": "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup",
     "local_path": "data/reference/tiebreak_rules_2026.yaml", "license": "CC-BY-SA",
     "coverage": "2026 format + tiebreak rules", "used_for": "simulator reference / tiebreak provenance",
     "leakage_note": "n/a (rules reference)"},
]


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    out = {"schema_version": "1.0", "generated_at_utc": RETRIEVED, "policy": "notes/research/provenance_policy.md",
           "sources": []}
    for s in SOURCES:
        p = ROOT / s["local_path"]
        rec = dict(s)
        rec["retrieved_at_utc"] = RETRIEVED
        rec["present"] = p.exists()
        rec["bytes"] = p.stat().st_size if p.exists() else 0
        rec["raw_payload_sha256"] = sha256(p)
        rec["quality_status"] = "ok" if p.exists() else "missing"
        out["sources"].append(rec)
    dest = ROOT / "data" / "processed" / "source_provenance.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"wrote {dest} with {len(out['sources'])} sources")
    for r in out["sources"]:
        print(f"  {r['source_name']:<32} present={r['present']} "
              f"{(r['bytes']/1e6):.1f}MB sha={str(r['raw_payload_sha256'])[:12]}")


if __name__ == "__main__":
    main()
