# ARROWOW STUDIO — IDEAL STATUS · BEST-IN-CLASS (MULTI-VENDOR)
## The Arrowow Directorial Rules Bible & Target Architecture
*A prompt-translatable, agent-executable reference for autonomous 30-second UGC*
*Owner: Claude · Variant: **Best-in-Class (strongest tool per job, any vendor)** · June 2026*

> ## 🔒 STATUS: LOCKED — retained alternative (top of the escalation path).
> The team selected **Google Vertex-native** (`ideal_status_google_native.md`) for v1. This
> Best-in-Class plan is locked as the **ceiling reference**: the multi-vendor route to pursue only
> if both native and Hybrid are outgrown.
>
> **THREE VARIANTS EXIST. THIS IS THE MAXIMAL-QUALITY PATH (not selected for v1).**
> - `ideal_status_hybrid.md` — ⭐ **RECOMMENDED.** Google core + targeted external add-ons.
> - `ideal_status_best_in_class.md` — **THIS DOC.** Best tool per job, multi-vendor, highest
>   quality and complexity; the orchestrator *routes* across engines per shot.
> - `ideal_status_google_native.md` — everything on Vertex AI, single billing, native limits.
>
> Shared **Directorial Grammar** (§01–§04, §07, §08, §11) is identical across all three. This
> variant diverges in **§05, §06, §09, §10**. Read `current_status.md` first.

---

## 00 · HOW TO USE THIS DOCUMENT

**Your role (every agent):** you are a film crew shooting a 30s UGC ad for a locked character.
Every decision flows from the grammar below; evaluate output against it and flag deviations.

**Assembly order for any shot prompt (never reorder):**
`shot type (A/B-Roll) → camera code → character lock → wardrobe → setting → safety/negative block → audio/sync mode → dialogue/voiceover`

**The best-in-class contract in one line:** *the Director routes each shot to the engine that wins
that shot — Veo for realism, Kling for long single-pass, Runway for camera control — with Sync.so/
Hedra for the mouth, ElevenLabs for voice, and generated tweening for transitions.*

---

## 01 · THE MULTI-AGENT FACTORY

The system evolves from a linear HITL script-runner into an **asynchronous, self-healing
orchestration graph** with **engine routing**. The human describes a scenario and **validates each
step**; everything else is automatic.

### Orchestration hierarchy
| # | Agent | Consumes | Produces | Model / Tool (Best-in-Class) |
|---|---|---|---|---|
| 0 | **Director (Orchestrator)** | Blackboard, Critic verdicts | routing, **engine selection**, retries, mutations | Gemini 3.1 Pro / Claude reasoning loop |
| 1 | **Creative Strategist** | brief, persona | hook / angle / CTA, emotional arc | best available LLM |
| 2 | **Scriptwriter** | strategy, persona | timestamped script (A-Roll / B-Roll) | best available LLM |
| 3 | **Storyboard & Continuity** | script, persona | beat sheet + camera codes + **per-beat engine tags** | LLM |
| 4 | **Prompt Engineer** | storyboard, wardrobe | per-engine payloads + filter-bypass | LLM |
| 5 | **Media Assembler / Compositor** | payloads, audio | clips, lip-synced A-Roll, interpolated master | **Veo 3.1 / Runway Gen-4.5 / Kling 3.0 + Sync.so/Hedra + ElevenLabs + Luma/Runway interp** |
| 6 | **Multi-Modal Critic** | final mp4 | approve / reject + per-defect routing | Gemini 3.1 Pro vision / GPT-vision ensemble |

### The single-gate-per-step human model
User **describes a scenario in natural language**; the Director expands it into the Blackboard and
shows **one validation card per stage** (script → storyboard → key frame → final cut). ✅ approve or
💬 one-line note routed back as a mutation. No terminal `Y/N` chains.

---

## 02 · CORE GRAMMAR OF 30-SECOND UGC

- **Deliberate hybrid format:** A-Roll (direct-to-camera dialogue) + B-Roll (voiceover action).
  Masks seams and protects lip-sync.
- **Pacing engineered for retention:** Hook → Intro → Action → Proof → CTA.
- **Protagonist locked** via Seed Locking + Latent-Space Casting, never degrading frame-chaining.
- **Three breakers under AI defaults:** generative melting, lip-sync stutter, hard cuts. §05 solves all.

---

## 03 · THE 30-SECOND TEMPORAL PACING TIMELINE

| Time | Beat | Action | Camera | Sync mode | Seed | Best-in-class engine |
|---|---|---|---|---|---|---|
| **0–3s** | **Hook** | kinetic entry / pattern interrupt | **C2** dynamic | Lip-synced | locked | **Runway Gen-4.5** (camera/motion control) |
| **3–10s** | **Intro** | states the premise to viewer | **C1** frontal | **Lip-synced** | locked | **Veo 3.1** (face realism) |
| **10–20s** | **Action** | real-world demo, facing away/moving | **C4/C3** | **Voiceover** | unlocked | **Kling 3.0** (long single-pass, 4K) |
| **20–27s** | **Proof** | close-up payoff / comparison | **C3** macro | **Voiceover** | unlocked | **Veo 3.1 / Runway** |
| **27–30s** | **CTA** | returns to camera, call to action | **C1** frontal | **Lip-synced** | locked | **Veo 3.1** |

Only ~13 of 30s are lip-synced (Hook+Intro+CTA); the middle 17s is voiceover over masked motion.

---

## 04 · CAMERA & COMPOSITION CODES

- **C1 · SYMMETRICAL FRONTAL CLOSE-UP** — eye-level, ~70% frame, minimal shake. Intro & CTA. Synced.
- **C2 · DYNAMIC HANDHELD FOLLOW** — visible vlog shake, tracking. Hook only.
- **C3 · MACRO DETAIL INSERT** — tight close on object/result, shallow DOF. Proof.
- **C4 · DEEP-SPACE WIDE** — subject <30% of frame, environment readable. Action.

**DO** default C1 for speaking beats; keep the face off-cam/profile for C3/C4 (no sync needed).
**DON'T** put direct dialogue in C3/C4; **DON'T** overuse C2 shake outside the Hook.

---

## 05 · SOLVING THE THREE LIMITATIONS — BEST-IN-CLASS ARCHITECTURE

> **Best-in-class principle:** no single engine wins every shot. The Director **routes per beat**,
> then a dedicated lip-sync engine and a generated-interpolation transition layer finish the cut.

### A. Lip-Sync — Audio-First + Dedicated Engine (A-Roll only)
1. **Audio first:** ElevenLabs v3 generates the VO track = timing ground-truth.
2. **Silent A-Roll** from whichever engine wins the beat (Veo 3.1 for face realism; Runway for the
   Hook's camera move).
3. **Force-align:** route the clip + VO into **Sync.so** (pure-sync API) for talking-head beats, or
   **Hedra** when a beat is driven from a single still (max facial realism from one image). For
   speed-critical batch variants, **VEED Fabric 1.0** is the fast-path (leads accuracy, ~68% faster).
4. **B-Roll** plays VO over masked motion — no sync.

**Engine matrix:** Sync.so = embeddable pure quality · Hedra = single-image realism · HeyGen =
multilingual avatars (40+ langs) if we localize · LatentSync = OSS/self-hosted cost floor.

### B. Continuity — Seed Lock + Latent-Space Casting + Cross-Engine Reference
1. **Seed lock** `427819` on all A-Roll (where the engine exposes a seed; Veo does).
2. **Latent-Space Casting** block in every prompt (immutable physical description).
3. **Reference-driven identity:** use **Runway Gen-4.5 reference images** and **Veo image
   conditioning** to carry the *same* face across engines — Runway Gen-4 is specifically strong at
   reference-driven character consistency across shots. The Continuity agent owns a single canonical
   reference frame (Imagen/Flux/Midjourney) fed to every engine.

### C. Transitions — Programmed **+ Generated Interpolation**
Beyond programmed match-cut/whip-pan/macro-zoom (§07), this variant adds **generated tweening**:
- **Luma / Runway interpolation** synthesizes intermediate frames between two beats for seamless
  whip-pans and morphs no concat can achieve.
- Compositor still owns xfade/audio L-cuts; interpolation is reserved for hero transitions.

### Best-in-class pipeline diagram
```
scenario ─▶ Director (routes per beat) ─▶ Strategist ─▶ Scriptwriter ─▶ Storyboard ─▶ Prompt Eng
                                                                              │
   ElevenLabs v3 (audio-first) ───────────────────┐                          ▼
                                                   ▼     Runway/Veo/Kling (silent clips per beat)
   A-Roll: Sync.so / Hedra / VEED Fabric lip-sync ◀┘     canonical reference frame → all engines
                                                   │
              Luma/Runway interpolation + moviepy/ffmpeg Compositor (hero transitions)
                                                   ▼
                       Multi-Modal Critic (Gemini/GPT vision ensemble) ─▶ (reject → Director)
                                                   ▼
                                          30s master.mp4
```

---

## 06 · THE COMPETITIVE TOOL LANDSCAPE (2026) — FULL ROUTING TABLE

| Job | Primary | When to route here | Runner-up |
|---|---|---|---|
| Realistic talking head | **Veo 3.1** | best face realism, native audio, prompt adherence | Kling 3.0 |
| Long single-pass / 4K action | **Kling 3.0** | 15s at 4K/60fps single pass; native dialogue, 5-lang sync | Seedance |
| Camera move / motion control | **Runway Gen-4.5** | motion brush, camera paths, reference consistency | — |
| Cinematic 1080p coverage | **Sora 2** | stylized cinematic shots | Veo 3.1 |
| Lip-sync (embed) | **Sync.so** | pure-sync quality in a pipeline | Hedra |
| Lip-sync (single image) | **Hedra** | max realism from one still | HeyGen |
| Lip-sync (fast batch) | **VEED Fabric 1.0** | fastest, accuracy leader | LatentSync (OSS) |
| Voice | **ElevenLabs v3** | most natural, breath/cadence | Cloud TTS |
| Transitions | **Luma / Runway interp** | generated tweening | moviepy xfade |
| Reasoning / critique | **Gemini 3.1 Pro / Claude** | vision + orchestration | GPT |

**Category leaders (reference):** Arcads (motion-capture actors, batched hook/body/CTA, $16M Dec
2025) for high-volume variations; Captions AI for short-form vertical; HeyGen for polished
multilingual. Best-in-class Arrowow **out-routes** any single product by composing the winners.

---

## 07 · PROMPT TEMPLATES & FILTER-BYPASS DICTIONARY

Filter map (Prompt Engineer must apply): squat → *deep athletic knee bend* · form-fitting/tight →
*performance activewear* · sports bra/midriff/chest → *activewear top / upper torso* · sheer/
see-through/opacity → *(drop; describe color + fabric only)*.

### Template A — A-Roll (C1/C2, lip-synced) — engine-agnostic
```text
[C1 SYMMETRICAL FRONTAL CLOSE-UP] Continuous talking-head vlog shot of Sienna looking into the lens,
speaking energetically.
[CHARACTER LOCK: Athletic 26-year-old Australian female, sun-kissed skin, messy blonde hair in a
claw clip, bright blue eyes, minimal clean-girl makeup.]
Wearing a modest, loose-fitting sage green activewear top. Brightly lit modern gym.
Strictly no captions/subtitles. Audio: clear energetic native Australian female voice, natural
breathing, realistic jaw cadence, no background music.
(Sienna: "Alright team, quick reality check...")
```
*(Generate SILENT on the routed engine; sync ElevenLabs VO via Sync.so/Hedra.)*

### Template B — B-Roll (C4, voiceover)
```text
[C4 DEEP-SPACE WIDE] Cinematic tracking shot of Sienna performing a deep athletic knee bend, facing
away from camera, demonstrating her sage green performance activewear pants. Camera slowly pans in a
brightly lit modern gym.
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

*(Identical across all variants — kills Blocker 2.)*

1. **Structured outputs only** (function-calling / strict schemas). Delete `clean_and_parse_json`
   and `main.py` key-probing; a schema violation is a hard error.
2. **One canonical shape per stage**, versioned in `schemas/`; Blackboard validates on write.
3. **Structured defects from the Critic:** `{defect, segment, severity}` → Director maps to targeted
   fix: `lip_sync` → re-run sync pass; `identity_drift` → regenerate clip w/ reinforced lock + seed;
   `artifact` → seed +1 + tighter negative; `pacing` → trim beat. **In best-in-class, a defect can
   also trigger an engine re-route** (e.g. Veo artifacted → retry the beat on Kling).
4. **Bounded retries (≤3/segment)**, cost-aware, before escalating to the human.

---

## 09 · MCP & EXTERNAL-RESOURCE INTEGRATION PLAN (BEST-IN-CLASS)

Every engine sits behind a uniform `VideoEngine` / `LipSyncEngine` / `TTSEngine` interface so the
Director routes by capability tag, not by hardcoded calls. Expose them via **MCP servers** so an
external Claude orchestrator can drive routing natively.

| Capability | Integration | Step |
|---|---|---|
| Veo 3.1 / Runway / Kling / Sora | `engines/*` behind one `VideoEngine` interface + capability tags | Phase 2–3 |
| Sync.so / Hedra / VEED / LatentSync | `LipSyncEngine` interface; async job poll | Phase 2 |
| ElevenLabs / Cloud TTS | `TTSEngine` interface | Phase 2 |
| Luma / Runway interpolation | `kernel/compositor.py` transition layer | Phase 3 |
| MCP exposure | wrap each engine family as an MCP server for external orchestration | Phase 3 |

**Secrets:** all vendor keys in a secret manager; rotate the leaked GCP key (see `current_status.md`
§8) first. Vendor sprawl ⇒ centralize key rotation and per-vendor rate-limit handling.

---

## 10 · PHASED IMPLEMENTATION ROADMAP (BEST-IN-CLASS)

### Phase 1 — Orchestration, Robustness & Engine Abstraction (Weeks 1–5)
- Async Director loop; single-gate-per-step; structured outputs (§08).
- Define `VideoEngine`/`LipSyncEngine`/`TTSEngine` interfaces + capability tags; wire **one** of each
  to start (Veo, Sync.so, ElevenLabs).
- Lift the 2-video cap; re-price ledger per-engine ($/s).
- ✅ *Accept when:* a scenario runs end-to-end through the abstraction with zero JSON-parse failures.

### Phase 2 — Multi-Engine Routing + Lip-Sync (Weeks 6–11)
- Add Runway + Kling behind `VideoEngine`; Storyboard tags beats with engines; Director routes.
- A-Roll = silent routed clip + Sync.so/Hedra; ElevenLabs audio-first.
- ✅ *Accept when:* per-beat routing demonstrably improves Critic scores vs single-engine on 10 samples,
  and A-Roll sync ≥8/10 on 9/10 scripts.

### Phase 3 — Generated Transitions, 30s Assembly, Autonomy (Weeks 12–18)
- Add Luma/Runway interpolation hero transitions; assemble full 5-beat 30s timeline.
- Critic→Director self-healing **with engine re-routing**; bounded retries.
- ✅ *Accept when:* unattended 30s asset, no seams, consistent identity across engines, ≤1 human note,
  on 8/10 scenarios.

---

## 11 · THE TEN NON-NEGOTIABLES + QUICK-REFERENCE CARD

### Ten Non-Negotiables
1. A 30s asset is **5 beats**, never one shot (Hook/Intro/Action/Proof/CTA).
2. Only Hook/Intro/CTA are **lip-synced**; the middle is **voiceover over masked motion**.
3. Audio is generated **first**; video syncs to it.
4. **Seed-lock A-Roll**; never seed-lock a different B-Roll composition.
5. **Latent-Space Casting** block in **every** prompt across **every** engine.
6. **Never chain reference frames** across clips; use a single canonical reference per persona.
7. Transitions are **programmed or generated-interpolated**, never bare concat.
8. **Structured outputs only** — a schema violation is an error, not a fallback.
9. The Critic returns **structured defects** → targeted fix **or engine re-route**, not blind rerun.
10. The human **describes + validates**; the factory **routes & executes**. One gate per step.

### The Universal Style Anchor (memorize)
```
Autonomous 30s UGC: 5-beat retention arc, hybrid A-Roll(synced,seed-locked,C1) + B-Roll(VO,masked),
Director routes pixels across Veo 3.1 / Runway Gen-4.5 / Kling 3.0 per shot,
mouth via Sync.so/Hedra, voice via ElevenLabs, transitions via Luma/Runway interpolation,
identity via seed-lock + Latent-Space Casting + single canonical reference (never frame-chaining),
structured outputs + self-healing Critic→Director loop with engine re-routing,
human describes & validates per step — the factory composes the winners.
```

---
*Maximal-quality path. For the leaner recommended route see `ideal_status_hybrid.md`; for the
single-billing Vertex-only route see `ideal_status_google_native.md`.*
