"""Phase 4/5 (real data): acquire a BOUNDED SoccerNet-Echoes sample (CC BY 4.0, open) via huggingface_hub,
extract <=10 games, normalize through the canonical adapter, and emit a REAL source-quality audit.
Raw arrow + processed sample are gitignored; only the manifest + audit numbers are committed.
historical_weak_supervision_only by construction (broadcast time; no publication_time). research_only.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary.adapters import soccernet_echoes as SNE  # noqa: E402
from wcdrawlab.research.commentary import source_registry as SR  # noqa: E402

RAW = ROOT / "data/raw/commentary/soccernet_echoes"
PROC = ROOT / "data/processed/commentary"
FILENAME = "whisper_v1/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"


def _read_arrow(path):
    import pyarrow as pa
    try:
        return pa.ipc.open_file(pa.memory_map(str(path), "r")).read_all()
    except Exception:
        with pa.OSFile(str(path), "rb") as f:
            return pa.ipc.open_stream(f).read_all()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-games", type=int, default=10)
    a = ap.parse_args()
    # gate: must be an open download-allowed source
    if SR.classification("soccernet_echoes") != "open_research_download_allowed":
        print("BLOCKED by rights gate"); return
    RAW.mkdir(parents=True, exist_ok=True); PROC.mkdir(parents=True, exist_ok=True)

    from huggingface_hub import hf_hub_download
    print("downloading SoccerNet-Echoes whisper_v1 arrow (CC BY 4.0, ~108MB, one-time)...")
    fp = hf_hub_download(repo_id="SoccerNet/SN-echoes", repo_type="dataset", filename=FILENAME,
                         local_dir=str(RAW))
    sha = hashlib.sha256(Path(fp).read_bytes()).hexdigest()
    tbl = _read_arrow(fp)
    games = tbl.column("game").to_pylist()
    sample_games = list(dict.fromkeys(games))[:a.max_games]   # first <=N distinct games (bounded)
    sg = set(sample_games)
    cols = {c: tbl.column(c).to_pylist() for c in ("game", "segment_index", "start_time", "end_time", "text")}

    per_game = {}
    for i in range(len(cols["game"])):
        g = cols["game"][i]
        if g not in sg:
            continue
        per_game.setdefault(g, []).append({"start_time": cols["start_time"][i],
                                           "end_time": cols["end_time"][i], "text": cols["text"][i]})

    retrieval = datetime.now(timezone.utc).isoformat()
    records, quals = [], Counter()
    for g, segs in per_game.items():
        recs = SNE.to_records(segs, canonical_match_id=g, language="multi", retrieval_time_utc=retrieval)
        for r in recs:
            quals[r.text_quality_status] += 1
            quals[r.causal_eligibility_status] += 1
        records.extend(recs)
    # processed sample (gitignored): derived labels only (no raw text retained in committed artifacts)
    import pandas as pd
    df = pd.DataFrame([{"canonical_match_id": r.canonical_match_id, "segment": r.source_order_index,
                        "match_clock_second": r.match_clock_second, "text_quality": r.text_quality_status,
                        "causal_eligibility": r.causal_eligibility_status,
                        "content_hash": r.source_content_hash, "norm_len": len(r.normalized_text or "")}
                       for r in records])
    df.to_parquet(PROC / "soccernet_echoes_sample.parquet", index=False)

    manifest = {"source": "soccernet_echoes", "license": "cc-by-4.0",
                "attribution": "Data provided by SoccerNet (SN-echoes, CC BY 4.0)",
                "file": FILENAME, "file_sha256": sha, "retrieval_time_utc": retrieval,
                "total_segments_in_corpus": len(cols["game"]),
                "games_sampled": len(sample_games), "segments_sampled": len(records),
                "publication_time_present": False,
                "causal_eligibility": "historical_weak_supervision_only",
                "quality_breakdown": dict(quals)}
    (ROOT / "notes/research/commentary_soccernet_sample_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"sampled {len(sample_games)} games / {len(records)} segments | sha256={sha[:12]}")
    print("quality:", dict(quals))
    print("manifest -> notes/research/commentary_soccernet_sample_manifest.json")


if __name__ == "__main__":
    main()
