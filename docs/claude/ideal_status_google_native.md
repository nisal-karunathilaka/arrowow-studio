# ARROWOW STUDIO — IDEAL STATUS · GOOGLE VERTEX-NATIVE
## The Arrowow Directorial Rules Bible & Target Architecture
*A prompt-translatable, agent-executable reference for autonomous 30-second UGC*
*Owner: Claude · Variant: **Google Vertex-native (single vendor, single billing)** · June 2026*

> ## ✅ STATUS: SELECTED / LOCKED — this is the committed target architecture.
> The system design for this path is specified in **`system_design_google_native.md`**.
>
> **THREE VARIANTS EXIST. THIS IS THE SIMPLEST-INFRA PATH (AND THE CHOSEN ONE).**
> - `ideal_status_hybrid.md` — ⭐ **RECOMMENDED.** Google core + targeted external add-ons.
> - `ideal_status_best_in_class.md` — best tool per job, multi-vendor, maximal quality.
> - `ideal_status_google_native.md` — **THIS DOC.** Everything on Vertex AI: Veo 3.1, Cloud TTS,
>   Imagen/Gemini. One vendor, one bill, no external keys — at the cost of native sync/transition
>   ceilings, documented honestly below.
>
> Shared **Directorial Grammar** (§01–§04, §07, §08, §11) is identical across all three. This
> variant diverges in **§05, §06, §09, §10**. Read `current_status.md` first.

---

## 00 · HOW TO USE THIS DOCUMENT

**Your role (every agent):** you are a film crew shooting a 30s UGC ad for a locked character.
Every decision flows from the grammar below; evaluate output against it and flag deviations.

**Assembly order for any shot prompt (never reorder):**
`shot type (A/B-Roll) → camera code → character lock → wardrobe → setting → safety/negative block → audio/sync mode → dialogue/voiceover`

**The Google-native contract in one line:** *one vendor does everything — Veo 3.1 generates video
with native audio + lip inference, Cloud TTS voices the B-Roll, Imagen anchors identity, ffmpeg
stitches — and we engineer **around** the native limits rather than buying our way past them.*

---

## 01 · THE MULTI-AGENT FACTORY

The system evolves from a linear HITL script-runner into an **asynchronous, self-healing
orchestration graph** — all agents on Gemini, all media on Vertex. The human describes a scenario
and **validates each step**; everything else is automatic.

### Orchestration hierarchy
| # | Agent | Consumes | Produces | Model / Tool (Vertex-native) |
|---|---|---|---|---|
| 0 | **Director (Orchestrator)** | Blackboard, Critic verdicts | routing, retries, seed/prompt mutations | **deterministic** (ADK workflow agents — no LLM) |
| 1 | **Creative Strategist** | brief, persona | hook / angle / CTA | **Gemini 3.5 Flash** (low cost) |
| 2 | **Scriptwriter** | strategy, persona | timestamped A-Roll / B-Roll script | **Gemini 3.5 Flash** |
| 3 | **Storyboard & Continuity** | script, persona | beat sheet + camera codes + seed plan | **Gemini 3.5 Flash** |
| 4 | **Prompt Engineer** | storyboard, wardrobe | per-shot Veo payloads + filter-bypass | **Gemini 3.5 Flash** |
| 5 | **Media Assembler / Compositor** | payloads | Veo clips + Cloud TTS VO + ffmpeg master | **Veo 3.1 + Imagen + Cloud TTS + ffmpeg** |
| 6 | **Multi-Modal Critic** | final mp4 | approve / reject + per-defect routing | **Gemini 3.1 Pro** (vision) |

> **Cost note:** the 6 creative/critic steps are the only LLM calls; five run on cheap **Gemini 3.5
> Flash**, and only the vision Critic uses **Gemini 3.1 Pro**. The Director is **deterministic** (ADK
> `SequentialAgent`/`LoopAgent`/`ParallelAgent`), spending **zero** LLM tokens on routing. See
> `system_design_google_native.md` for the full orchestration design.

### The single-gate-per-step human model
User **describes a scenario in natural language**; the Director expands it into the Blackboard and
shows **one validation card per stage** (script → storyboard → key frame → final cut). ✅ approve or
💬 one-line note routed back as a mutation. No terminal `Y/N` chains.

---

## 02 · CORE GRAMMAR OF 30-SECOND UGC

- **Deliberate hybrid format:** A-Roll (direct-to-camera dialogue) + B-Roll (voiceover action).
  Masks seams and protects lip-sync. *In this variant the hybrid split is load-bearing — it is our
  primary lip-sync mitigation, since we have no dedicated sync engine.*
- **Pacing engineered for retention:** Hook → Intro → Action → Proof → CTA.
- **Protagonist locked** via Seed Locking + Latent-Space Casting, never degrading frame-chaining.
- **Three breakers under AI defaults:** generative melting, lip-sync stutter, hard cuts. §05 covers
  how far we can get against each **within Veo's native ceiling.**

---

## 03 · THE 30-SECOND TEMPORAL PACING TIMELINE

| Time | Beat | Action | Camera | Sync mode | Seed |
|---|---|---|---|---|---|
| **0–3s** | **Hook** | kinetic entry / pattern interrupt | **C2** dynamic | Veo native sync (short) | locked |
| **3–10s** | **Intro** | states the premise to viewer | **C1** frontal | **Veo native sync** | locked |
| **10–20s** | **Action** | real-world demo, facing away/moving | **C4/C3** | **Cloud TTS voiceover** | unlocked |
| **20–27s** | **Proof** | close-up payoff / comparison | **C3** macro | **Cloud TTS voiceover** | unlocked |
| **27–30s** | **CTA** | returns to camera, call to action | **C1** frontal | **Veo native sync** | locked |

**Critical tactic:** because native sync is our weakest link, **minimize on-camera dialogue
duration**. Keep Intro and CTA tight (≤6s combined of true close-up talking) and push as much
message as possible into B-Roll voiceover. The shorter the synced segment, the less Veo's
end-of-clip drift shows.

---

## 04 · CAMERA & COMPOSITION CODES

- **C1 · SYMMETRICAL FRONTAL CLOSE-UP** — eye-level, ~70% frame, minimal shake. Intro & CTA. Synced.
- **C2 · DYNAMIC HANDHELD FOLLOW** — visible vlog shake, tracking. Hook only.
- **C3 · MACRO DETAIL INSERT** — tight close on object/result, shallow DOF. Proof.
- **C4 · DEEP-SPACE WIDE** — subject <30% of frame, environment readable. Action.

**DO** default C1 for speaking beats but keep them **short**. **DO** keep the face off-cam/profile
for C3/C4 (no sync needed — Veo native audio just plays as VO). **DON'T** put direct dialogue in
C3/C4; **DON'T** stretch a single synced C1 beyond ~6–7s (drift territory).

---

## 05 · SOLVING THE THREE LIMITATIONS — VERTEX-NATIVE ARCHITECTURE

> **Native principle:** we accept Veo's ceiling and **engineer around it** — shorten synced
> segments, lean on B-Roll masking, and use Imagen + seed for continuity. This is the lowest-cost,
> lowest-complexity path; it will not match Hybrid/Best-in-class on sync polish, and that's the
> explicit trade.

### A. Lip-Sync — Native Veo Inference + Aggressive Masking (NO external engine)
1. **Veo 3.1 native audio + lip inference** for A-Roll (Hook/Intro/CTA). Veo 3.1 is the strongest
   native audio model in 2026 — but native inference still stutters on long/complex phrasing.
2. **Mitigation = duration discipline.** Keep each synced beat short (§03/§04). Short synced beats =
   the regime where Veo's native sync is genuinely acceptable.
3. **Mitigation = scripting.** Scriptwriter favors simple, punchy, open-vowel phrasing in synced
   beats; complex sentences go to B-Roll voiceover.
4. **B-Roll = zero sync risk.** Cloud TTS (`en-AU-Neural2-A` or a Journey/Neural2 voice) carries the
   middle 17s over masked motion. This is the bulk of the message and is sync-free by construction.

*Documented ceiling:* without Sync.so/Hedra, A-Roll sync tops out at "good for short beats," not
"flawless." If a campaign demands flawless long talking-head sync, escalate to the Hybrid variant.

### B. Continuity — Seed Lock + Latent-Space Casting + Imagen Anchor (unchanged doctrine)
1. **Seed lock** `427819` on all A-Roll (C1/C2) Veo generations.
2. **Latent-Space Casting** block in every prompt (immutable physical description).
3. **Imagen reference frame** is the single canonical identity anchor, fed to Veo's image
   conditioning on the **first frame** of each A-Roll. **Never chain** last-frame→next-anchor (that
   was Strategy A's melt). One stable anchor per persona, reused — not regenerated per clip.

### C. Transitions — Programmed + FFmpeg `xfade` (NO generated interpolation)
- **Match cut** — Prompt Engineer makes Scene A end in the posture Scene B begins.
- **Whip pan** — append `[rapid horizontal whip-pan blur]` to the outgoing clip; ffmpeg blends the
  motion-blurred tail into the next head (motion-masked cut, not a true tween).
- **Macro zoom** — C3 zoom-in masks the environment change.
- **`xfade` / audio L-cut** — ffmpeg `xfade` for soft transitions; carry audio across the cut to
  smooth it.

*Documented ceiling:* no Luma/Runway frame-interpolation means hero morph-transitions aren't
available — we rely on motion-masking + xfade. Good enough for authentic-vlog UGC; not for
high-gloss morphs.

### Vertex-native pipeline diagram
```
scenario ─▶ Director ─▶ Strategist ─▶ Scriptwriter ─▶ Storyboard ─▶ Prompt Eng
                                                                       │
                                                                       ▼
   Imagen (canonical reference frame) ─────────────▶ Veo 3.1 (A-Roll, seed-lock, native sync, SHORT)
   Cloud TTS (en-AU) ──────────────────────────────▶ Veo 3.1 (B-Roll action, voiceover over)
                                                                       │
                          ffmpeg Compositor (match-cut / whip-pan motion-mask / xfade)
                                                                       ▼
                              Gemini 3.1 Pro Multi-Modal Critic ─▶ (reject → Director)
                                                                       ▼
                                                            30s master.mp4
```

---

## 06 · THE TOOL LANDSCAPE (2026) — WHY STAY NATIVE

| Job | Vertex-native choice | Native strength | What we give up (vs other variants) |
|---|---|---|---|
| Video gen | **Veo 3.1** | best all-round realism, native audio, 4K, prompt adherence | Kling's 15s single-pass; Runway's camera control |
| Reference image | **Imagen / Gemini 3.1 Flash Image** | integrated, cheap, fast | Midjourney/Flux aesthetics |
| Voice | **Cloud TTS** (`en-AU-Neural2-A` / Journey) | already wired, cheap ($0.000016/char) | ElevenLabs' breath/cadence realism |
| Lip-sync | **Veo native inference** | no extra vendor/key/latency | Sync.so/Hedra precision |
| Compositing | **ffmpeg** | scriptable, free | Luma/Runway generated tweening |
| Creative reasoning | **Gemini 3.5 Flash** | cheap, fast, structured output; the 5 non-vision agents | Gemini 3.1 Pro (overkill/costly here) |
| Vision critique | **Gemini 3.1 Pro** | multimodal video QA; the one place Pro earns its cost | — |

**The case for native:** one bill, one set of credentials, one rate-limit regime, no PII/audio
leaving Google, and Veo 3.1 genuinely *is* the best all-round 2026 video model — so the pixels are
already top-tier. **The cost of native:** sync polish and hero transitions plateau. Track whether
campaigns actually hit that ceiling; if they do, the same grammar lifts cleanly into Hybrid.

**Category leaders (reference):** Arcads (motion-capture actors, batched hook/body/CTA, $16M Dec
2025), Captions AI (short-form vertical), HeyGen (multilingual avatars). A Vertex-native Arrowow
trades their specialized sync/avatar tech for **infra simplicity + single-vendor cost control.**

---

## 07 · PROMPT TEMPLATES & FILTER-BYPASS DICTIONARY

Filter map (Prompt Engineer must apply): squat → *deep athletic knee bend* · form-fitting/tight →
*performance activewear* · sports bra/midriff/chest → *activewear top / upper torso* · sheer/
see-through/opacity → *(drop; describe color + fabric only)*.

### Template A — A-Roll (C1/C2, Veo native sync, keep SHORT)
```text
[C1 SYMMETRICAL FRONTAL CLOSE-UP] Continuous talking-head vlog shot of Sienna looking into the lens,
speaking energetically. Keep the spoken line short and punchy.
[CHARACTER LOCK: Athletic 26-year-old Australian female, sun-kissed skin, messy blonde hair in a
claw clip, bright blue eyes, minimal clean-girl makeup.]
Wearing a modest, loose-fitting sage green activewear top. Brightly lit modern gym.
Strictly no captions/subtitles. Audio: clear energetic native Australian female voice, natural
breathing, realistic jaw cadence, no background music.
(Sienna: "Quick reality check, team...")
```
*(Vertex-native: let Veo render audio + lips natively; do NOT exceed ~6–7s of on-cam dialogue.)*

### Template B — B-Roll (C4, Cloud TTS voiceover)
```text
[C4 DEEP-SPACE WIDE] Cinematic tracking shot of Sienna performing a deep athletic knee bend, facing
away from camera, demonstrating her sage green performance activewear pants. Camera slowly pans in a
brightly lit modern gym.
[CHARACTER LOCK: ...same block...]
Strictly no captions. No direct eye contact with camera.
(Voiceover [Cloud TTS en-AU]: "...if your gear isn't holding up, what are we even doing? Let's get
after it.")
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

1. **Structured outputs only** (Gemini function-calling / strict schemas). Delete
   `clean_and_parse_json` and `main.py` key-probing; a schema violation is a hard error.
2. **One canonical shape per stage**, versioned in `schemas/`; Blackboard validates on write.
3. **Structured defects from the Critic:** `{defect, segment, severity}` → Director maps to targeted
   fix: `lip_sync` → **shorten/re-script that synced beat or re-roll seed** (no external sync engine
   to call here); `identity_drift` → regenerate clip w/ reinforced lock + same seed; `artifact` →
   seed +1 + tighter negative; `pacing` → trim beat.
4. **Bounded retries (≤3/segment)**, cost-aware, before escalating to the human.

---

## 09 · MCP & EXTERNAL-RESOURCE INTEGRATION PLAN (VERTEX-NATIVE)

Minimal external surface by design. Everything is Vertex; the only "integration" work is internal
structure + optional MCP exposure of our own pipeline.

| Capability | Integration | Step |
|---|---|---|
| Veo 3.1 / Imagen | existing `live_providers.py` (keep, extend for multi-clip) | done / Phase 1 |
| Cloud TTS | re-activate `GoogleTTSProvider` (currently unused) for B-Roll VO | Phase 2 |
| Compositor | `kernel/compositor.py` (ffmpeg match-cut/whip-pan/xfade) | Phase 3 |
| MCP exposure (optional) | wrap the Arrowow pipeline itself as one MCP server for external Claude orchestration | Phase 3+ |

**Secrets:** only GCP credentials — but still **never** a committed `google-credentials.json`. Move
to env/secret manager and rotate the leaked key first (see `current_status.md` §8). Single-vendor
means a single, simple rotation story — a real operational advantage of this variant.

---

## 10 · PHASED IMPLEMENTATION ROADMAP (VERTEX-NATIVE)

### Phase 1 — Orchestration & Robustness (Weeks 1–4)
- Async Director loop; single-gate-per-step; structured outputs (§08).
- Filter-bypass dictionary as shared config.
- **Lift the 2-video cap** (a 30s native asset needs 4+ Veo clips); re-price ledger to real Veo 3.1
  rates (~$0.15/s) — note this variant has the **simplest** cost model (one vendor).
- ✅ *Accept when:* a scenario runs end-to-end at current ~15s output with zero JSON-parse failures.

### Phase 2 — B-Roll Voiceover + Duration Discipline (Weeks 5–8)
- Re-activate Cloud TTS for all B-Roll voiceover; Scriptwriter enforces short synced beats + simple
  phrasing for A-Roll.
- ✅ *Accept when:* on 10 sample scripts, ≥80% of the message lives in sync-free B-Roll VO and A-Roll
  synced beats stay ≤7s, with Critic native-sync scores ≥7/10.

### Phase 3 — Compositor, 30s Assembly, Autonomy (Weeks 9–14)
- Build `compositor.py` (match-cut / whip-pan motion-mask / xfade); assemble full 5-beat 30s
  timeline from multiple Veo clips + Imagen anchor + Cloud TTS VO.
- Activate Critic→Director self-healing (re-script/re-seed strategies; no external sync engine).
- ✅ *Accept when:* unattended 30s asset, no visible seams, consistent identity across 5 beats, ≤1
  human note, on 8/10 scenarios — accepting "good short-beat sync" as the native bar.

> **Escalation trigger:** if Phase 2/3 acceptance repeatedly fails on lip-sync alone (not identity,
> not pacing), that is the signal to graduate to `ideal_status_hybrid.md` and bolt on Sync.so +
> ElevenLabs — the grammar and roadmap carry over unchanged.

---

## 11 · THE TEN NON-NEGOTIABLES + QUICK-REFERENCE CARD

### Ten Non-Negotiables
1. A 30s asset is **5 beats**, never one shot (Hook/Intro/Action/Proof/CTA).
2. Only Hook/Intro/CTA are on-camera-synced, kept **SHORT**; the middle is **Cloud TTS voiceover**.
3. Native sync is the weak link → **minimize on-cam dialogue duration** and simplify synced phrasing.
4. **Seed-lock A-Roll** (`427819`); never seed-lock a different B-Roll composition.
5. **Latent-Space Casting** block in **every** prompt — identity from text, not chained frames.
6. **One Imagen anchor per persona, reused** — never chain last-frame→next-anchor.
7. Transitions are **programmed + ffmpeg xfade/motion-mask**, never bare concat.
8. **Structured outputs only** — a schema violation is an error, not a fallback.
9. Critic returns **structured defects** → re-script / re-seed targeted fixes (no sync vendor here).
10. The human **describes + validates**; the factory **executes** on one vendor. One gate per step.

### The Universal Style Anchor (memorize)
```
Autonomous 30s UGC on Vertex only: 5-beat retention arc,
hybrid A-Roll(Veo native sync, SHORT, seed-locked, C1) + B-Roll(Cloud TTS voiceover, masked, C3/C4),
Veo 3.1 pixels + Imagen anchor + Cloud TTS voice + ffmpeg transitions,
identity via seed-lock + Latent-Space Casting + one reused anchor (never frame-chaining),
engineer AROUND native sync limits via duration discipline + B-Roll masking,
structured outputs + self-healing Critic→Director loop,
one vendor, one bill — escalate to Hybrid only if lip-sync alone fails acceptance.
```

---
*Simplest-infra path. For the recommended balance see `ideal_status_hybrid.md`; for maximal quality
see `ideal_status_best_in_class.md`.*
