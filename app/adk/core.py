"""
Arrowow Studio — Interim Orchestration Core (ADK-shaped)
========================================================

Phase 1 scaffold. These primitives intentionally mirror the *semantics* and *API
shape* of Google ADK (`google.adk`) so the orchestration graph defined in
`orchestrator.py` can later be re-backed by real ADK with a thin adapter swap and
no change to the graph topology.

WHY A SHIM (read this before "fixing" it):
  - `google-adk` is not yet installed in the project venv, and a true ADK run needs
    a live model backend even to exercise the graph. Phase 1's acceptance criterion
    is "empty graph runs end-to-end with mocks" — this core delivers that today with
    ZERO external dependencies (pydantic only), without touching the working pipeline
    in app/agents, app/kernel, app/providers.

MIGRATION TO REAL ADK (Phase 6 / deploy):
  - BaseAgent           -> google.adk.agents.BaseAgent
  - SequentialAgent     -> google.adk.agents.SequentialAgent
  - LoopAgent           -> google.adk.agents.LoopAgent
  - ParallelAgent       -> google.adk.agents.ParallelAgent
  - LlmAgent            -> google.adk.agents.LlmAgent (output_schema + output_key)
  - FunctionTool        -> google.adk.tools.FunctionTool
  - InvocationContext   -> google.adk.agents.InvocationContext (ctx.session.state)
  - InMemorySessionService -> google.adk.sessions.InMemorySessionService
                              (prod: VertexAiSessionService or Firestore-backed)

The graph in orchestrator.py only depends on these names, so swapping the import
of this module for the ADK equivalents is the entire migration surface.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Session + invocation context (mirrors ADK ctx.session.state)
# ---------------------------------------------------------------------------
class Session:
    """Holds the shared, mutable state dict for one production run."""

    def __init__(self, session_id: str, state: dict):
        self.id = session_id
        self.state = state


class InvocationContext:
    """Passed to every agent's run(). `ctx.state` is the shared session state.

    In real ADK this is `ctx.session.state`; we expose `.state` directly for
    convenience and keep `.session` for parity.
    """

    def __init__(self, session: Session, mode: str, logger: Callable[[str], None]):
        self.session = session
        self.mode = mode  # DRY_RUN | LLM_ONLY | LIVE_MEDIA
        self._log = logger

    @property
    def state(self) -> dict:
        return self.session.state

    def log(self, message: str) -> None:
        self._log(message)


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------
class BaseAgent:
    """Abstract unit of work in the graph. Subclass and implement `run`."""

    def __init__(self, name: str):
        self.name = name

    async def run(self, ctx: InvocationContext) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# LLM agent (structured output + output_key, mirrors ADK LlmAgent)
# ---------------------------------------------------------------------------
class LlmAgent(BaseAgent):
    """A reasoning agent that returns a Pydantic-validated dict and writes it to
    `ctx.state[output_key]` (exactly like ADK's output_schema + output_key).

    DRY_RUN/LLM_ONLY without a wired live_fn uses `mock_fn(state) -> dict`.
    LIVE uses `live_fn(state) -> dict`. The result is validated against
    `output_schema` before being stored — a schema violation raises, which is the
    intended "structured outputs only" contract (no free-text JSON fallback).
    """

    def __init__(
        self,
        name: str,
        output_schema,
        output_key: str,
        mock_fn: Callable[[dict], dict],
        live_fn: Optional[Callable[[dict], dict]] = None,
        instruction: str = "",
    ):
        super().__init__(name)
        self.output_schema = output_schema
        self.output_key = output_key
        self.mock_fn = mock_fn
        self.live_fn = live_fn
        self.instruction = instruction

    async def run(self, ctx: InvocationContext) -> dict:
        use_live = ctx.mode in ("LLM_ONLY", "LIVE_MEDIA") and self.live_fn is not None
        raw = (self.live_fn if use_live else self.mock_fn)(ctx.state)
        if asyncio.iscoroutine(raw):  # live_fn may be async (awaits the LLM backend)
            raw = await raw
        validated = self.output_schema(**raw).model_dump()
        ctx.state[self.output_key] = validated
        ctx.log(f"    [LlmAgent:{self.name}] -> state['{self.output_key}'] "
                f"({'live' if use_live else 'mock'})")
        return validated


# ---------------------------------------------------------------------------
# Function tool (deterministic media op, mirrors ADK FunctionTool used as a stage)
# ---------------------------------------------------------------------------
class FunctionTool(BaseAgent):
    """Wraps a plain function `fn(ctx) -> Any` as a graph stage. Used for the
    deterministic media operations (frame / render / voiceover / composite)."""

    def __init__(self, name: str, fn: Callable[[InvocationContext], Any]):
        super().__init__(name)
        self.fn = fn

    async def run(self, ctx: InvocationContext) -> Any:
        result = self.fn(ctx)
        if asyncio.iscoroutine(result):
            result = await result
        return result


# ---------------------------------------------------------------------------
# Workflow agents (deterministic control flow — the cost/stability lever)
# ---------------------------------------------------------------------------
class SequentialAgent(BaseAgent):
    """Runs sub-agents one after another, sharing the same context/state."""

    def __init__(self, name: str, sub_agents: list[BaseAgent]):
        super().__init__(name)
        self.sub_agents = sub_agents

    async def run(self, ctx: InvocationContext) -> None:
        ctx.log(f"  [Sequential:{self.name}]")
        for agent in self.sub_agents:
            await agent.run(ctx)


class ParallelAgent(BaseAgent):
    """Runs sub-agents concurrently (asyncio.gather). Used to fan out the 5 beats.

    NOTE: real ADK ParallelAgent runs branches in isolated state then merges; here
    sub-agents share state but each writes to its own key (e.g. beats[beat_id]), so
    there is no contention under single-threaded asyncio.
    """

    def __init__(self, name: str, sub_agents: list[BaseAgent]):
        super().__init__(name)
        self.sub_agents = sub_agents

    async def run(self, ctx: InvocationContext) -> None:
        ctx.log(f"  [Parallel:{self.name}] fan-out x{len(self.sub_agents)}")
        await asyncio.gather(*(agent.run(ctx) for agent in self.sub_agents))


class LoopAgent(BaseAgent):
    """Repeats its sub-agents until `should_exit(state)` is true or max_iterations
    is reached (mirrors ADK LoopAgent / a while-loop refinement)."""

    def __init__(
        self,
        name: str,
        sub_agents: list[BaseAgent],
        max_iterations: int,
        should_exit: Callable[[dict], bool],
    ):
        super().__init__(name)
        self.sub_agents = sub_agents
        self.max_iterations = max_iterations
        self.should_exit = should_exit

    async def run(self, ctx: InvocationContext) -> None:
        for i in range(1, self.max_iterations + 1):
            ctx.log(f"  [Loop:{self.name}] iteration {i}/{self.max_iterations}")
            for agent in self.sub_agents:
                await agent.run(ctx)
            if self.should_exit(ctx.state):
                ctx.log(f"  [Loop:{self.name}] exit condition met on iteration {i}")
                return
        ctx.log(f"  [Loop:{self.name}] reached max_iterations ({self.max_iterations})")


# ---------------------------------------------------------------------------
# Session service (mirrors ADK InMemorySessionService)
# ---------------------------------------------------------------------------
class InMemorySessionService:
    """Creates/holds sessions in memory (DRY_RUN parity). Production swaps this for
    a Firestore-backed service (Cloud Run) or VertexAiSessionService (Agent Engine)."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self, session_id: str, initial_state: dict) -> Session:
        session = Session(session_id, initial_state)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)
