"""
Arrowow Studio — ADK App Builder
================================

Single place that constructs the configured root agent. In Phase 6 this is wrapped by
FastAPI / `adk api_server` for Cloud Run; for now it returns the Director for direct
invocation (see run_dry.py).
"""
from __future__ import annotations

from .orchestrator import ArrowowDirector


def build_director(autonomous: bool = True) -> ArrowowDirector:
    """Construct the root orchestrator with the full graph assembled."""
    return ArrowowDirector(autonomous=autonomous)
