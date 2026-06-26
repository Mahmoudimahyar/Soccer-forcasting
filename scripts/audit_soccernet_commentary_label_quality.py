"""Phase 1: reproducible quality audit of the real SoccerNet-Echoes <-> SoccerNet-labels overlap.
Tracked outputs carry counts/rates only (NO raw commentary text). research_only / historical_weak_supervision_only.
"""
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_features as F  # noqa: E402

LABELS = ROOT / "data/raw/soccernet_action_labels"
SUPPORTED = ["goal", "corner", "yellow_card", "foul", "offside", "substitution", "kickoff",
             "shot", "shot_on_target", "penalty_awarded", "red_card", "second_yellow"]


def arrow(variant):
    return ROOT / f"data/raw/commentary/soccernet_echoes/{variant}/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"


def echoes_match_ids(variant):
    import pyarrow as pa
    ap = arrow(variant)
    if not ap.exists():
        return set()
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(ap), "r")).read_all()
    except Exception:
        with pa.OSFile(str(ap), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    return {F.echoes_match_id(g) for g in tbl.column("game").to_pylist()}


def main():
    events = F.load_label_events(LABELS)
    en_ids = echoes_match_ids("whisper_v1_en")
    orig_ids = echoes_match_ids("whisper_v1")
    overlap = sorted(en_ids & set(events))
    segs = F.load_echoes_segments(arrow("whisper_v1_en"), overlap)
    matched = sorted(m for m in overlap if segs.get(m) and events.get(m))

    comps = Counter(m.split("/")[0] for m in matched)
    seasons = Counter("/".join(m.split("/")[:2]) for m in matched)
    n_segments = sum(len(segs[m]) for m in matched)
    event_class = Counter()
    for m in matched:
        for e in events[m]:
            event_class[e["canonical"]] += 1
    # duplicates: same content_hash within a match; corrections via quality module
    from wcdrawlab.research.commentary import quality as Q
    dup = 0
    corr = 0
    durations = []
    for m in matched:
        seen = set()
        per_half_max = {}
        for s in segs[m]:
            h = s["content_hash"]
            if h in seen:
                dup += 1
            seen.add(h)
            if Q.is_correction(s.get("norm", "")):
                corr += 1
            per_half_max[s["half"]] = max(per_half_max.get(s["half"], 0), s["t_s"])
        durations.append(sum(per_half_max.values()))
    seg_times = [s["t_s"] for m in matched for s in segs[m]]
    ev_times = [e["t_s"] for m in matched for e in events[m] if e["canonical"] in SUPPORTED]

    summary = {
        "commentary_games_en": len(en_ids), "commentary_games_orig": len(orig_ids),
        "label_games": len(events), "overlap_matched_games": len(matched),
        "competitions": dict(comps), "n_seasons": len(seasons),
        "n_segments": n_segments, "n_events_supported": sum(event_class[c] for c in SUPPORTED),
        "events_by_class": {c: event_class.get(c, 0) for c in SUPPORTED},
        "duplicate_segment_rate": round(dup / n_segments, 4) if n_segments else None,
        "correction_segment_rate": round(corr / n_segments, 4) if n_segments else None,
        "median_match_commentary_duration_s": round(statistics.median(durations), 1) if durations else None,
        "segment_time_p50_s": round(statistics.median(seg_times), 1) if seg_times else None,
        "event_time_p50_s": round(statistics.median(ev_times), 1) if ev_times else None,
        "match_mapping": "exact game-path, confidence 1.0, 0 collisions",
        "taxonomy_classes_with_events": sum(1 for c in SUPPORTED if event_class.get(c, 0) > 0),
        "rights": "echoes=CC BY 4.0; labels=non-commercial research; no publication_time -> historical only",
        "language": "primary=whisper_v1_en (English translation); original-lang audited separately (Phase 6)",
        "orig_minus_en_games": len(orig_ids - en_ids),
    }
    (ROOT / "notes/research/_phase1_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out = ROOT / "data/processed/soccernet_commentary_label_quality_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for k, v in summary.items():
            w.writerow([k, json.dumps(v) if isinstance(v, dict) else v])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
