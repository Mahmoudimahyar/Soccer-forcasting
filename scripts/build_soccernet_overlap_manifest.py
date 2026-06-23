"""Phase 3: compute the REAL overlap between SoccerNet-Echoes commentary games and the acquired
SoccerNet action-label games, using the deterministic mapper. Writes a tracked aggregate manifest
(game IDs + status only; no raw text). research_only / historical_weak_supervision_only.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_mapping as M  # noqa: E402

ECHOES_ARROW = ROOT / "data/raw/commentary/soccernet_echoes/whisper_v1/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"
LABELS = ROOT / "data/raw/soccernet_action_labels"
OUT = ROOT / "data/processed/soccernet_commentary_action_overlap_manifest.csv"


def echoes_match_id(g: str) -> str:
    """Echoes keys are game/HALF (trailing '/1' or '/2'). Drop a trailing pure-integer segment to get the
    match-level id that joins to SoccerNet labels (which are per-match, not per-half)."""
    parts = str(g).replace("\\", "/").rstrip("/").split("/")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    return "/".join(parts)


def echoes_games():
    import pyarrow as pa
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(ECHOES_ARROW), "r")).read_all()
    except Exception:
        with pa.OSFile(str(ECHOES_ARROW), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    return list(dict.fromkeys(echoes_match_id(g) for g in tbl.column("game").to_pylist()))


def label_games():
    return [str(p.parent.relative_to(LABELS)).replace("\\", "/") for p in LABELS.rglob("Labels-v2.json")]


def main():
    eg, lg = echoes_games(), label_games()
    print(f"echoes games (corpus): {len(eg)} | label games (acquired): {len(lg)}")
    print("echoes sample id:", eg[0] if eg else None)
    print("label  sample id:", lg[0] if lg else None)
    mapping = M.map_games(eg, lg)
    status = {}
    for v in mapping.values():
        status[v["status"]] = status.get(v["status"], 0) + 1
    overlap = [(e, v["label_id"], v["status"], v["confidence"]) for e, v in mapping.items()
               if v["status"] in ("exact", "normalized", "override")]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["echoes_game", "label_game", "status", "confidence"])
        w.writerows(overlap)
    print("status breakdown:", status)
    print(f"OVERLAP (joinable echoes<->label games): {len(overlap)} -> {OUT.name}")
    collisions = M.detect_collisions(lg)
    print("label-side collisions:", len(collisions))


if __name__ == "__main__":
    main()
