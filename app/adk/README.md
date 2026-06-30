# `app/adk/` — Arrowow Studio Orchestration (Google-Native)

Phase 1 scaffold of the agent orchestration described in
[`docs/claude/system_design_google_native.md`](../../docs/claude/system_design_google_native.md).

## Run it (DRY_RUN, no GCP, no new deps)

```bash
# from the project root
python -m app.adk.run_dry --scenario "30s ad for our new running leggings, gym setting"
```

Expected: the full 7-stage graph runs end-to-end with mocks, writes
`output/{session_id}/session_state.json`, and prints a `PASS` summary with the 5 beats
and a (mock) 30s master URI.

## Structure (maps 1:1 to system design §2/§3)

| File | Role |
|---|---|
| `core.py` | Interim ADK-shaped primitives (BaseAgent, Sequential/Loop/Parallel, LlmAgent, FunctionTool, SessionService) |
| `schemas.py` | Pydantic data contracts (reused + BeatPromptsResponse, VideoCriticResponse) |
| `creative_agents.py` | 6 LlmAgent factories — DRY_RUN mocks **+ live async backends** |
| `prompts.py` | System-instruction builders + prohibited-terms + filter-bypass dictionary |
| `llm_backend.py` | Async `structured_generate()` — Vertex Gemini via **google.genai** (response_schema), **structured-output only (no regex fallback)** |
| `tools/media_tools.py` | FunctionTools wrapping existing providers (frame / render_beat / voiceover) |
| `tools/compositor.py` | Transition + audio-mux assembler (replaces bare ffmpeg concat) |
| `state/session.py` | State key contract + persistence (replaces blackboard.py) |
| `state/cost_ledger.py` | Per-run video-seconds budget guard + cost breakdown |
| `orchestrator.py` | `ArrowowDirector` — assembles & runs the deterministic graph + gates |
| `app.py` / `run_dry.py` | Builder + runnable DRY_RUN harness |
| `selftest.py` | No-GCP regression: `python -m app.adk.selftest` (DRY_RUN + live-path + filter-bypass + no-fallback) |

## The deterministic graph

```
Intake → PreProductionLoop(Strategist→Scriptwriter→TextCritic, ≤3)
       → VisualPlanning(Storyboard→Wardrobe→ShotPrompt)
       → ReferenceFrame → MediaProductionParallel(render×5 ‖ voiceover)
       → Compositor → ProductionCriticLoop(VideoCritic→DefectRouter, ≤3)
```

Control flow is deterministic (zero LLM tokens on routing); LLM calls happen only in
the 6 creative/critic agents. This is the core stability + low-cost lever.

## Migrating to real Google ADK (build Phase 6 / deploy)

`core.py` is an interim shim with the **same API shape** as `google.adk`. Migration is a
contained swap — the graph in `orchestrator.py` is unchanged:

| Interim (`core.py`) | Real ADK |
|---|---|
| `BaseAgent` / `SequentialAgent` / `LoopAgent` / `ParallelAgent` | `google.adk.agents.*` |
| `LlmAgent(output_schema, output_key, ...)` | `google.adk.agents.LlmAgent` |
| `FunctionTool` | `google.adk.tools.FunctionTool` |
| `InvocationContext.state` | `ctx.session.state` |
| `InMemorySessionService` | `InMemorySessionService` (dev) / `VertexAiSessionService` or Firestore (prod) |

Then wire the LIVE backends: `creative_agents.*.live_fn` → existing prompts in
`app/agents/live_agents.py`; the media tools already call `app/providers/live_providers.py`
in `LIVE_MEDIA` mode. Install with `pip install -r app/adk/requirements-adk.txt`.

## Status / next phases

- ✅ Phase 1 — scaffold + DRY_RUN parity.
- ✅ Phase 2 — live creative agents (google.genai structured output, filter-bypass). Live-validated.
- ✅ Phase 3 — character bible + realism profile, live media tools, QA agent + adversarial
  refinement loop, post-production compositor, full cost system. DRY_RUN verified; **one live Veo
  beat rendered** ($1.20). New modules: `profiles/` (character/sienna/realism/registry), `qa.py`,
  `improvement.py`, enriched `state/cost_ledger.py`, `probe_live_beat.py`.
- ⏳ Phase 3b — full 5-beat live render (~$6) + live QA loop (pending review of the single beat).
- ⏭ Phase 6 — deploy to Cloud Run + Firestore SessionService.

### Cost & live testing
- `python -m app.adk.probe_live_beat [beat]` — render ONE live Veo beat (cost-gated, ~$1.20).
- Every live call is logged to `output/<session>/cost_log.jsonl`; cumulative dev spend vs the
  $100 ceiling is tracked in `output/_dev_spend_ledger.json` with a hard guard before any render.
