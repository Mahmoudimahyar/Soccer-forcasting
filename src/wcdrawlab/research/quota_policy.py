"""Dynamic collector-aware API-Football reserve. Replaces the static 25% rule. research_only.
research_reserve = max(200, ceil(1.5 * collector_expected_requests) + 50)."""
from __future__ import annotations
import math
from pathlib import Path
import yaml
_CFG = Path(__file__).resolve().parents[3] / "configs/research_quota_policy.yaml"
def load_policy():
    return yaml.safe_load(_CFG.read_text(encoding="utf-8"))
def dynamic_reserve(collector_expected_requests: int | None = None) -> int:
    pol = load_policy()
    c = pol.get("collector_expected_requests", 0) if collector_expected_requests is None else collector_expected_requests
    return max(int(pol.get("hard_floor", 200)), math.ceil(1.5 * int(c)) + 50)
def research_budget(remaining: int, max_requests: int, collector_expected_requests: int | None = None):
    """Return (budget, reserve). budget = min(max_requests, remaining - reserve), never below 0."""
    reserve = dynamic_reserve(collector_expected_requests)
    return max(0, min(int(max_requests), int(remaining) - reserve)), reserve
