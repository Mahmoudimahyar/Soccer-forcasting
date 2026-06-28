"""EV_JOB10 -- decision memo (next-investment).

Synthesizes a NEXT-INVESTMENT decision memo from the consolidated evidence already produced upstream:
  - the 258->58 funnel (the binding constraint is DATA AVAILABILITY: 200 exact-international bridge
    matches lack on-disk StatsBomb events);
  - the match-level power curve (the primary lever is MORE INDEPENDENT INTERNATIONAL MATCHES, not more
    snapshots of the same 58 -- the clustering ceiling);
  - the live-readiness matrix (no source carries an event-publication timestamp -> live needs measured
    provider latency + rights + schema parity, a separate gate).

Reuses the existing next_investment_decision_matrix.json + minimum_evidence_requirements.json where
present. Writes notes/research/EVIDENCE_POWER_DECISION_MEMO.md + a structured JSON. Makes NO purchase
recommendation and NO market/2026 claim; states what evidence each option would require. Honest
data_insufficient if the power + funnel inputs are both absent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    power = _ev.read_ref_json("match_level_power_analysis.json")
    lin = _ev.read_ref_json("evaluation_cohort_lineage.json") or {}
    readiness = _ev.read_ref_json("live_readiness_matrix.json")
    min_req = _ev.read_ref_json("minimum_evidence_requirements.json")
    matrix = _ev.read_ref_json("next_investment_decision_matrix.json")

    if power is None and not lin:
        _ev.emit("data_insufficient",
                 reason="neither power analysis nor cohort lineage present; cannot write a grounded memo")
        return

    fs = lin.get("meta", {}).get("funnel_summary", {})
    needed = (power or {}).get("matches_and_tournaments_needed", {})
    cur58 = (power or {}).get("current_power_at_58_matches", {})

    options = [
        {"option": "acquire_full_statsbomb_event_pull",
         "rationale": f"restores the cohort from {fs.get('residual_population', 58)} toward "
                      f"{fs.get('exact_bridge_population', 258)} exact-international matches "
                      f"(the 200 dropped for missing_statsbomb_events); a DATA-ACQUISITION step, not a "
                      f"modeling change",
         "evidence_required": "the StatsBomb open events for the 200 bridge-exact matches on disk",
         "lever": "more_independent_international_matches (primary power lever)"},
        {"option": "add_more_snapshots_per_match",
         "rationale": "does NOT raise power -- the independent unit is the match; the clustering ceiling "
                      "demonstration shows power is invariant to snapshot inflation on the same 58 matches",
         "evidence_required": "none would help; recorded as a non-lever",
         "lever": "rejected_non_lever"},
        {"option": "pursue_live_eligibility",
         "rationale": "blocked until a provider's real event-publication latency is measured and causally "
                      "gated; offline match-clock replay is not live eligibility",
         "evidence_required": "measured per-event provider latency + data rights + schema parity",
         "lever": "separate_live_gate"},
    ]

    memo = {
        "memo": "evidence_power_next_investment",
        "binding_constraint": "data_availability (missing_statsbomb_events on 200 exact-intl matches)",
        "funnel_summary": fs,
        "power_at_58": cur58,
        "matches_and_tournaments_needed": needed,
        "options": options,
        "reused_artifacts": {
            "next_investment_decision_matrix": bool(matrix),
            "minimum_evidence_requirements": bool(min_req),
            "live_readiness_matrix": bool(readiness),
        },
        "no_purchase_recommendation": True, "no_market_claim": True, "no_2026_claim": True,
        "utc": _ev.utc(), "labels": _ev.LABELS,
    }
    _ev.write_json("ev_decision_memo.json", memo)

    md = [
        "# Evidence-Power Consolidation -- Next-Investment Decision Memo", "",
        f"`{_ev.LABELS}`", "",
        "Synthesized from local consolidated evidence only. No purchase recommendation, no market claim, "
        "no 2026 WC claim.", "",
        "## Binding constraint", "",
        "The residual in-play evaluation cohort is bounded by **data availability**, not modeling. Of "
        f"{fs.get('exact_bridge_population', 258)} exact-international bridge matches, "
        f"**{fs.get('dropped_missing_statsbomb_events', 200)}** drop with reason `missing_statsbomb_events` "
        f"(no StatsBomb event JSON on disk), leaving **{fs.get('residual_population', 58)}** evaluable "
        "matches. This is a preregistered data boundary, not a defect.", "",
        "## Power levers", "",
        "| option | lever | raises power? |", "|---|---|---|",
        "| acquire full StatsBomb event pull | more independent international matches | **yes (primary)** |",
        "| more snapshots per match | clustering ceiling | no (non-lever) |",
        "| pursue live eligibility | separate live gate | n/a (latency/rights/schema) |", "",
        "Match-level power at M=58 (by target absolute-RPS improvement): "
        f"{cur58}", "",
        "## What each option requires", "",
    ]
    for o in options:
        md.append(f"- **{o['option']}** ({o['lever']}): {o['rationale']} _Evidence required:_ "
                  f"{o['evidence_required']}")
    (_ev.NOTES).mkdir(parents=True, exist_ok=True)
    (_ev.NOTES / "EVIDENCE_POWER_DECISION_MEMO.md").write_text("\n".join(md), encoding="utf-8")

    _ev.emit("complete",
             reason=f"decision memo written; binding_constraint=data_availability; "
                    f"residual={fs.get('residual_population')}; primary_lever=more_intl_matches",
             state_updates={"decision_memo_written": True,
                            "binding_constraint": "data_availability"})


main()
