"""Adapter registry (Phase 3). Only the mock adapter is registered. NOTHING here is runtime/trade/live
eligible — these are research-only prep modules that must never enter execution paths."""
from __future__ import annotations

from .mock_provider import MockProvider

_REGISTRY = {}


def register(adapter_cls):
    if getattr(adapter_cls, "RUNTIME_ELIGIBLE", False) or getattr(adapter_cls, "TRADE_ELIGIBLE", False):
        raise ValueError("licensed-event adapters may not declare runtime/trade eligibility")
    _REGISTRY[adapter_cls.provider_name] = adapter_cls
    return adapter_cls


def get(name):
    return _REGISTRY.get(name)


def list_adapters():
    return sorted(_REGISTRY)


def is_runtime_eligible(name) -> bool:
    return False  # always — research-only plane


register(MockProvider)
