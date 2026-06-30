"""
Arrowow Studio — Session State Contract & Persistence
=====================================================

Replaces app/kernel/blackboard.py. The state dict carries the SAME key contract the
old Blackboard used, so the data model is familiar (system design §5).

In Phase 1 we persist to output/{session_id}/session_state.json (parity with the
current pipeline). Production swaps `persist_state` for a Firestore write (Cloud Run)
or relies on VertexAiSessionService (Agent Engine).
"""
from __future__ import annotations

import json
import os
import uuid

from ..core import InMemorySessionService, Session

# Canonical state keys written across the graph.
STATE_KEYS = [
    "metadata", "brief", "character",          # intake
    "strategy", "script", "text_critic",       # pre-production
    "storyboard", "wardrobe", "beat_prompts",  # visual planning
    "reference_frame", "beats", "voiceover",   # media production
    "production", "video_critic",              # composite + critique
    "cost_ledger", "errors",
]


def new_initial_state(session_id: str, mode: str, scenario: str) -> dict:
    """Build the starting state dict for one run."""
    return {
        "metadata": {
            "session_id": session_id,
            "mode": mode,
            "status": "intake",
            "current_stage": "initialized",
            "scenario": scenario,
        },
        "brief": {},
        "character": {},
        "strategy": {},
        "script": {},
        "text_critic": {},
        "storyboard": {},
        "wardrobe": {},
        "beat_prompts": {},
        "reference_frame": {},
        "beats": {},
        "voiceover": {},
        "production": {},
        "video_critic": {},
        "cost_ledger": {
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "image_generations": 0,
            "video_generations": 0,
            "video_seconds": 0,
            "tts_characters": 0,
            "regenerations": 0,
            "budget_status": "within_limit",
        },
        "errors": [],
    }


def make_session(mode: str, scenario: str, session_id: str | None = None) -> Session:
    """Create an in-memory session with initialized state."""
    session_id = session_id or str(uuid.uuid4())
    service = InMemorySessionService()
    return service.create_session(session_id, new_initial_state(session_id, mode, scenario))


def persist_state(state: dict) -> str:
    """Write the full state to output/{session_id}/session_state.json. Returns path."""
    session_id = state.get("metadata", {}).get("session_id", "unknown")
    out_dir = os.path.join("output", session_id)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "session_state.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
    return path
