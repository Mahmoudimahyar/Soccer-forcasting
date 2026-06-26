"""Phase 4: generate a clean vendor questionnaire (NO credentials, NO account info) that maps every project
acceptance criterion to a question a provider must answer. Output: data_requests/pending/*.yaml + markdown.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QUESTIONNAIRE = {
    "project": "Research-only World Cup / international football forecasting. No live trading; no raw-data "
               "redistribution; no scraping. Derived research outputs only.",
    "rights": [
        "May we store your data locally (append-only) for research?",
        "May we use it for historical research and model training on DERIVED features?",
        "May we publish AGGREGATE derived metrics/labels (no raw data)?",
        "Any restriction on commercial future use? Attribution required?",
        "Raw redistribution: prohibited / conditional? Historical export allowed?",
    ],
    "coverage": [
        "How many complete lineup+substitution matches across men's senior internationals (+ major leagues)?",
        "How many matches carry per-event TIMESTAMPS (match clock + update/publication time)?",
        "How many direct-red / second-yellow examples across your historical coverage?",
        "Which historical seasons carry full event/xG/lineup granularity? Competition IDs?",
        "World Cup + Euro/Copa/AFCON/Asian Cup coverage + depth?",
    ],
    "schema": [
        "Stable unique match IDs and player IDs? Bench/substitute lists included?",
        "Card semantics (yellow / second-yellow / direct-red distinct)?",
        "Shot + shot-location + xG semantics? Position/formation fields?",
        "Substitution semantics (on/off + minute)? Event correction support?",
    ],
    "causal_availability": [
        "Do events carry a source publication time and a provider update time?",
        "Published live latency? Historical vs live feeds clearly distinguished?",
        "Are retrospectively-corrected events ever relabeled as live? (must be no)",
    ],
    "quality": [
        "Score reconciliation guarantees? Event ordering? Duplicate + correction rates? Missingness?",
    ],
    "operational": [
        "Rate limits? Historical backfill practicality? Append-only raw export? Resumability? "
        "Quota budgeting? Documented retry behavior?",
    ],
    "sample_data_request": [
        "20 historical matches (events + lineups + subs + corrections + source timing metadata)",
        "5 live or archived event timelines with publication/update timestamps",
    ],
    "no_credentials_note": "Do NOT send API keys or account credentials in your reply; documentation + a "
                           "sample export are sufficient for evaluation.",
}


def main():
    out = ROOT / "data_requests/pending/structured_event_vendor_questionnaire.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    out.write_text(yaml.safe_dump(QUESTIONNAIRE, sort_keys=False, allow_unicode=True), encoding="utf-8")
    # also a markdown version
    md = ["# Structured Event Provider Questionnaire (no credentials)\n", QUESTIONNAIRE["project"], ""]
    for sec in ("rights", "coverage", "schema", "causal_availability", "quality", "operational",
                "sample_data_request"):
        md.append(f"## {sec}")
        md += [f"- {q}" for q in QUESTIONNAIRE[sec]]
        md.append("")
    md.append(f"> {QUESTIONNAIRE['no_credentials_note']}")
    (ROOT / "data_requests/pending/structured_event_vendor_questionnaire.md").write_text("\n".join(md), encoding="utf-8")
    print("questionnaire written (yaml + md); no credentials included")


if __name__ == "__main__":
    main()
