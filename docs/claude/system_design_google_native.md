# ARROWOW STUDIO — SYSTEM DESIGN (GOOGLE-NATIVE)
## Autonomous 30-Second UGC Video Factory · Agent Orchestration Architecture
*Owner: Claude (technical owner) · Target: Google Vertex AI ecosystem · June 2026*

> ## 🔒 STATUS: LOCKED — approved build blueprint.
> This design is locked as the implementation contract. Build proceeds per **§10 Phased Build
> Order**. Phase 1 (ADK scaffold) is in progress under `app/adk/`.

> **Scope.** This is the production system design for the **selected** path
> (`ideal_status_google_native.md`): a stable, low-cost, production-grade pipeline that turns one
> natural-language scenario into a validated 30-second UGC video, fully on Google Cloud.
> It is grounded in the **current code** (`app/`) — existing providers and Pydantic schemas are
> **reused, not rewritten**. Read `current_status.md` for the as-built baseline this evolves from.

---

## §0 · DESIGN GOALS & THE ONE BIG DECISION

| Goal | How this design achieves it |
|---|---|
| **Stable** | Deterministic orchestration (workflow agents), strict structured outputs, bounded self-healing loops. |
| **Low cost** | Cheap Gemini 3.5 Flash for creative agents; **zero** LLM tokens on routing; Cloud Run scale-to-zero; targeted single-beat regeneration; parallel renders. |
| **Production-grade** | Multimodal critic gate, durable state, observability, secret management, retries on long-running media ops. |

### The one big decision — *deterministic orchestration, not an LLM router*
The pipeline is a **known DAG** (scenario → script → plan → frame → render → composite → critique).
We therefore drive control flow with **Google ADK deterministic workflow agents**
(`SequentialAgent`, `LoopAgent`, `ParallelAgent`) and spend LLM calls **only** on the 6 creative/
critic steps. An LLM "manager" that decides what to do next would add cost, latency, and
non-determinism for no benefit here. **This single choice is what makes the system stable *and*
cheap.** LLM-driven dynamic routing is explicitly rejected for v1.

---

## §1 · FRAMEWORK CHOICE & RATIONALE

### Chosen: **Google ADK (Agent Development Kit)** as the orchestration spine
ADK is Google's code-first, production-ready multi-agent framework. It gives us exactly the
primitives this pipeline needs, natively:
- **Workflow agents** — `SequentialAgent` (assembly line), `LoopAgent` (refine-until-pass),
  `ParallelAgent` (concurrent fan-out).
- **`LlmAgent`** — reasoning agent with `output_schema` (a Pydantic model it must return) and
  `output_key` (auto-writes its result into `session.state`).
- **`BaseAgent`** — subclass for custom control flow (our `DefectRouter`).
- **`FunctionTool`** — wrap any Python function as a callable tool (our media ops).
- **`SessionService` + `session.state`** — first-class shared state (replaces the JSON Blackboard).
- **Deploys to Cloud Run or Vertex AI Agent Engine** with built-in tracing.

### Why not keep the current `google.antigravity` SDK as the spine?
The code today uses the **Antigravity SDK** (`google.antigravity.Agent` / `LocalAgentConfig`,
Gemini 3.5 Flash, `vertex=True`). That SDK is an excellent **single-agent harness** (one agentic
loop + tools + MCP), but it has **no native multi-agent orchestration** — which is why the current
code glues agents together with separate `asyncio.run()` calls and a hand-rolled Blackboard. ADK is
purpose-built for the multi-agent orchestration we need.

**Migration is low-risk** because the Antigravity agents already (a) target Vertex AI and (b) return
**Pydantic structured outputs** — the same two things ADK `LlmAgent` wants. We reuse the schemas
verbatim. *(Antigravity SDK may be retained later for a tool-using research/asset sub-agent; it is
not the orchestration layer.)*

### Separation of concerns (the rule that keeps it stable)
- **LLM = creative reasoning only** → the 6 `LlmAgent`s.
- **Deterministic code = everything else** → control flow (workflow agents) + media ops
  (`FunctionTool`s wrapping Veo/Imagen/TTS/ffmpeg).
- **Never give an `LlmAgent` both an `output_schema` and tools** — a known ADK conflict where the
  model ignores the schema. Our creative agents have schemas and **no** tools; our media work lives
  in tools called by deterministic stages. This cleanly avoids the bug.

---

## §2 · ORCHESTRATION TOPOLOGY (THE AGENT GRAPH)

```
ArrowowDirector  ── root, custom BaseAgent (owns the run, budget, human gates) ──
│
├─ 1. IntakeStage            FunctionTool            → resolve scenario → persona lock
│
├─ 2. PreProductionLoop      LoopAgent (max 3)       → refine script until critic approves
│      ├─ StrategistAgent        LlmAgent · StrategyResponse        (Gemini 3.5 Flash)
│      ├─ ScriptwriterAgent      LlmAgent · ScriptResponse          (Gemini 3.5 Flash)
│      └─ TextCriticAgent        LlmAgent · TextCriticResponse      (Gemini 3.5 Flash)
│                                 └─ escalate_or_continue() → sets loop-exit on approve
│
├─ 3. VisualPlanningSequence SequentialAgent
│      ├─ StoryboardAgent        LlmAgent · StoryboardResponse  (5-beat sheet: Hook/Intro/Action/Proof/CTA)
│      ├─ WardrobeAgent          LlmAgent · WardrobeLocationResponse
│      └─ ShotPromptAgent        LlmAgent · BeatPromptsResponse (per-beat prompts + sync/seed policy)
│
├─ 4. ReferenceFrameStage    FunctionTool → Imagen   → one canonical persona anchor (reused for all beats)
│
├─ 5. MediaProductionParallel ParallelAgent          → fan out the 5 beats concurrently
│      ├─ render_beat(Hook)      FunctionTool → Veo 3.1   seed=LOCK   sync=native
│      ├─ render_beat(Intro)     FunctionTool → Veo 3.1   seed=LOCK   sync=native
│      ├─ render_beat(Action)    FunctionTool → Veo 3.1   seed=None   sync=voiceover
│      ├─ render_beat(Proof)     FunctionTool → Veo 3.1   seed=None   sync=voiceover
│      ├─ render_beat(CTA)       FunctionTool → Veo 3.1   seed=LOCK   sync=native
│      └─ synthesize_voiceover   FunctionTool → Cloud TTS (for Action+Proof voiceover track)
│
├─ 6. CompositorStage        FunctionTool → ffmpeg    → transitions + audio mux → master.mp4
│
└─ 7. ProductionCriticLoop   LoopAgent (max 3)        → critique → targeted regen until pass
       ├─ VideoCriticAgent       LlmAgent (multimodal · Gemini 3.1 Pro) · VideoCriticResponse
       └─ DefectRouter           custom BaseAgent      → map each defect to a targeted fix or exit
```

**Beat → policy mapping** (drives `render_beat` arguments; from `ideal_status_google_native.md` §03):

| Beat | Camera | Seed | Sync mode | Engine call |
|---|---|---|---|---|
| Hook (0–3s) | C2 | **LOCK (427819)** | Veo native sync | `render_beat("hook", …, seed=LOCK, sync_mode="native")` |
| Intro (3–10s) | C1 | **LOCK** | Veo native sync | `render_beat("intro", …, seed=LOCK, sync_mode="native")` |
| Action (10–20s) | C4 | None | Cloud TTS voiceover | `render_beat("action", …, seed=None, sync_mode="voiceover")` |
| Proof (20–27s) | C3 | None | Cloud TTS voiceover | `render_beat("proof", …, seed=None, sync_mode="voiceover")` |
| CTA (27–30s) | C1 | **LOCK** | Veo native sync | `render_beat("cta", …, seed=LOCK, sync_mode="native")` |

**Human validation gates** (the single-gate-per-step model) are owned by `ArrowowDirector`: after
stages 2, 3, 4, and 6 it emits a validation event (approve / one-line refine). In autonomous mode
the gates auto-approve unless the cost ledger or critic escalates.

---

## §3 · CLASS & MODULE SPECIFICATION

Proposed module layout (new ADK app under `app/adk/`, reusing existing `app/providers` & schemas):

```
app/
├─ providers/                # REUSED AS-IS — live_providers.py (Imagen, Veo, TTS)
├─ agents/                   # REUSED — Pydantic schemas migrate to schemas.py
└─ adk/
   ├─ orchestrator.py        # ArrowowDirector(BaseAgent) — builds & runs the graph
   ├─ creative_agents.py     # factory fns → the 6 LlmAgents (schema + output_key, NO tools)
   ├─ schemas.py             # Pydantic data contracts (reuse + extend)
   ├─ tools/
   │   ├─ media_tools.py     # FunctionTools wrapping providers (frame/render/voiceover)
   │   └─ compositor.py      # composite_timeline() — ffmpeg transition + mux engine
   ├─ state/
   │   ├─ session.py         # SessionService wiring + state-key contract (replaces blackboard.py)
   │   └─ cost_ledger.py     # CostLedgerCallback (reuses cost_ledger.py logic) + budget guard
   ├─ callbacks.py           # before_model / after_tool callbacks (cost, RAI retry, logging)
   └─ app.py                 # FastAPI / `adk api_server` entrypoint for Cloud Run
```

### Core classes

```python
# app/adk/orchestrator.py
class ArrowowDirector(BaseAgent):
    """Root agent. Owns the end-to-end run: assembles the workflow graph, enforces
    human-validation gates, applies the cost-ledger budget guard, and returns the
    final master.mp4 URI + QA report. Deterministic — no LLM reasoning of its own."""
    def __init__(self, session_service: SessionService): ...
    async def _run_async_impl(self, ctx: InvocationContext):  # ADK entrypoint
        # 1 intake → 2 pre-prod loop → 3 visual plan → 4 ref frame
        # → 5 parallel render → 6 composite → 7 critic loop
        ...

# app/adk/creative_agents.py  — factories, each returns a schema-bound LlmAgent (no tools)
def build_strategist()  -> LlmAgent  # output_schema=StrategyResponse,        output_key="strategy"
def build_scriptwriter()-> LlmAgent  # output_schema=ScriptResponse,          output_key="script"
def build_text_critic() -> LlmAgent  # output_schema=TextCriticResponse,      output_key="text_critic"
def build_storyboard()  -> LlmAgent  # output_schema=StoryboardResponse,      output_key="storyboard"
def build_wardrobe()    -> LlmAgent  # output_schema=WardrobeLocationResponse,output_key="wardrobe"
def build_shot_prompt() -> LlmAgent  # output_schema=BeatPromptsResponse,     output_key="beat_prompts"
def build_video_critic()-> LlmAgent  # multimodal (Gemini 3.1 Pro), VideoCriticResponse, output_key="video_critic"

# app/adk/orchestrator.py  — custom control agents
class DefectRouter(BaseAgent):
    """Reads VideoCriticResponse.defects and dispatches the cheapest fix per defect:
       identity_drift → re-render that beat w/ reinforced lock + same seed
       artifact       → re-render that beat w/ seed+1 + tighter negative prompt
       lip_sync       → shorten/re-script that synced beat (native ceiling)
       pacing         → trim the offending beat
       (no defects)   → escalate_action='exit' to end the LoopAgent."""
    async def _run_async_impl(self, ctx): ...
```

### Why each agent type was chosen
| Node | ADK type | Reason |
|---|---|---|
| Director | `BaseAgent` (custom) | needs bespoke control: gates, budget guard, final assembly |
| PreProduction | `LoopAgent` | script must iterate until the Text Critic approves (≤3) |
| Visual planning | `SequentialAgent` | strict order; each step feeds the next |
| 6 creative agents | `LlmAgent` + `output_schema` | structured reasoning; **no tools** (avoids the schema/tool bug) |
| Media production | `ParallelAgent` | 5 beats are independent → render concurrently (huge wall-clock win) |
| Production critique | `LoopAgent` | critique → targeted regen → re-critique until pass (≤3) |
| Defect routing | `BaseAgent` (custom) | deterministic mapping defect→fix; no LLM needed |

---

## §4 · TOOL CONTRACTS (CLEARLY DEFINED FUNCTIONS)

Every media operation is a deterministic **`FunctionTool`** wrapping an **existing provider method**
(`app/providers/live_providers.py`). Signatures are explicit so a human can read the structure at a
glance. Each writes its result into `session.state` via `tool_context`.

```python
# app/adk/tools/media_tools.py

def generate_reference_frame(prompt: str, persona_lock: str,
                             tool_context: ToolContext) -> dict:
    """Create the ONE canonical persona anchor frame, reused across every beat.
    Wraps ImagenProvider.generate_image (model: gemini-3.1-flash-image).
    Returns: {"uri": <local/gcs path>, "status": "success"|"failed"}."""

def render_beat(beat_id: str, prompt: str, sync_mode: str,
                seed: int | None, tool_context: ToolContext) -> dict:
    """Render one 8s beat with Veo 3.1. beat_id ∈ {hook,intro,action,proof,cta}.
    sync_mode: 'native' (on-camera dialogue, seed-locked) | 'voiceover' (masked, seed=None).
    Wraps VeoVideoProvider.generate_video(prompt, reference_image, output_dir, seed).
    Handles the long-running op (poll/await). Returns: {"uri","status","beat_id"}."""

def synthesize_voiceover(text: str, voice_id: str,
                         tool_context: ToolContext) -> dict:
    """Generate the B-roll voiceover track (Action+Proof). voice_id default 'en-AU-Neural2-A'.
    Wraps GoogleTTSProvider.generate_audio. Returns: {"uri","status"}."""

# app/adk/tools/compositor.py

def composite_timeline(beats: list[dict], audio: list[dict],
                       transitions: list[str], tool_context: ToolContext) -> dict:
    """Assemble the 5 beats into a 30s master via ffmpeg: programmed transitions
    (match-cut / whip-pan motion-mask / xfade) + audio mux (native A-roll audio +
    Cloud TTS voiceover over B-roll). Replaces the old bare `concat` in production_stage.py.
    Returns: {"final_uri": <path>, "duration_s": float, "status": ...}."""

# app/adk/creative_agents.py (critic implementation detail)

def critique_video(uri: str) -> dict:
    """Multimodal QA with Gemini 3.1 Pro (google.genai, vertexai=True). Returns a
    VideoCriticResponse dict: {"approved": bool, "defects": [...], "score": int}.
    Reuses the existing LiveVideoCritic logic."""
```

### Data contracts (`app/adk/schemas.py`)
Reuse existing Pydantic models from `app/agents/live_agents.py`:
`StrategyResponse`, `ScriptResponse`, `TextCriticResponse`, `StoryboardResponse`,
`WardrobeLocationResponse`. Two changes:

```python
# EXTEND VisualPromptResponse → per-beat prompts for the 5-beat timeline
class BeatPrompt(BaseModel):
    beat_id: str            # hook | intro | action | proof | cta
    camera: str             # C1..C4
    sync_mode: str          # native | voiceover
    seed_locked: bool
    prompt: str
    dialogue_or_vo: str

class BeatPromptsResponse(BaseModel):
    reference_frame_prompt: str
    beats: list[BeatPrompt] # exactly 5

# NEW structured critic output (kills the relaxed free-text critic)
class Defect(BaseModel):
    type: str               # lip_sync | identity_drift | artifact | pacing
    segment: str            # hook | intro | action | proof | cta
    severity: int           # 1..5

class VideoCriticResponse(BaseModel):
    approved: bool
    defects: list[Defect]
    production_grade_score: int  # 0..10
```

---

## §5 · STATE & DATA FLOW

The custom JSON **Blackboard** (`app/kernel/blackboard.py`) is replaced by ADK **`session.state`**,
preserving the same key contract so the data model is familiar:

```
session.state = {
  "metadata":      {...},  "brief":      {...},  "character":   {...},
  "strategy":      {...},  "script":     {...},  "text_critic": {...},   # written by output_key
  "storyboard":    {...},  "wardrobe":   {...},  "beat_prompts":{...},
  "reference_frame":{uri}, "beats":      [{beat_id,uri}...],  "voiceover": {uri},
  "production":    {final_uri}, "video_critic": {...},  "cost_ledger": {...},
}
```

- **Creative agents** write via `output_key` (ADK auto-saves the structured result).
- **Tools** read inputs and write outputs via `tool_context.state[...]`.
- **Durable persistence** (production):
  - **Cloud Run** → a **Firestore-backed `SessionService`** (custom) so runs survive restarts and a
    scaled-to-zero service.
  - **Agent Engine** → `VertexAiSessionService` (managed sessions/memory) if we adopt that runtime.
- **DRY_RUN parity:** an `InMemorySessionService` keeps the fast, free local loop the current code
  relies on.

---

## §6 · GCP DEPLOYMENT TOPOLOGY (LOW-COST, PRODUCTION-GRADE)

```
                         ┌──────────────────────────────────────────────┐
   user scenario ───────▶│  Cloud Run (scale-to-zero)                    │
   + validation events   │  ADK app  ·  ArrowowDirector  ·  FastAPI      │
                         └───────┬───────────────┬───────────────┬───────┘
                                 │               │               │
                    Vertex AI ───┤               │               ├─── Secret Manager
                    • Gemini 3.5 Flash (agents)   │               │     (SA key — no repo file)
                    • Gemini 3.1 Pro (critic)     │               │
                    • Veo 3.1 (video)             │               ├─── Firestore
                    • Imagen / Flash Image        │               │     (session.state + cost ledger)
                    • Cloud TTS                   │               │
                                                  │               └─── Cloud Trace + Logging
                            Cloud Tasks / Workflows│                     (ADK tracing, audit)
                            (async Veo fan-out,    │
                             retries, long ops) ◀──┘
                                 │
                            GCS bucket  arrowow-videos-{project}
                            (inputs / renders / 30s finals)
```

### Why this topology
- **Cloud Run, scale-to-zero** — a UGC factory runs in **bursts**; paying only for request duration
  (and $0 at idle) is the lowest-cost production runtime. Hosts the ADK app behind FastAPI /
  `adk api_server`.
- **Long-running Veo ops (1–3 min each)** — `render_beat` submits and polls. For the 5-beat fan-out
  we use **`ParallelAgent`** (concurrent polling → ~1 clip's wall-clock, not 5×). At higher volume,
  offload to **Cloud Tasks / Cloud Workflows** so a single Cloud Run request isn't billed while
  idling on polls, and retries are managed.
- **Firestore** — durable `session.state` + cost ledger; cheap, serverless, survives scale-to-zero.
- **Secret Manager** — credentials move here; **the committed `google-credentials.json` is
  eliminated** (rotate the leaked key first — `current_status.md` §8). The Cloud Run service runs as
  a **least-privilege service account** (Vertex User, Storage Object Admin on the one bucket,
  Firestore User, Secret Accessor).
- **GCS** — reuse the existing `arrowow-videos-{project}` bucket the Veo provider already targets.
- **Cloud Trace + Logging** — ADK emits spans per agent/tool; gives per-stage latency/cost audit.

### Documented alternative — **Vertex AI Agent Engine** (managed runtime, scale path)
Managed sessions/memory and deployment, at higher cost: **$0.0864/vCPU-hr + $0.0090/GB-hr**, session
storage **$0.30/GiB-month**, events **$0.25/1k**. Choose this when we want managed memory/identity
and can accept the always-warm-ish cost. **For v1 low-cost, Cloud Run wins.** *(Note: Vertex AI was
rebranded "Gemini Enterprise Agent Platform" at Next 2026 — same services, new umbrella name.)*

---

## §7 · COST MODEL & LOW-COST LEVERS

**Per-30s-video estimate** (real 2026 rates; one clean pass):

| Item | Qty | Unit | Subtotal |
|---|---|---|---|
| Veo 3.1 video | 5 beats × 8s = 40s | ~$0.15/s (fast mode) | **~$6.00** |
| Imagen reference frame | 1 | ~$0.03 | ~$0.03 |
| Gemini 3.5 Flash (5 creative agents) | ~few k tokens | ~$ negligible | ~$0.01 |
| Gemini 3.1 Pro critique | 1 video | per-token (vision) | ~$0.05–0.20 |
| Cloud TTS voiceover | ~300 chars | $0.000016/char | ~$0.005 |
| Cloud Run + Firestore + GCS | per run | scale-to-zero | ~$0.01–0.05 |
| **Total (happy path)** | | | **≈ $6.1–6.4 / 30s video** |

> Reality check vs current ledger: the hardcoded `$0.07/5s` understates Veo ~10×. The real driver is
> **video seconds**, so every lever below targets *reducing wasted Veo seconds*.

**Low-cost levers (build these in):**
1. **Deterministic routing** — zero LLM tokens spent deciding control flow.
2. **Flash-first** — only the vision critic uses Pro; the 5 creative agents use cheap Flash.
3. **Targeted regeneration** — `DefectRouter` re-renders **only the failing beat**, never the whole
   30s. One bad beat = ~$1.2 to fix, not ~$6.
4. **Parallel fan-out** — cuts wall-clock (and Cloud Run billed time) ~5×.
5. **Veo fast mode + 8s cap discipline** — never over-generate.
6. **Budget guard** — `CostLedgerCallback` halts a run before it blows past a per-video cap
   (replace the old hard `>2 videos` cap with a **per-video seconds budget**, e.g. 60s incl. retries).
7. **Scale-to-zero** — $0 when idle.

---

## §8 · MIGRATION MAP (CURRENT → TARGET)

| Current (`app/…`) | Target (`app/adk/…`) | Action |
|---|---|---|
| `main.py` (linear gates) | `orchestrator.py` `ArrowowDirector` + workflow agents | Replace glue with ADK graph |
| `agents/live_agents.py` `Live*` classes | `creative_agents.py` `LlmAgent` factories | Reuse system prompts + **reuse Pydantic schemas** |
| `agents/live_agents.py` Pydantic models | `schemas.py` | Move as-is; extend `VisualPromptResponse`→`BeatPromptsResponse`; add `VideoCriticResponse` |
| `providers/live_providers.py` | `tools/media_tools.py` `FunctionTool`s | **Wrap, don't rewrite** — providers stay |
| `kernel/production_stage.py` (concat) | `tools/compositor.py` `composite_timeline` | Replace bare concat with transition engine |
| `kernel/blackboard.py` | `state/session.py` (ADK `SessionService`) | Same key contract, durable backend |
| `kernel/cost_ledger.py` | `state/cost_ledger.py` callback | Reuse logic; run as ADK callback + budget guard |
| `kernel/approval_gate.py` | Director validation events | Terminal `Y/N` → single-gate-per-step events |
| `agents/live_agents.py` `clean_and_parse_json` + `main.py` key-probing | *(deleted)* | ADK `output_schema` enforces shape (see `ideal_status_*` §08) |

**What is explicitly preserved:** the three provider classes, the GCS bucket convention, the seed
value `427819`, the RAI filter-bypass dictionary, and the A-Roll/B-Roll + 5-beat doctrine.

---

## §9 · END-TO-END SEQUENCE (HAPPY PATH)

```
1. User: "30s ad for our new running leggings, energetic, gym setting."
2. ArrowowDirector → IntakeStage: resolve persona (sienna_fitness_01), write brief+character.
3. PreProductionLoop:
     Strategist → hook/angle/CTA → Scriptwriter → script (A-roll + B-roll VO split)
     → TextCritic → approved? yes → exit loop.            [gate: validate script]
4. VisualPlanningSequence:
     Storyboard (5 beats) → Wardrobe → ShotPrompt (BeatPromptsResponse: 5 beats + ref-frame prompt).
                                                          [gate: validate plan]
5. ReferenceFrameStage → generate_reference_frame → canonical anchor.png.
                                                          [gate: validate frame]
6. MediaProductionParallel (concurrent):
     render_beat(hook,intro,cta: seed=LOCK, native) ‖ render_beat(action,proof: seed=None, VO)
     ‖ synthesize_voiceover(action+proof text).
7. CompositorStage → composite_timeline → 30s master.mp4 (transitions + audio mux).
                                                          [gate: validate cut]
8. ProductionCriticLoop:
     VideoCritic (Gemini 3.1 Pro) → VideoCriticResponse.
     DefectRouter: no defects → exit. (else: targeted re-render of failing beat → recompose → re-critique)
9. ArrowowDirector → return {final_uri, qa_report, cost_breakdown}.  ✅ 30s asset delivered.
```

---

## §10 · PHASED BUILD ORDER

| Phase | Deliverable | Done when |
|---|---|---|
| **0 · Hygiene** | Secret Manager + key rotation; `.gitignore`; commit current work | leaked key dead; clean repo |
| **1 · ADK scaffold** | `adk/` app, `ArrowowDirector`, InMemory SessionService, DRY_RUN parity | empty graph runs end-to-end with mocks |
| **2 · Creative agents** | Migrate 6 `LlmAgent`s + `schemas.py`; delete JSON-parse fallbacks | structured outputs, 0 parse failures / 20 runs |
| **3 · Media tools** | `media_tools.py` FunctionTools over providers; ParallelAgent render | 5 beats render concurrently |
| **4 · Compositor** | `composite_timeline` (transitions + mux); full 30s assembly | seamless 30s master, no bare cuts |
| **5 · Critic loop** | `VideoCriticResponse` + `DefectRouter` targeted regen | unattended pass on 8/10 scenarios |
| **6 · Deploy** | Cloud Run + Firestore SessionService + Cloud Tasks for Veo; tracing | production run from a single API call |

---

## §11 · OPEN RISKS & MITIGATIONS

| Risk | Mitigation |
|---|---|
| **Veo long ops** (1–3 min) exceed a Cloud Run request | Parallel fan-out now; Cloud Tasks/Workflows at scale; idempotent op-name tracking in Firestore |
| **ADK `output_schema` + tools conflict** | Creative agents have schemas and **no tools**; tools live in deterministic stages |
| **RAI safety filters** block fitness prompts | Keep the filter-bypass dictionary; A-roll "safe string" override; critic re-route on empty Veo response |
| **Native lip-sync ceiling** | Duration discipline + B-roll masking (native doctrine); escalate to `ideal_status_hybrid.md` (Sync.so) only if sync alone fails acceptance |
| **Cold-start latency** (scale-to-zero) | min-instances=0 default; bump to 1 for latency-sensitive demos; renders dominate latency anyway |
| **Cost runaway** | `CostLedgerCallback` per-video seconds budget halts the run; targeted single-beat regen |

---

## §12 · QUICK-REFERENCE — THE STRUCTURE IN ONE GLANCE

```
FRAMEWORK   Google ADK (deterministic workflow agents) on Vertex AI
RUNTIME     Cloud Run (scale-to-zero)  ·  Firestore state  ·  GCS assets  ·  Secret Manager
ROOT        ArrowowDirector(BaseAgent) — owns run, gates, budget
CONTROL     LoopAgent (script + critic)  ·  SequentialAgent (visual plan)  ·  ParallelAgent (5 beats)
LLM AGENTS  6 total — 5× Gemini 3.5 Flash (creative) + 1× Gemini 3.1 Pro (vision critic); schema-bound, NO tools
TOOLS       generate_reference_frame · render_beat · synthesize_voiceover · composite_timeline · critique_video
            (all FunctionTools wrapping EXISTING providers in app/providers/live_providers.py)
STATE       ADK session.state (same keys as old Blackboard) → Firestore
COST        ~$6/30s video; levers: deterministic routing, Flash-first, targeted regen, parallel, scale-to-zero
DOCTRINE    5-beat timeline · seed-lock A-roll · Latent-Space Casting · voiceover-masked B-roll · structured self-healing
```

---
*This design realizes `ideal_status_google_native.md`. If native lip-sync proves insufficient, the
same ADK graph upgrades to the Hybrid escalation path (`ideal_status_hybrid.md`) by swapping the
`render_beat`/lip-sync tools — no orchestration change required.*
