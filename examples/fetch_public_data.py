from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingest import download_default_sources, write_source_registry


def main():
    write_source_registry(ROOT / "data" / "source_registry.json")
    paths = download_default_sources(ROOT, overwrite=False)
    print("Downloaded public sources:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
