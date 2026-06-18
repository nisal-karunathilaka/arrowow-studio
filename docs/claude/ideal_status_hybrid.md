# ARROWOW STUDIO — IDEAL STATUS · HYBRID ARCHITECTURE ⭐ RECOMMENDED
## The Arrowow Directorial Rules Bible & Target Architecture
*A prompt-translatable, agent-executable reference for autonomous 30-second UGC*
*Owner: Claude · Variant: **Hybrid (Google core + targeted external add-ons)** · June 2026*

> ## 🔒 STATUS: LOCKED — retained alternative (escalation path).
> The team selected **Google Vertex-native** (`ideal_status_google_native.md`) for v1. This Hybrid
> plan is locked as the **escalation path**: adopt it if native lip-sync alone fails acceptance
> (add Sync.so + ElevenLabs without changing the grammar).
>
> **THREE VARIANTS EXIST. THIS WAS THE RECOMMENDED PATH (not selected for v1).**
> - ⭐ `ideal_status_hybrid.md` — **THIS DOC.** Google Veo/Imagen/Gemini core for video & image,
>   plus one external lip-sync engine and ElevenLabs TTS where Google can't compete.
> - `ideal_status_best_in_class.md` — strongest tool per job regardless of vendor.
> - `ideal_status_google_native.md` — everything on Vertex AI, single billing, native limits.
>
> All three share the identical **Directorial Grammar** (§01–§04, §07, §08, §11). They diverge in
> **§05 Solving the Three Limitations**, **§06 Tool Landscape**, **§09 Integration**, **§10 Roadmap**.
> Read `current_status.md` first for the as-built reality this evolves from.

---

## 00 · HOW TO USE THIS DOCUMENT

**Your role (every agent in the factory):** you are not "calling a video API." You are a film crew
shooting a 30-second UGC ad for a locked character. Every decision — beat, framing, sync mode,
seed — flows from the grammar below. When you (or another agent) produce output, **evaluate it
against this grammar and flag deviations before accepting.**

**Assembly order for any shot prompt (never reorder):**
`shot type (A/B-Roll) → camera code → character lock → wardrobe → setting → safety/negative block → audio/sync mode → dialogue/voiceover`

**The Hybrid contract in one line:** *Google generates the pixels (Veo 3.1 video, Imagen frames,
Gemini reasoning); an external engine fixes the mouth (Sync.so/Hedra lip-sync); ElevenLabs speaks;
a compositor stitches with real transitions.*

---

## 01 · THE MULTI-AGENT FACTORY

The system evolves from a linear HITL script-runner into an **asynchronous, self-healing
orchestration graph**. The human describes a scenario and **validates each step** (a lightweight
approve/refine gate); everything else is automatic.

### Orchestration hierarchy
| # | Agent | Consumes | Produces | Model / Tool (Hybrid) |
|---|---|---|---|---|
| 0 | **Director (Orchestrator)** | Blackboard, Critic verdicts | stage routing, retries, seed/prompt mutations | Gemini 3.1 Pro reasoning loop |
| 1 | **Creative Strategist** | brief, persona | hook / angle / CTA, emotional arc | Gemini 3.1 |
| 2 | **Scriptwriter** | strategy, persona | timestamped script split A-Roll / B-Roll voiceover | Gemini 3.1 |
| 3 | **Storyboard & Continuity** | script, persona | beat sheet w/ camera codes + seed plan | Gemini 3.1 |
| 4 | **Prompt Engineer** | storyboard, wardrobe | per-shot API payloads + filter-bypass | Gemini 3.1 |
| 5 | **Media Assembler / Compositor** | payloads, audio | clips, lip-synced A-Roll, stitched master | **Veo 3.1 + Imagen + ElevenLabs + Sync.so + moviepy/ffmpeg** |
| 6 | **Multi-Modal Critic** | final mp4 | approve / reject + per-defect routing | Gemini 3.1 Pro (vision) |

### The single-gate-per-step human model
The user **describes a scenario in natural language** (not a JSON brief). The Director expands it
into the Blackboard. The human then sees **one validation card per stage** (script → storyboard →
key frame → final cut) and either ✅ approves or 💬 gives a one-line note that the Director routes
back as a mutation. No terminal `Y/N` chains; no manual prompt-key spelunking.

---

## 02 · CORE GRAMMAR OF 30-SECOND UGC

- **The format is a deliberate hybrid.** Direct-to-camera dialogue (A-Roll) + dynamic
  voiceover-driven action (B-Roll). This masks concatenation seams *and* protects lip-sync — the
  mouth is only on-camera during segments we will explicitly lip-sync.
- **Pacing is engineered for retention.** A 30s video is never one shot. It is a sequence:
  **Hook → Intro → Action → Proof → CTA.**
- **The protagonist is locked** via **Seed Locking** + **Latent-Space Casting** (an immutable
  physical-description block injected into *every* prompt) — never via degrading reference-image
  chaining.
- **Three things break the grammar under AI defaults:** (1) generative melting over long durations;
  (2) lip-sync stutter on complex phrasing; (3) hard unstylized cuts. §05 solves all three.

---

## 03 · THE 30-SECOND TEMPORAL PACING TIMELINE

Every 30s asset follows this rigid beat sheet. Each beat is a separately generated clip; the
Compositor joins them with the §07 transition grammar.

| Time | Beat | Action | Camera | Sync mode | Seed |
|---|---|---|---|---|---|
| **0–3s** | **Hook** | kinetic entry / pattern interrupt (grab bottle, turn to cam) | **C2** dynamic | Lip-synced (short, punchy) | locked |
| **3–10s** | **Intro** | character states the premise / problem to viewer | **C1** frontal | **Lip-synced** | locked |
| **10–20s** | **Action** | real-world demo (workout, product in use), facing away/moving | **C4** wide / **C3** macro | **Voiceover** (no mouth on cam) | unlocked |
| **20–27s** | **Proof** | close-up payoff (texture, result, comparison) | **C3** macro | **Voiceover** | unlocked |
| **27–30s** | **CTA** | character returns to camera, direct call to action | **C1** frontal | **Lip-synced** | locked |

**Sync budget:** only ~13 of 30 seconds (Hook + Intro + CTA) are ever lip-synced. The middle 17s
is voiceover over masked motion — *zero lip-sync risk by design.*

---

## 04 · CAMERA & COMPOSITION CODES

Inject these named codes verbatim into prompts. The Compositor and Critic both reason over them.

- **C1 · SYMMETRICAL FRONTAL CLOSE-UP** — eye-level, subject ~70% of frame, minimal shake.
  *Default for Intro (3–10s) and CTA (27–30s).* Lip-synced.
- **C2 · DYNAMIC HANDHELD FOLLOW** — visible vlog shake, tracking front/side. *Hook only (0–3s).*
- **C3 · MACRO DETAIL INSERT** — tight close on object/result, shallow DOF. *Proof (20–27s).*
- **C4 · DEEP-SPACE WIDE** — subject <30% of frame, environment readable. *Action (10–20s).*

**DO** default to C1 for any on-camera speaking beat. **DO** keep the face off-camera or in profile
for C3/C4 so no sync is needed. **DON'T** put direct-to-camera dialogue in C3/C4. **DON'T** use C2
shake outside the Hook — it reads as instability, not energy, when overused.

---

## 05 · SOLVING THE THREE LIMITATIONS — HYBRID ARCHITECTURE

> **Hybrid principle:** keep video/image on Google (cost, infra, prompt adherence, native realism),
> but **stop asking Veo to do the two things it's worst at** — perfect lip-sync and stylized
> transitions — and hand those to purpose-built tools.

### A. Lip-Sync — Audio-First + Dedicated Engine (A-Roll only)
1. **Generate audio first.** ElevenLabs v3 produces the dialogue track (natural Australian VO,
   breath, cadence) *before* any video. This becomes the timing ground-truth.
2. **Generate silent A-Roll** with Veo 3.1 (seed-locked C1/C2), ignoring native audio for sync.
3. **Force-align with a dedicated lip-sync engine.** Feed the ElevenLabs track + the Veo A-Roll
   into **Sync.so** (best-in-class pure lip-sync API, built for developer pipelines) — or **Hedra**
   if we ever drive a beat from a single still frame and want maximal facial realism. Output: an
   A-Roll where the mouth matches the waveform exactly.
4. **B-Roll needs no sync.** The middle 17s plays the ElevenLabs VO over masked motion.

**Why Sync.so for Hybrid:** it is the strongest *pure lip-sync* API and is designed to be embedded
in another product's pipeline (exactly our Compositor's need) — not a full avatar studio we'd be
fighting. Hedra is the fallback when a beat is image-driven.

### B. Continuity — Seed Lock + Latent-Space Casting (unchanged across variants)
1. **Seed lock** `427819` on all C1/C2 A-Roll generations.
2. **Latent-Space Casting** — Prompt Engineer injects an immutable block into *every* prompt:
   `[CHARACTER LOCK: Athletic 26-year-old Australian female, sun-kissed skin, messy blonde hair in
   a claw clip, bright blue eyes, minimal clean-girl makeup]`.
3. **Imagen reference frame** seeds the look; Veo 3.1's image-conditioning anchors identity on the
   *first* frame of each A-Roll (not chained across clips — that's what melted in Strategy A).

### C. Transitions — Programmed, Not Concatenated
Replace bare FFmpeg concat with a **moviepy/ffmpeg compositor** that executes the §07 transition
grammar:
- **Match cut** — Scene A ends in the exact posture Scene B begins (Prompt Engineer enforces).
- **Whip pan** — append `[rapid horizontal whip-pan blur to the right]` to the outgoing clip; the
  compositor blends the motion-blurred tail into the next clip's head.
- **Macro zoom** — a C3 zoom-in masks the cut into the next environment.
- **Crossfade/`xfade`** — for soft Proof→CTA returns.

**Hybrid stops here on transitions** (programmed + xfade). True generated tweening (Luma/Runway
interpolation) is a *best-in-class* upgrade, intentionally out of scope to keep infra lean.

### Hybrid pipeline diagram
```
scenario ─▶ Director ─▶ Strategist ─▶ Scriptwriter ─▶ Storyboard ─▶ Prompt Eng
                                                                       │
   ElevenLabs v3 (VO, audio-first) ──────────────┐                     ▼
                                                  ▼              Veo 3.1 (silent A-Roll, seed-lock)
   A-Roll: Sync.so lip-sync (VO + silent clip) ◀──┘              Veo 3.1 (B-Roll action, no sync)
                                                  │              Imagen (reference frame)
                          moviepy/ffmpeg Compositor (match-cut / whip-pan / xfade)
                                                  ▼
                                      Gemini 3.1 Pro Multi-Modal Critic ─▶ (reject → Director)
                                                  ▼
                                         30s master.mp4
```

---

## 06 · THE COMPETITIVE TOOL LANDSCAPE (2026) — HYBRID SUBSET

| Job | Hybrid choice | Why | Alternatives (see other variants) |
|---|---|---|---|
| Video gen | **Veo 3.1** | best all-round; native realism + prompt adherence; ~$0.15/s fast | Kling 3.0 (15s/4K single pass), Runway Gen-4.5 (camera control) |
| Reference image | **Imagen / Gemini 3.1 Flash Image** | already integrated, cheap | Midjourney, Flux |
| Lip-sync | **Sync.so** (Hedra fallback) | best pure-sync API for embedding | HeyGen (avatars), LatentSync (OSS), VEED Fabric |
| TTS / voice | **ElevenLabs v3** | most natural, breath/cadence control | Google Cloud TTS (native, cheaper) |
| Compositing | **moviepy + ffmpeg** | scriptable transitions | Runway/Luma interpolation |
| Reasoning | **Gemini 3.1 Pro** | vision critique + orchestration | Claude, GPT |

**How the category leaders structure this (reference):** Arcads (raised $16M Dec 2025) drives
high-volume UGC variations from motion-captured consenting actors + batched hook-body-CTA scripts;
Captions AI specializes in short-form vertical; HeyGen targets polished multilingual avatars. Our
Hybrid borrows Arcads' **batch hook/body/CTA structure** and **avoids** their proprietary-actor lock-in
by generating personas with Veo + Latent-Space Casting.

---

## 07 · PROMPT TEMPLATES & FILTER-BYPASS DICTIONARY

Vertex RAI aggressively blocks fitness terms. The Prompt Engineer **must** map them:

| Banned → | Safe equivalent |
|---|---|
| squat | deep athletic knee bend |
| form-fitting / tight leggings | performance activewear pants |
| sports bra / midriff / cleavage / chest | activewear top / upper torso |
| sheer / see-through / opacity | (drop entirely; describe color + fabric only) |

### Template A — A-Roll (C1/C2, lip-synced)
```text
[C1 SYMMETRICAL FRONTAL CLOSE-UP] A continuous talking-head vlog shot of Sienna looking directly
into the lens, speaking energetically.
[CHARACTER LOCK: Athletic 26-year-old Australian female, sun-kissed skin, messy blonde hair in a
claw clip, bright blue eyes, minimal clean-girl makeup.]
Wearing a modest, loose-fitting sage green activewear top. Brightly lit modern gym.
Strictly no captions, no subtitles, clear on-screen visual field.
Audio: clear energetic native Australian female voice, natural breathing, realistic jaw cadence,
no background music.
(Sienna: "Alright team, quick reality check...")
```
*(Hybrid: generate this SILENT; sync the ElevenLabs track via Sync.so.)*

### Template B — B-Roll (C4, voiceover)
```text
[C4 DEEP-SPACE WIDE] Cinematic tracking shot of Sienna performing a deep athletic knee bend,
facing away from camera, demonstrating her sage green performance activewear pants. Camera slowly
pans around her in a brightly lit modern gym.
[CHARACTER LOCK: ...same block...]
Strictly no captions. No direct eye contact with camera.
(Voiceover: "...if your gear isn't holding up, what are we even doing? Let's get after it.")
```

### Universal negative prompt (append to every shot)
```text
--no captions, subtitles, on-screen text, watermark, logo
--no extra fingers, deformed hands, face warping, identity drift
--no jump-cut seams, no abrupt lighting change between shots
--no real-person likeness or celebrity resemblance
```

---

## 08 · STRUCTURED-OUTPUT & SELF-HEALING CONTRACT

Kills Blocker 2 (LLM brittleness) — **identical across all variants.**

1. **Enforce structured outputs.** Every agent uses Gemini function-calling / strict response
   schemas. **Delete the `clean_and_parse_json` regex fallback** and the 5-key probing in
   `main.py`; a schema violation is a hard error the Director catches, not something we paper over.
2. **One canonical shape per stage**, versioned in `schemas/`. The Blackboard validates on write.
3. **Self-healing loop.** The Critic returns *structured defects* — `{defect: "lip_sync"|"identity_
   drift"|"artifact"|"pacing", segment: "intro", severity: 1-5}`. The Director maps each defect to a
   mutation:
   - `lip_sync` → re-run Sync.so pass (don't regenerate video).
   - `identity_drift` → regenerate that clip with reinforced character lock, same seed.
   - `artifact` → regenerate with seed +1 and tightened negative prompt.
   - `pacing` → ask Scriptwriter to trim that beat.
4. **Bounded retries** (≤3 per segment) with cost-ledger awareness before escalating to the human.

---

## 09 · MCP & EXTERNAL-RESOURCE INTEGRATION PLAN (HYBRID)

We "move step by step" by wrapping each external capability behind a clean provider interface so
the orchestrator can call it like any other tool — and, where useful, behind an **MCP server** so
future Claude-driven orchestration can invoke it natively.

| Capability | Integration | Step |
|---|---|---|
| ElevenLabs TTS | REST provider `providers/elevenlabs_tts.py` (mirror `live_providers` shape) | Phase 2 |
| Sync.so lip-sync | REST provider `providers/sync_lipsync.py`; async job poll | Phase 2 |
| Veo / Imagen | existing `live_providers.py` (keep) | done |
| Compositor | `kernel/compositor.py` (moviepy/ffmpeg transition engine) | Phase 3 |
| MCP exposure (optional) | wrap providers as an MCP server so an external Claude orchestrator can drive end-to-end | Phase 3+ |

**Secrets:** move all keys (GCP, ElevenLabs, Sync.so) to environment / secret manager; **never** a
committed `google-credentials.json` (see `current_status.md` §8 — rotate the leaked key first).

---

## 10 · PHASED IMPLEMENTATION ROADMAP (HYBRID)

### Phase 1 — Orchestration & Robustness (Weeks 1–4)
- Refactor `main.py` → async Director loop; replace 5 terminal gates with single-gate-per-step.
- Enforce structured outputs across all agents; delete regex/key-probing fallbacks (§08).
- Ship the filter-bypass dictionary as shared config.
- **Lift the 2-video cost cap**; re-price ledger to real Veo 3.1 rates (~$0.15/s).
- ✅ *Accept when:* a scenario runs end-to-end producing the current ~15s output with **zero**
  JSON-parse failures across 20 runs.

### Phase 2 — Audio-First + Lip-Sync (Weeks 5–9)
- Add ElevenLabs provider (audio generated first, becomes timing ground-truth).
- Add Sync.so provider; A-Roll = silent Veo clip + Sync.so pass.
- ✅ *Accept when:* A-Roll lip-sync passes the Critic at ≥8/10 on 9 of 10 sample scripts.

### Phase 3 — Compositor, 30s Assembly, Autonomy (Weeks 10–16)
- Build `compositor.py` (match-cut / whip-pan / xfade); assemble full 5-beat 30s timeline.
- Activate Critic→Director self-healing with bounded retries.
- ✅ *Accept when:* the system produces a complete 30s asset with ≤1 human note, no visible seams,
  consistent identity across all 5 beats, on 8 of 10 scenarios — unattended.

---

## 11 · THE TEN NON-NEGOTIABLES + QUICK-REFERENCE CARD

### Ten Non-Negotiables (enforce every one; these break most under AI defaults)
1. A 30s asset is **5 beats**, never one shot (Hook/Intro/Action/Proof/CTA).
2. Only Hook/Intro/CTA are **lip-synced**; the middle is **voiceover over masked motion**.
3. Audio is generated **first**; video syncs to it — never the reverse.
4. **Seed-lock A-Roll** (`427819`); **never** seed-lock a different B-Roll composition.
5. **Latent-Space Casting** block in **every** prompt — identity comes from text, not chained frames.
6. **Never chain reference frames** across clips (that's the melt).
7. Transitions are **programmed** (match-cut/whip-pan/macro-zoom), never bare concat.
8. **Structured outputs only** — a schema violation is an error, not a fallback.
9. The Critic returns **structured defects** that route to **targeted** fixes, not full reruns.
10. The human **describes + validates**; the factory **executes**. One gate per step, max.

### The Universal Style Anchor (memorize)
```
Autonomous 30s UGC: 5-beat retention arc (hook/intro/action/proof/cta),
hybrid A-Roll(lip-synced, seed-locked, C1) + B-Roll(voiceover, masked motion, C3/C4),
Google Veo 3.1 pixels + ElevenLabs voice + Sync.so mouth + moviepy transitions,
identity via seed-lock + Latent-Space Casting (never frame-chaining),
structured outputs + self-healing Critic→Director loop,
human describes & validates per step — the factory shoots the film.
```

---
*Recommended path. For the maximal-quality multi-vendor route see `ideal_status_best_in_class.md`;
for the single-billing Vertex-only route see `ideal_status_google_native.md`.*
