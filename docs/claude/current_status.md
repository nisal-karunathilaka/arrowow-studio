# ARROWOW STUDIO — CURRENT STATUS
## As-Built Audit & Reality Check
*Maintained by: Claude (technical + creative owner) · Last audited: June 18, 2026 · Branch audited: `feature/b-roll-architecture` (working tree)*

> This document is the **canonical, code-verified snapshot** of what Arrowow Studio actually is
> today — not what it aspires to be. Every claim below is traced to a specific file, function, or
> commit. The aspirational target lives in the companion `ideal_status_*.md` documents.
> It supersedes `docs/gemini/current_status.md` (kept as prior-art baseline).

---

## 1. Executive Summary

Arrowow Studio is a **local, CLI-driven, Human-in-the-Loop (HITL) video production kernel** that
converts a JSON brand brief into a short-form UGC (User-Generated Content) video for a single,
locked character persona. It runs entirely on **Google Vertex AI** (Veo 3.1, Gemini 3.1 Flash
Image, Cloud TTS) orchestrated by a Python state machine.

**What works end-to-end today:** brief → persona lock → strategy → script → safety-critique →
storyboard → wardrobe → prompt engineering → reference frame → A-Roll/B-Roll video → FFmpeg
concat → multimodal video critique → cost-accounted artifacts on disk. A full run in
`LIVE_MEDIA` mode produces a real `.mp4`. There are **13 completed session directories** in
`output/`, confirming repeated successful live runs.

**What does not work yet:** true 30-second videos, production-grade lip-sync, cinematic
transitions, character consistency across more than ~2 clips, and any form of autonomous
self-healing. The pipeline currently halts and waits for a human at every stage.

**Strategic gap:** the goal is *one polished 30-second video per user-described scenario,
generated autonomously with only lightweight per-step validation*. Today we produce ~15 seconds
(2 × 8s clips concatenated), gated by 5 manual terminal approvals, with quality blockers in all
three critical dimensions (sync, LLM robustness, transitions).

---

## 2. System Architecture (As Built)

The pipeline is a **Blackboard state machine**: each stage reads prior state, writes its output,
and a validator gates progression. Orchestrated linearly in [`app/main.py`](../../app/main.py).

```
                          ┌─────────────────────────────────────────────┐
   brief.json ──▶ INTAKE ─┤ Blackboard (JSON state, persisted to disk)   │
                          │  metadata · brief · character · pre_production│
                          │  visual_plan · static_frame · production      │
                          │  cost_ledger                                  │
                          └─────────────────────────────────────────────┘
        │            │              │              │            │
     GATE 0       GATE 1         GATE 2A        GATE 2B    (final QA)
    (Intake)   (Story/Script) (Visual Plan) (Static Frame)  (no gate)
```

### A. Core Kernel — `app/kernel/`
| Component | File | Role |
|---|---|---|
| **Blackboard** | `blackboard.py` | Thread-safe local JSON state container; persists each stage's output to `output/{session_id}/session_state.json`. |
| **State Validator** | `state_validator.py` | Validates Blackboard against `schemas/session_state.schema.json` before advancing. |
| **Cost Ledger** | `cost_ledger.py` | Audits token/image/video/TTS usage; enforces hard budget caps (see §6). |
| **Approval Gate** | `approval_gate.py` | Terminal `Y/N` prompts — the HITL checkpoints. |
| **Production Session** | `production_session.py` | Creates session ID, initializes Blackboard + validators. |
| **Static Frame Stage** | `static_frame_stage.py` | Generates the reference anchor image. |
| **Production Stage** | `production_stage.py` | A-Roll + B-Roll generation, FFmpeg concat, critique. |

### B. Agent Layer — `app/agents/`
Live agents ([`live_agents.py`](../../app/agents/live_agents.py)) wrap Vertex AI; mock agents
([`mock_agent.py`](../../app/agents/mock_agent.py)) return canned JSON for `DRY_RUN`.

| Agent | Stage | Output | Notes |
|---|---|---|---|
| **Intake / Persona Matcher** | Phase A | `character` block | Deterministically locks to `sienna_fitness_01`. |
| **Creative Strategist** | Phase B | hook / angle / CTA | Injects expanded prohibited-phrase list. |
| **Scriptwriter** | Phase B | dialogue script | Uses `...` for breath pauses, CAPS for stress. |
| **Text Critic** | Phase B | approve/reject | Self-healing loop (≤3 retries) for banned terms. |
| **Storyboard Director** | Phase C | scene sequence | Enforces "A-Roll hook first, then B-Roll" rule. |
| **Wardrobe / Location** | Phase C | wardrobe + setting | Avoids filter-triggering apparel words. |
| **Shot Prompt Engineer** | Phase C | `static_frame_prompt` + `b_roll_prompt` | Two prompts; hard-overrides A-Roll to a "safe" string. |
| **Video Critic** | Phase E | approve + score /10 | `gemini-3.1-pro` analysis of final mp4. |

### C. Providers — `app/providers/live_providers.py`
| Modality | Model / Voice | Signature |
|---|---|---|
| **Image** | `gemini-3.1-flash-image` | `generate_image(prompt, reference_image, output_dir)` |
| **TTS** | `en-AU-Neural2-A` (Cloud TTS) | parses language from voice ID |
| **Video** | `veo-3.1-generate-001` | `generate_video(prompt, reference_image=None, output_dir=None, seed=None)` — passes `seed` into config only when not `None` |

### D. Execution Modes
| Mode | Agents | Providers | Cost |
|---|---|---|---|
| `DRY_RUN` (default) | Mock | Mock | Free |
| `LLM_ONLY` | Live Gemini | Mock | ~Free (Gemini free tier) |
| `LIVE_MEDIA` | Live Gemini | Live Veo/Imagen/TTS | Real $ |

---

## 3. Branch & Generation-Strategy Ledger

The repository holds **three competing video-generation strategies** across branches and the
uncommitted working tree. None fully solves the long-form problem. This is the single most
important thing to understand about the current state.

### Strategy A — 8s Image-to-Video Frame Chaining · `master` (commit `d717232`)
- **Mechanism:** script split into ~15–20-word chunks; first chunk generated from a static image
  anchor; FFmpeg extracts the last frame → becomes the anchor for the next chunk.
- **Fails because:** **latent-space drift** — after 2–3 hops the face "melts," clothing morphs,
  background destabilizes; and **visible seams** between consecutive talking-head shots.

### Strategy B — A-Roll / B-Roll Split · `feature/b-roll-architecture` (UNCOMMITTED working tree) ← current
- **Mechanism:** abandons frame-chaining. Pure **text-to-video** (`reference_image=None`). Script
  split in half: first half = A-Roll talking head, second half = B-Roll action voiceover.
  - `VisualPromptResponse` now carries **two** fields: `static_frame_prompt` + `b_roll_prompt`.
  - **Seed locking:** `GENERATION_SEED = 427819` applied to **A-Roll only**; B-Roll uses
    `seed=None` (identical seed on a different composition warps Veo's latent space).
  - Video Critic **relaxed** to ignore minor lip-sync micro-stutters.
  - Prohibited-phrase list **expanded** (squat, bra, tight, midriff, sheer, …) and injected at
    Strategist + Scriptwriter level; Prompt Engineer **hard-overrides** the A-Roll prompt to an
    extremely "safe" string to dodge Vertex RAI filters.
- **Strengths:** protects lip-sync (B-Roll is voiceover, no mouth-on-camera); avoids drift.
- **Fails because:** FFmpeg hard-concat = abrupt, unstylized cut; total length capped at the sum
  of two 8s generations (~15s).

### Strategy C — 15s Native Text-to-Video · `feature/15s-native-seed-locking`
- **Mechanism:** one continuous 15s A-Roll shot from descriptive prompting + locked seed; no
  reference images.
- **Fails because:** **low retention** (a static 15s talking head underperforms on TikTok/Reels)
  and **end-of-clip facial twitching** as temporal coherence degrades.

**Verdict:** Strategy B is the most viable foundation. The target architecture (`ideal_status_*`)
generalizes it: A-Roll (synced, seed-locked) + multiple B-Roll beats (voiceover-masked) +
programmed transitions = a true 30s asset.

---

## 4. The Three Critical Blockers (Diagnosed)

### Blocker 1 — Lip-Sync Fidelity
- **Root cause:** the pipeline relies entirely on **Veo's native text-to-lip inference**. No
  pre-generated audio is force-aligned to the video; there is no dedicated lip-sync pass.
- **Code evidence:** `production_stage.py` passes a dialogue string into the Veo prompt and trusts
  the model; `live_agents.py` `LiveVideoCritic` was *relaxed* to stop failing on the resulting
  micro-stutters — i.e. we lowered the bar rather than fixed the cause.
- **Consequence:** acceptable-but-not-production sync; the B-Roll voiceover trick exists purely to
  *avoid* needing sync for 50% of the runtime.

### Blocker 2 — LLM Robustness
- **Root cause:** agent outputs are parsed from free text. Despite Pydantic response *schemas*,
  the code carries a `clean_and_parse_json()` regex fallback for when the LLM escapes quotes
  wrong or wraps JSON in markdown. `main.py` itself probes 5+ possible key names
  (`static_frame_prompt`, `prompt`, `image_generation_prompt`, …) because output shape is
  unreliable.
- **Consequence:** brittle; no enforced structured-output contract; no self-healing on malformed
  output.

### Blocker 3 — Transitions & Continuity
- **Root cause:** compilation is a bare FFmpeg `concat` demuxer. No spatial reasoning, no match
  cuts / whip-pans / L-cuts, no temporal interpolation.
- **Consequence:** mechanical, amateur cuts; continuity held together only by seed-lock +
  repeated character description, which itself caps the usable clip count.

---

## 5. Autonomy Gap

There are **5 manual gates** (`GATE 0` Intake, `GATE 1` Story/Script, `GATE 2A` Visual Plan,
`GATE 2B` Static Frame, plus final QA print). The `VideoCritic` can *flag* a bad render but
**cannot route it back** for regeneration with a mutated seed/prompt — a human must re-run. This
blocks the "describe a scenario, walk away, get a finished video" goal.

---

## 6. Cost Model (from `cost_ledger.py`)

| Item | Unit price (LIVE_MEDIA) | Notes |
|---|---|---|
| Gemini LLM tokens | **$0.00** | treated as free tier |
| Imagen image | **$0.03 / image** | reference frame |
| Cloud TTS | **$0.000016 / char** | currently unused (Veo native audio) |
| Veo video | **$0.07 / 5s** | per generation |

**Hard caps (`_update_status`)**: `> 2 videos` OR `> 100k input tokens` ⇒ `budget_status =
exceeded`; `== 2 videos` OR `> 80k tokens` ⇒ `warning`. Billing labeled *"GCP Free Trial ($300)"*.

> ⚠️ The 2-video cap directly constrains the architecture — a 30s asset built from 8s clips needs
> **4+ generations**, so the cap must be lifted (and re-priced against real 2026 rates: Veo 3.1 is
> ~$0.15/sec in fast mode, not $0.07/5s) before scaling. The hardcoded `$0.07/5s` reflects old
> Veo 2.0 pricing and **understates true cost ~10×**.

---

## 7. Capability Scorecard

| Capability | Status | Evidence |
|---|---|---|
| Brief → persona lock | ✅ Works | `intake_agent.py`, deterministic to `sienna_fitness_01` |
| Strategy / script / safety critique | ✅ Works | `pre_production.py`, 3-retry critic loop |
| Storyboard + wardrobe + prompts | ✅ Works | `visual_planning.py`, two-prompt output |
| Reference frame generation | ✅ Works | `static_frame_stage.py` + `gemini-3.1-flash-image` |
| A-Roll + B-Roll video generation | ✅ Works | `production_stage.py`, seed-locked A-Roll |
| FFmpeg concatenation | ✅ Works | concat demuxer, but hard cut only |
| Multimodal video critique | 🟡 Partial | `LiveVideoCritic` flags but cannot auto-retry |
| Cost accounting | ✅ Works | `cost_ledger.py` — but prices stale (~10× low) |
| **30-second output** | ❌ Missing | capped at ~15s (2×8s) |
| **Production-grade lip-sync** | ❌ Missing | native Veo inference only; critic relaxed |
| **Cinematic transitions** | ❌ Missing | bare FFmpeg concat |
| **Multi-clip character consistency** | 🟡 Partial | seed-lock holds ~2 clips, then drifts |
| **Autonomous self-healing** | ❌ Missing | 5 manual gates, no critic→regenerate routing |
| **Structured-output enforcement** | 🟡 Partial | Pydantic schemas + regex fallback |
| **Multi-persona support** | ❌ Missing | hardcoded single persona |

---

## 8. Repository Hygiene & Security Findings

These are **not** code-architecture issues but must be addressed before any scaling or sharing:

1. 🔴 **Leaked service-account credential** — `google-credentials.json` (GCP private key) is
   present in the working tree. If it is (or ever was) committed/pushed, **rotate the key
   immediately** and purge from history. Add to `.gitignore`.
2. 🟠 **Uncommitted critical work** — the entire Strategy-B architecture lives only in the
   uncommitted working tree on `feature/b-roll-architecture`. One `git checkout` could lose it.
3. 🟠 **Repo noise** — tracked/loose `__pycache__/*.pyc`, `venv_system/`, `output/` session
   artifacts (videos/images), and `.DS_Store` files bloat the repo. Add a proper `.gitignore`.
4. 🟡 **`master` == `d717232` only** — `master` is a single-commit snapshot of the *old* Strategy
   A. The good work is all on feature branches. Decide the canonical branch and merge intentionally.

---

## 9. Verified Fact Sheet (for downstream agents)

```
PERSONA          sienna_fitness_01 (hardcoded)
SEED (A-Roll)    427819   ·   B-Roll seed = None
AGENT LLM        gemini-3.5-flash            (via google.antigravity SDK, vertex=True)
VIDEO MODEL      veo-3.1-generate-001        (~8s clips, native audio)
IMAGE MODEL      gemini-3.1-flash-image
TTS VOICE        en-AU-Neural2-A             (Cloud TTS, currently unused; provider default en-US-Journey-F)
CRITIC MODEL     gemini-3.1-pro-preview      (via google.genai, multimodal)
GATES            0 Intake · 1 Script · 2A Visual · 2B Frame · (final QA)
BUDGET CAPS      videos>2 OR tokens>100k = exceeded ; videos==2 OR tokens>80k = warning
CURRENT OUTPUT   ~15s (A-Roll 8s + B-Roll 8s, FFmpeg hard concat)
TARGET OUTPUT    30s autonomous, validated per-step
```

---
*Next: see `ideal_status_hybrid.md` (recommended), `ideal_status_best_in_class.md`, and
`ideal_status_google_native.md` for the three target-architecture paths.*
