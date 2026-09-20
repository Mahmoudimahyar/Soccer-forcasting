"""Run the DATA-DEPENDENT integration tests (require local gitignored datasets). In a clean worktree these
are skipped by conftest; this runner invokes them explicitly so failures are visible when data is present.
research_only."""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    r = subprocess.run([sys.executable,"-m","pytest","-q","tests/test_inplay_dataset.py","-rs"], cwd=str(ROOT))
    sys.exit(r.returncode)
