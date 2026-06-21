from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

@pytest.fixture
def seed_root() -> Path:
    return ROOT
