"""Provider-neutral licensed-event adapter framework (Phase 3).

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. NO real provider client, NO
credentials, NO API calls live here. Mock-only. Must NOT be importable by runtime/trading/Kalshi paths.
"""
from . import contracts, provider_interface, normalization, reconciliation, availability, quality_gate, registry  # noqa: F401

__all__ = ["contracts", "provider_interface", "normalization", "reconciliation", "availability",
           "quality_gate", "registry"]
