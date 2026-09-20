"""Phase 4: package a rights-safe SILVER-LABEL data product for APPROVED classes only.
Importable core (record construction + guards) is unit-tested; main() reads the gate decision + the
gitignored emissions and writes a gitignored derived dataset + a TRACKED manifest/data-card. NO raw text.
research_only / historical_weak_supervision_only / not_live_eligible / not_runtime_approved / not_trade_eligible.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = "precision_v2"
FORBIDDEN = {"text", "normalized_text", "norm", "raw", "commentary_text", "utterance"}
SOURCE_RIGHTS = "echoes=CC_BY_4.0;soccernet_labels=non_commercial_research"


def to_silver_record(em, source_hash=""):
    """Build one schema-compliant silver record from an emission dict (NO raw text)."""
    return {
        "canonical_match_id": em["match_id"],
        "commentary_record_id": em["commentary_record_id"],
        "commentary_content_hash": em["content_hash"],
        "source_id": "soccernet_echoes+soccernet_labels",
        "source_rights_classification": SOURCE_RIGHTS,
        "competition": em["competition"], "season": em["season"],
        "event_class": em["event_class"],
        "confidence_score": round(float(em["confidence"]), 4),
        "confidence_tier": "high",
        "event_time_s": round(float(em["event_time_s"]), 2),
        "alignment_delta_s": round(float(em["alignment_delta_s"]), 2),
        "parser_model_version": MODEL_VERSION,
        "source_hash": source_hash,
        "causal_status": "historical_weak_supervision_only",
        "live_eligibility": False, "runtime_eligibility": False, "trading_eligibility": False,
    }


def assert_no_raw_text(records):
    for r in records:
        bad = FORBIDDEN & set(r.keys())
        if bad:
            raise AssertionError(f"raw-text field leaked into silver dataset: {bad}")


def filter_approved(records, approved_classes):
    return [r for r in records if r["event_class"] in set(approved_classes)]


def assert_all_historical_non_live(records):
    for r in records:
        assert r["causal_status"] == "historical_weak_supervision_only"
        assert r["live_eligibility"] is False and r["runtime_eligibility"] is False and r["trading_eligibility"] is False


def _approved_from_gate():
    gate = ROOT / "notes/research/commentary_silver_label_gate.json"
    if not gate.exists():
        return []
    g = json.loads(gate.read_text(encoding="utf-8"))
    return [c for c, v in g.get("classes", {}).items()
            if v.get("label") == "silver_label_approved_for_historical_research"]


def main():
    approved = _approved_from_gate()
    emfile = ROOT / "data/processed/silver_emissions.json"  # gitignored, produced by generate_*.py
    emissions = json.loads(emfile.read_text(encoding="utf-8")) if emfile.exists() else []
    records = filter_approved([to_silver_record(e, source_hash="precision_v2") for e in emissions], approved)
    assert_no_raw_text(records)
    assert_all_historical_non_live(records)
    out = ROOT / "data/processed/soccernet_silver_labels.parquet"  # gitignored
    if records:
        import pandas as pd
        pd.DataFrame(records).to_parquet(out, index=False)
    man = {"approved_classes": approved, "n_records": len(records),
           "by_class": {c: sum(1 for r in records if r["event_class"] == c) for c in approved},
           "parser_model_version": MODEL_VERSION, "rights": SOURCE_RIGHTS,
           "causal_status": "historical_weak_supervision_only", "live_eligible": False}
    (ROOT / "notes/research/commentary_silver_label_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    print("silver release:", json.dumps(man))


if __name__ == "__main__":
    main()
