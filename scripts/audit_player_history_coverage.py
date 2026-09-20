"""Phase 2: audit COVERAGE & integrity of the player-history corpus and derived priors. Read-only.

Reports, per comp_type: fixtures present, with-events, with-lineups, with-player-ids, with-positions,
with-bench; regulation reconciliation rate (exact vs unresolved); appearance counts; the share of
starting-XI players that are UNKNOWN (no strictly-earlier history) — the cold-start curve; and a
leakage self-check (every prior's contributing appearances are strictly earlier than the match date).
Writes notes/research/player_history_coverage_report.md. NO network; NO Odds API; no key printed.

Run: python scripts/audit_player_history_coverage.py
"""
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import player_history as PH  # noqa: E402
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

RAW_ROOTS = [
    ROOT / "data/raw/player_history_corpus",
    ROOT / "data/raw/api_football_historical_corpus",
    Path("C:/Users/Mahyar/worldcup-api-football-corpus/data/raw/api_football_historical_corpus"),
]
REPORT = ROOT / "notes/research/player_history_coverage_report.md"


def _load_raw():
    fixtures, events, lineups = {}, {}, {}
    for root in RAW_ROOTS:
        if not root.exists():
            continue
        for fp in root.glob("fixtures_*.json"):
            if "events" in fp.name or "lineups" in fp.name:
                continue
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            for fx in p.get("response", []) or []:
                fixtures.setdefault(str((fx.get("fixture") or {}).get("id")), fx)
        for fp in root.glob("fixtures_events_*.json"):
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            fid = (p.get("parameters") or {}).get("fixture")
            if fid is not None:
                events.setdefault(str(fid), p.get("response", []) or [])
        for fp in root.glob("fixtures_lineups_*.json"):
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            fid = (p.get("parameters") or {}).get("fixture")
            if fid is not None:
                lineups.setdefault(str(fid), p.get("response", []) or [])
    return fixtures, events, lineups


def main():
    fixtures, events, lineups = _load_raw()
    cov = defaultdict(lambda: defaultdict(int))
    for fid, fx in fixtures.items():
        ct = PH._comp_type_for_fixture(fx)
        ev = events.get(fid)
        ln = lineups.get(fid)
        cov[ct]["fixtures"] += 1
        cov[ct]["with_events"] += int(ev is not None)
        cov[ct]["with_lineups"] += int(bool(ln) and len(ln) >= 2)
        if ln:
            first_xi = (ln[0].get("startXI") or [{}])
            if first_xi and (first_xi[0].get("player") or {}).get("id") is not None:
                cov[ct]["with_player_ids"] += 1
            if first_xi and (first_xi[0].get("player") or {}).get("pos") is not None:
                cov[ct]["with_positions"] += 1
            if ln[0].get("substitutes"):
                cov[ct]["with_bench"] += 1
        if ev is not None:
            can = RS.canonical_result(fx, ev)
            cov[ct]["reconciled" if can["reconciliation_status"] == "exact" else "unresolved"] += 1

    appearances = PH.build_appearances(fixtures, events, lineups)
    hist = PH.PlayerHistory(appearances)
    by_ct_app = defaultdict(int)
    for a in appearances:
        by_ct_app[a.comp_type] += 1

    # cold-start curve + leakage self-check across all XI players
    unknown = defaultdict(int)
    total_xi = defaultdict(int)
    leak_violations = 0
    ordered = sorted([f for f in fixtures if f in events and f in lineups],
                     key=lambda f: (PH._parse_dt((fixtures[f].get("fixture") or {}).get("date")) or datetime.min, f))
    for fid in ordered:
        fx = fixtures[fid]
        date = PH._parse_dt((fx.get("fixture") or {}).get("date"))
        if date is None:
            continue
        ct = PH._comp_type_for_fixture(fx)
        for tl in lineups[fid]:
            p = HD.parse_lineup(tl)
            for s in p["starters"]:
                pid = s.get("player_id")
                if pid is None:
                    continue
                total_xi[ct] += 1
                pr = hist.prior(pid, date, ct)
                if pr["unknown_player"]:
                    unknown[ct] += 1
                # leakage self-check: no contributing appearance may be dated >= match date
                for ap in hist._by_key.get((ct, pid), []):
                    if ap.match_date >= date and ap.source_hash in pr["source_hashes"]:
                        leak_violations += 1

    lines = ["# Player-History Coverage Report",
             "research_only / not_runtime_approved. Generated by scripts/audit_player_history_coverage.py.",
             "",
             f"- prior_model_version: `{PH.PRIOR_MODEL_VERSION}` parser_version: `{PH.PARSER_VERSION}`",
             f"- leakage self-check (contributing appearance dated >= match date): **{leak_violations} violations**",
             f"- total appearances derived (reconciled-exact fixtures only): {len(appearances)}",
             "",
             "## Coverage by comp_type"]
    for ct in sorted(cov):
        c = cov[ct]
        fxs = c["fixtures"] or 1
        rec = c.get("reconciled", 0)
        rec_den = (c.get("reconciled", 0) + c.get("unresolved", 0)) or 1
        lines += [f"### {ct}",
                  f"- fixtures: {c['fixtures']}; with_events: {c['with_events']}; with_lineups: {c['with_lineups']}",
                  f"- with_player_ids: {c.get('with_player_ids',0)}; with_positions: {c.get('with_positions',0)}; with_bench: {c.get('with_bench',0)}",
                  f"- regulation reconciled exact: {rec}/{rec_den} ({rec/rec_den:.1%}); unresolved: {c.get('unresolved',0)}",
                  f"- appearances: {by_ct_app.get(ct,0)}",
                  f"- starting-XI cold-start (unknown / no prior history): {unknown.get(ct,0)}/{total_xi.get(ct,0)}"
                  + (f" ({unknown.get(ct,0)/total_xi[ct]:.1%})" if total_xi.get(ct) else ""),
                  ""]
    lines += ["## Notes",
              "- Cold-start share is HIGH for the earliest matches in a cohort (no prior history yet) and",
              "  falls as the rolling window accrues appearances — this is expected and is exposed, never hidden.",
              "- Unknown players contribute the shrinkage prior only; they never receive a future-derived value.",
              "- Club and international are reported separately; priors are never pooled across comp_type."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    summary = {"leak_violations": leak_violations, "n_appearances": len(appearances),
               "coverage": {ct: dict(cov[ct]) for ct in cov},
               "cold_start": {ct: {"unknown": unknown.get(ct, 0), "total_xi": total_xi.get(ct, 0)} for ct in cov}}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
