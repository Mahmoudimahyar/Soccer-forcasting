"""Phase 3 (xG bridge): acquire ONLY already-open StatsBomb Open Data for the senior MEN'S
INTERNATIONAL competitions that also exist in the API-Football corpus, so we can build an EXACT
match bridge and derive causal in-play xG state features for the overlapping games.

Scope (target competitions — all already public under the StatsBomb Open Data license):
  - FIFA World Cup 2018  (competition_id 43, season_id 3)
  - FIFA World Cup 2022  (competition_id 43, season_id 106)
  - UEFA Euro 2020       (competition_id 55, season_id 43)
  - UEFA Euro 2024       (competition_id 55, season_id 282)
  - Copa America 2024    (competition_id 223, season_id 282)

What it acquires (BOUNDED, resumable, raw is gitignored — NEVER committed):
  - competitions.json (catalogue, for provenance/sanity)
  - matches/<cid>/<sid>.json for each target competition-season (the match list — small)
  - events/<match_id>.json for a BOUNDED SAMPLE of matches per competition (default 12/comp),
    selected deterministically by sorted match_id so the sample is reproducible.

Transport: urllib over the PUBLIC raw.githubusercontent.com paths (github.com/statsbomb/open-data).
No API key, no auth, no secrets. Read-only GET. Polite delay between requests. Resumable: a file
already on disk (non-empty + valid JSON) is skipped.

Data provided by StatsBomb under the StatsBomb Open Data license (CC BY-NC-SA spirit). Non-commercial
research use with attribution; raw is kept local/gitignored and never redistributed here.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/statsbomb_open"            # gitignored — never commit
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
USER_AGENT = "wcdrawlab-research/1.0 (StatsBomb open-data, non-commercial research; resumable GET)"

# Senior MEN'S INTERNATIONAL competitions present in BOTH StatsBomb open data AND the API-Football corpus.
TARGETS = [
    {"label": "FIFA World Cup 2018", "competition_id": 43, "season_id": 3},
    {"label": "FIFA World Cup 2022", "competition_id": 43, "season_id": 106},
    {"label": "UEFA Euro 2020", "competition_id": 55, "season_id": 43},
    {"label": "UEFA Euro 2024", "competition_id": 55, "season_id": 282},
    {"label": "Copa America 2024", "competition_id": 223, "season_id": 282},
]


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 (https only, public data)
        return r.read()


def _valid_json_file(fp: Path) -> bool:
    if not fp.exists() or fp.stat().st_size == 0:
        return False
    try:
        json.loads(fp.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def _fetch_to(url: str, fp: Path, delay: float) -> str:
    """Resumable fetch: return 'cached' | 'fetched' | 'error:<msg>'."""
    if _valid_json_file(fp):
        return "cached"
    fp.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = _get(url)
        # validate it parses as JSON before persisting (avoid writing 404 html)
        json.loads(data.decode("utf-8"))
        fp.write_bytes(data)
        time.sleep(delay)
        return "fetched"
    except urllib.error.HTTPError as e:
        return f"error:http {e.code}"
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}"


def _sha256(fp: Path) -> str:
    return hashlib.sha256(fp.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Acquire bounded StatsBomb open data for the xG bridge.")
    ap.add_argument("--events-per-comp", type=int, default=12,
                    help="bounded number of event JSONs to download per competition (deterministic by match_id)")
    ap.add_argument("--delay", type=float, default=0.2, help="seconds between requests (politeness)")
    ap.add_argument("--matches-only", action="store_true", help="only fetch competitions + match lists (no events)")
    args = ap.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {"base": BASE, "targets": [], "events_per_comp": args.events_per_comp,
                "license": "StatsBomb Open Data (non-commercial research, attribution); raw gitignored"}

    # 1) competitions catalogue (provenance)
    comp_fp = RAW / "competitions.json"
    st = _fetch_to(f"{BASE}/competitions.json", comp_fp, args.delay)
    print(f"competitions.json: {st}")

    total_events = 0
    for t in TARGETS:
        cid, sid = t["competition_id"], t["season_id"]
        m_fp = RAW / "matches" / str(cid) / f"{sid}.json"
        st = _fetch_to(f"{BASE}/matches/{cid}/{sid}.json", m_fp, args.delay)
        if not _valid_json_file(m_fp):
            print(f"  {t['label']}: matches FETCH FAILED ({st}) — skipping")
            manifest["targets"].append({**t, "matches_status": st, "n_matches": 0, "events_sampled": 0})
            continue
        matches = json.loads(m_fp.read_text(encoding="utf-8"))
        match_ids = sorted(int(m["match_id"]) for m in matches)
        print(f"  {t['label']}: matches {st} — {len(match_ids)} matches")

        sampled = 0
        if not args.matches_only:
            take = match_ids if args.events_per_comp <= 0 else match_ids[: args.events_per_comp]
            for mid in take:
                e_fp = RAW / "events" / f"{mid}.json"
                est = _fetch_to(f"{BASE}/events/{mid}.json", e_fp, args.delay)
                if _valid_json_file(e_fp):
                    sampled += 1
                else:
                    print(f"    event {mid}: {est}")
            total_events += sampled
        manifest["targets"].append({
            **t, "matches_status": st, "n_matches": len(match_ids),
            "matches_sha256": _sha256(m_fp), "events_sampled": sampled,
            "events_per_comp_cap": args.events_per_comp,
        })
        print(f"    events sampled: {sampled}")

    man_fp = RAW / "acquisition_manifest.json"
    man_fp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote acquisition manifest -> {man_fp} (gitignored)")
    print(f"total event JSONs on disk this run scope: {total_events}")
    print("NOTE: raw StatsBomb data is gitignored and must NEVER be committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
