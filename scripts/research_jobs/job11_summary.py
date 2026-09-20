import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    rd = Path(_job.run_dir())
    def load(n):
        p = rd/n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    summary = {k: load(v) for k,v in {"quality":"job03_quality.json","readiness":"job05_readiness.json",
        "wdl":"job06_wdl.json","nextgoal":"job07_nextgoal.json","discipline":"job08_discipline.json",
        "transfer":"job09_transfer.json","calibration_failure":"job10_calibration_failure.json"}.items()}
    (rd/"research_findings.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # human draft
    q=summary.get("quality") or {}; w=summary.get("wdl") or {}; n=summary.get("nextgoal") or {}
    lines=["# Deep Research Run — Draft Findings (research_only / experimental / not_runtime_approved)",""]
    lines.append(f"- Corpus: {q.get('fixtures')} fixtures, exact reconcile {q.get('exact_rate')}, sendings_off {q.get('sendings_off')}.")
    if w: lines.append(f"- W/D/L leader by RPS: {w.get('leader_by_rps')}; models: "+", ".join(f"{k}={v['rps']}" for k,v in (w.get('models') or {}).items()))
    if n: lines.append(f"- Next-goal leader by Brier: {n.get('leader_by_brier')}.")
    t=summary.get("transfer"); 
    if t: lines.append(f"- Club->international transfer: {t.get('verdict')} (intl-only {t.get('intl_only_W3_rps')} vs club-aux {t.get('club_aux_W3_rps')}).")
    lines.append("- DISCIPLINE C1: "+((summary.get('discipline') or {}).get('C1_skip_reason') or "run"))
    lines.append("")
    lines.append("All outputs research-only; no model trained for promotion; B1/M1-M5/M2 frozen; trading disabled.")
    (rd/"draft_report.md").write_text("\n".join(lines), encoding="utf-8")
    _job.emit("complete", reason="machine + human summary written")
main()
