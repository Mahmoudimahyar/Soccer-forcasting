"""Phase 6: build a reproducible, rights-safe DERIVED weak-supervision dataset from the SoccerNet
commentary<->label alignment. NO raw commentary text in tracked outputs (only content hashes + derived
fields). Raw processed parquet is gitignored; a tracked manifest holds aggregate counts only.
historical_weak_supervision_only / not_live_eligible / not_runtime_approved / not_trade_eligible.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_alignment as A  # noqa: E402

PARSER_VERSION = "soccernet_ws_v1"
FORBIDDEN = {"text", "normalized_text", "norm", "raw", "commentary_text"}
WINDOW = 45.0


def emit_records(events_by_match, segments_by_match, match_ids, offset_s=0.0,
                 source_hash="", rights="soccernet_labels=non_commercial_research;echoes=cc_by_4_0"):
    """Return derived weak-supervision records (dicts). NO raw text — content hashes only."""
    out = []
    for mid in match_ids:
        comp = mid.split("/")[0]
        season = mid.split("/")[1] if len(mid.split("/")) > 1 else ""
        evs, segs = events_by_match.get(mid, []), segments_by_match.get(mid, [])
        seg_h = {}
        for s in segs:
            seg_h.setdefault(s["half"], []).append(s)
        for i, e in enumerate(evs):
            ct = e["canonical"]
            if ct not in A.KEYWORD_RULES:
                continue
            et = e["t_s"] + offset_s
            kw = [s for s in seg_h.get(e["half"], [])
                  if abs(s["t_s"] - et) <= WINDOW and A.text_claims_event(s.get("norm", ""), ct)]
            if not kw:
                continue
            near = min(kw, key=lambda s: abs(s["t_s"] - et))
            dt = near["t_s"] - et
            out.append({
                "canonical_match_id": mid,
                "canonical_commentary_id": f"{mid}#h{e['half']}#{near['t_s']:.1f}",
                "commentary_content_hash": near.get("content_hash", ""),
                "source_id": "soccernet_echoes+soccernet_labels",
                "competition": comp, "season": season,
                "match_clock_start_s": round(near["t_s"], 2), "match_clock_end_s": round(near["t_s"], 2),
                "event_label": ct, "event_label_confidence": round(1.0 - min(abs(dt), WINDOW) / WINDOW, 3),
                "event_time_s": round(e["t_s"], 2), "alignment_time_delta_s": round(dt, 2),
                "alignment_confidence": round(max(0.0, 1.0 - abs(dt) / WINDOW), 3),
                "source_timing_status": "broadcast_clock_only_no_publication_time",
                "causal_eligibility": "historical_weak_supervision_only",
                "rights_classification": rights,
                "parser_version": PARSER_VERSION, "source_hash": source_hash,
            })
    return out


def assert_no_raw_text(records):
    for r in records:
        bad = FORBIDDEN & set(r.keys())
        if bad:
            raise AssertionError(f"raw-text field leaked into derived dataset: {bad}")


def main():
    from wcdrawlab.research.commentary import soccernet_features as F
    import os
    _v=os.environ.get("ECHOES_VARIANT","whisper_v1_en")
    arrow = ROOT / f"data/raw/commentary/soccernet_echoes/{_v}/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"
    labels = ROOT / "data/raw/soccernet_action_labels"
    events = F.load_label_events(labels)
    import pyarrow as pa
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(arrow), "r")).read_all()
    except Exception:
        with pa.OSFile(str(arrow), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    echoes_mids = {F.echoes_match_id(g) for g in tbl.column("game").to_pylist()}
    overlap = sorted(echoes_mids & set(events.keys()))
    if not overlap:
        print("no overlap -> no derived records (blocked at data level)"); return
    segs = F.load_echoes_segments(arrow, overlap)
    matched = sorted([m for m in overlap if segs.get(m) and events.get(m)])
    recs = emit_records(events, segs, matched)
    assert_no_raw_text(recs)
    import pandas as pd
    out = ROOT / "data/processed/soccernet_weak_supervision.parquet"
    pd.DataFrame(recs).to_parquet(out, index=False) if recs else None
    man = {"n_records": len(recs), "n_matched_games": len(matched),
           "by_event": {}, "parser_version": PARSER_VERSION,
           "causal_eligibility": "historical_weak_supervision_only", "live_eligible": False}
    for r in recs:
        man["by_event"][r["event_label"]] = man["by_event"].get(r["event_label"], 0) + 1
    Path(ROOT / "notes/research/soccernet_weak_supervision_manifest.json").write_text(
        json.dumps(man, indent=2), encoding="utf-8")
    print("derived WS records:", len(recs), "->", man["by_event"])


if __name__ == "__main__":
    main()
