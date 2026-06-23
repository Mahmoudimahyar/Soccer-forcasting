"""Phase 2: acquire OFFICIAL SoccerNet action-spotting Labels-v2.json via the official SoccerNet pip
package (labels only; NDA/password is for VIDEOS, not labels). No password used, no bypass. Raw goes to
gitignored data/raw/soccernet_action_labels/. Videos/features/360 are NEVER downloaded."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/soccernet_action_labels"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--splits", nargs="+", default=["test"]); a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    from SoccerNet.Downloader import SoccerNetDownloader
    d = SoccerNetDownloader(LocalDirectory=str(RAW))
    # labels only; no password (videos need the NDA password, labels do not)
    d.downloadGames(files=["Labels-v2.json"], split=list(a.splits))
    n = len(list(RAW.rglob("Labels-v2.json")))
    print(f"downloaded {n} Labels-v2.json files (no password) into gitignored {RAW}")

if __name__ == "__main__":
    main()
