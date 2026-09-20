"""Canonical model-ID registry for the event-process intelligence phase.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

These are the *only* sanctioned model identifiers for this phase, taken verbatim from the spec. The
engine does not fit models here -- it produces the leakage-safe feature snapshots that the EP fit/eval
jobs (ep_job08..ep_job15) consume. Centralizing the IDs prevents ad-hoc names leaking into artifacts.
"""
from __future__ import annotations

# forward-chain / LOCO W-D-L family
EVENT_PROCESS_MODELS = [
    "research.event_process.e0",  # baseline (no event-process features)
    "research.event_process.e1",
    "research.event_process.e2",
    "research.event_process.e3",
    "research.event_process.e4",
    "research.event_process.e5",
    "research.event_process.e6",
    "research.event_process.e7",
    "research.event_process.e8",
    "research.event_process.e9",
]

# next-goal family
NEXT_GOAL_MODELS = [
    "research.next_goal.q0",
    "research.next_goal.q1",
    "research.next_goal.q2",
    "research.next_goal.q3",
    "research.next_goal.q4",
]

# near-term scoring family
SCORING_MODELS = [
    "research.scoring.h0",
    "research.scoring.h1",
    "research.scoring.h2",
    "research.scoring.h3",
]

# discipline family
DISCIPLINE_MODELS = [
    "research.discipline.y0",
    "research.discipline.y1",
    "research.discipline.y2",
]

ALL_MODELS = EVENT_PROCESS_MODELS + NEXT_GOAL_MODELS + SCORING_MODELS + DISCIPLINE_MODELS


def is_canonical(model_id: str) -> bool:
    return model_id in ALL_MODELS


def assert_canonical(model_id: str) -> str:
    if model_id not in ALL_MODELS:
        raise ValueError(f"non-canonical model id {model_id!r}; allowed: {ALL_MODELS}")
    return model_id
