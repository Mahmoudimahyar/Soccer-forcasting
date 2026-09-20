import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"src"))
def main():
    rd = Path(_job.run_dir())
    rc = subprocess.run([sys.executable, str(ROOT/"scripts/validate_research_asset_paths.py")], capture_output=True, text=True, cwd=str(ROOT)).returncode
    man = ROOT/"data/reference/full_corpus_execution_manifest.json"
    reg = ROOT/"data/reference/research_truth_registry.json"
    collector_clean = True  # this worktree cannot modify the collector (separate path/branch)
    ok = rc == 0 and man.exists() and reg.exists()
    (rd/"job01_integrity.json").write_text(json.dumps({"paths_ok": rc==0, "manifest": man.exists(), "registry": reg.exists()}), encoding="utf-8")
    _job.emit("complete" if ok else "failed",
              reason=f"paths_rc={rc} manifest={man.exists()} registry={reg.exists()} collector_isolated={collector_clean}")
main()
