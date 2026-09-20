"""JOB13: machine + human run summary. Aggregates every job's JSON output into research_findings.json and
a human draft_report.md. All outputs are research-only; no model is trained for promotion; frozen prospective
predictions (M1-M5 / B1) are untouched; trading disabled; no Odds API. research_only / experimental /
not_runtime_approved / not_trade_eligible / not_live_eligible."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job


def main():
    rd = Path(_job.run_dir())

    def load(n):
        p = rd / n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    summary = {k: load(v) for k, v in {
        "manifest": "job02_manifest.json", "quality": "job04_quality.json", "linkage": "job05_linkage.json",
        "statsbomb_xg": "job06_statsbomb_xg.json", "wdl": "job07_wdl.json", "nextgoal": "job08_nextgoal.json",
        "discipline": "job09_discipline.json", "xg_fusion": "job10_xg_fusion.json",
        "ablation": "job11_ablation.json", "calibration": "job12_calibration.json"}.items()}
    (rd / "research_findings.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    q = summary.get("quality") or {}; lk = summary.get("linkage") or {}
    w = summary.get("wdl") or {}; n = summary.get("nextgoal") or {}
    xf = summary.get("xg_fusion") or {}; ab = summary.get("ablation") or {}
    lines = ["# Player-Impact + xG Fusion Run — Draft Findings",
             "(research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible)", ""]
    man = summary.get("manifest") or {}
    if man:
        lines.append(f"- Player-history manifest: {man.get('n_fixtures')} fixtures (target {man.get('fixture_target')}), "
                     f"seed={man.get('seed')}, leagues={man.get('leagues')}.")
    if q:
        lines.append(f"- Corpus: {q.get('fixtures')} fixtures, exact reconcile {q.get('exact_rate')}, "
                     f"sendings_off {q.get('sendings_off')} ({q.get('intl_fixtures')} intl / {q.get('club_fixtures')} club).")
    if lk:
        lines.append(f"- Exact player-id linkage: match_rate {lk.get('match_rate')} "
                     f"(matched {lk.get('exact_id_matched')}, unmatched {lk.get('unmatched_no_id')}, "
                     f"ambiguous {lk.get('ambiguous_dup_id')}); rule={lk.get('linkage_rule')}.")
    if w:
        lines.append("- In-play W/D/L (P1-P4) leader by RPS: " + str(w.get("leader_by_rps")) + "; models: "
                     + ", ".join(f"{k}={v['rps']}" for k, v in (w.get("models") or {}).items()))
    if n:
        lines.append(f"- Next-goal (N0-N3) leader by Brier: {n.get('leader_by_brier')}.")
    if xf:
        if "models" in xf:
            lines.append("- xG-fusion (X0-X3) leader by RPS: " + str(xf.get("leader_by_rps")) + "; models: "
                         + ", ".join(f"{k}={v['rps']}" for k, v in (xf.get("models") or {}).items()))
    else:
        lines.append("- xG-fusion (X0-X3): SKIPPED (StatsBomb bridge not built).")
    if ab:
        lines.append(f"- Ablation: full RPS {ab.get('full_model_rps')}; most-valuable group {ab.get('most_valuable_group')} "
                     f"(player_count = player-impact channel).")
    disc = summary.get("discipline") or {}
    lines.append("- Discipline C1: " + ((disc.get("C1_skip_reason")) or "run (>=150 sendings-off)"))
    lines.append("")
    lines.append("All outputs research-only; no model trained for promotion; frozen prospective M1-M5/B1 untouched; "
                 "Odds API not called; trading disabled (paper-only).")
    (rd / "draft_report.md").write_text("\n".join(lines), encoding="utf-8")
    _job.emit("complete", reason="machine + human summary written")


main()
