"""
Arrowow Studio — Prompt Library (production-grade, bible + realism driven)
=========================================================================

Every agent instruction and every generation prompt is assembled here from two
inputs: the CharacterProfile bible (identity, voice, persona, brand) and the
RealismProfile (anti-hyperrealism). Keeping all prompt text in one module makes the
behaviour of each agent auditable and tunable in one place.

Filter-bypass: a deterministic net rewrites RAI-tripping terms into safe equivalents.
"""
from __future__ import annotations

from typing import List

from .profiles.character import CharacterProfile
from .profiles.realism import RealismProfile, UGC_REALISM

# Extra blanket terms beyond a profile's own prohibited list.
EXTRA_PROHIBITED = ["squat", "squats", "squat-proof", "sheer", "see-through", "opacity",
                    "show-through", "transparency", "sports bra", "bra", "tight", "midriff",
                    "cleavage", "form-fitting", "chest up"]

FILTER_BYPASS = {
    "squat-proof": "performance-tested", "squats": "deep athletic knee bends",
    "squat": "deep athletic knee bend", "form-fitting": "performance", "tight leggings":
    "performance activewear pants", "tight": "performance", "sports bra": "activewear top",
    "midriff": "upper torso", "cleavage": "upper torso", "chest up": "upper torso",
    "sheer": "", "see-through": "", "opacity": "",
}

# Back-compat constant (older modules import prompts.CHARACTER_LOCK).
CHARACTER_LOCK = ("Athletic 26-year-old Australian female, sun-kissed skin, messy blonde "
                  "hair in a claw clip, bright blue eyes, minimal clean-girl makeup")


def apply_filter_bypass(text: str) -> str:
    """Rewrite banned terms into safe equivalents (deterministic safety net)."""
    if not text:
        return text
    out = text
    for banned, safe in FILTER_BYPASS.items():
        if banned in out.lower():
            out = out.replace(banned, safe).replace(banned.capitalize(), safe)
    return " ".join(out.split())


def _prohibited_clause(profile: CharacterProfile) -> str:
    terms = list(dict.fromkeys(list(profile.prohibited_terms) + EXTRA_PROHIBITED))
    return (" You must NEVER use these prohibited phrases/concepts: "
            + ", ".join(f"'{t}'" for t in terms)
            + ". Focus purely on performance, energy and style.")


# ---- agent system instructions -------------------------------------------
def strategist_instruction(profile: CharacterProfile) -> str:
    return (
        f"You are a senior Creative Strategist for high-performing short-form UGC ads. "
        f"The talent is {profile.display_name}, {profile.archetype}. {profile.brand_block()} "
        f"From the brief, craft a scroll-stopping HOOK (first 2s), a clear ANGLE, and a "
        f"punchy CTA for a 30-second vertical video. {profile.persona_direction()}"
        + _prohibited_clause(profile)
    )


def scriptwriter_instruction(profile: CharacterProfile) -> str:
    return (
        f"You are an expert UGC scriptwriter writing for {profile.display_name}. "
        f"{profile.persona_direction()} Write a single ~30-second spoken script as a 5-beat "
        f"arc: HOOK (0-3s, direct to camera) -> INTRO (3-10s, direct to camera, the premise) "
        f"-> ACTION (10-20s, voiceover over her moving/working out) -> PROOF (20-27s, "
        f"voiceover over a close detail) -> CTA (27-30s, back to camera). Mark each segment "
        f"[HOOK]/[INTRO]/[ACTION]/[PROOF]/[CTA]. Use ellipses (...) for natural breath pauses "
        f"and CAPITALIZE stressed words. Keep it real and conversational, never salesy."
        + _prohibited_clause(profile)
    )


def text_critic_instruction(profile: CharacterProfile) -> str:
    return (
        f"You are a strict brand-safety + tone QA critic for {profile.display_name}. "
        f"{profile.brand_block()} Approve ONLY if the script avoids every prohibited phrase, "
        f"matches her tone ({profile.persona.speaking_tone}), and fits the 5-beat 30s arc; "
        f"otherwise reject with specific, actionable feedback." + _prohibited_clause(profile)
    )


def storyboard_instruction(profile: CharacterProfile) -> str:
    return (
        "You are a Storyboard Director for authentic UGC. Plan EXACTLY 5 beats in order: "
        "1) Hook (kinetic entry, camera C2 dynamic handheld), 2) Intro (direct-to-camera, "
        "C1 frontal close-up), 3) Action (wide demo, character moving/facing away, C4 deep "
        "wide), 4) Proof (macro product/result detail, C3 macro), 5) CTA (back to camera, C1). "
        "Beats 1/2/5 are on-camera dialogue; beats 3/4 are voiceover (no lip-sync risk).\n"
        "CRITICAL STORY CONTINUITY & TRANSITION RULES:\n"
        "- Ensure the physical movements and subject velocity flow naturally between consecutive scenes.\n"
        "- Explicitly match the subject's ending posture in scene i to their starting posture in scene i+1 (e.g. if Scene 3 ends with subject jogging towards the left, Scene 4 should start with the subject already in motion, or transition seamlessly using a motion-matched panning angle).\n"
        "- Plan camera angles and distances so that the transition boundaries are not jarring (e.g. match vectors, clean crossfade alignment).\n"
        "Output scene_actions and scene_cameras as parallel 5-element lists. Keep actions "
        "realistic and shot like a real person filming themselves on a phone."
    )


def wardrobe_instruction(profile: CharacterProfile) -> str:
    w = profile.wardrobe
    return (
        f"You are an Art Director dressing {profile.display_name}. Pick ONE wardrobe and a "
        f"location. Wardrobe style: {w.style}. Choose only from: {', '.join(w.allowed_items)}; "
        f"palette: {', '.join(w.color_palette)}. NEVER use: {', '.join(w.forbidden_items)} "
        f"(they trip safety filters). Location should suit authentic fitness UGC."
    )


def shot_prompt_instruction(profile: CharacterProfile,
                            realism: RealismProfile = UGC_REALISM) -> str:
    return (
        "You are a Prompt Engineer producing a 5-beat shot list for image/video generation. "
        "Return 'reference_frame_prompt' (one canonical front-facing portrait) and a 'beats' "
        "list of EXACTLY 5 items (beat_id in [hook, intro, action, proof, cta], that order). "
        "For each beat provide: camera (hook=C2, intro=C1, action=C4, proof=C3, cta=C1); "
        "camera_movement; lens; lighting; background (the setting); ambient_audio (the room/"
        "background sound bed); sync_mode ('native' for hook/intro/cta, 'voiceover' for action/"
        "proof); seed_locked (true for hook/intro/cta, false otherwise); a detailed 'prompt'; "
        "and 'dialogue_or_vo' (the line for that beat).\n"
        "UPSTREAM SCENE TRANSITION PLANNING:\n"
        "- You must engineer every scene's prompt to maintain absolute body orientation, posture continuity, and motion vectors relative to the adjacent scenes.\n"
        "- Add explicit pose-matching descriptors at the boundaries of adjacent scenes (e.g. 'Scene starts matching the ending pose of the previous scene').\n"
        "CHARACTER LOCK — describe the subject in EVERY prompt using EXACTLY: "
        f"'{profile.casting_block()}'. Never use a real person's name or celebrity likeness.\n"
        f"{realism.directive_block()}"
        + _prohibited_clause(profile)
    )


def qa_instruction(profile: CharacterProfile, realism: RealismProfile = UGC_REALISM) -> str:
    return (
        "You are a senior commercial-video QA reviewer for AI-generated UGC. Watch the video "
        "and grade it like a broadcast deliverable. Score 0-10 each: overall, realism "
        "(higher = more like REAL phone footage, lower = AI/plastic/uncanny), lip_sync, audio, "
        "continuity (does the person match the character bible across shots, is color "
        "consistent).\n"
        "CRITICAL COLOR & REALISM EVALUATION: You must aggressively penalize glossy, hyperrealistic, "
        "saturated, or overly professional cinematic colors (such as warm orange-and-teal grading, "
        "high dynamic range pops, or deep studio saturation). The footage MUST look like flat, raw, "
        "slightly desaturated, un-graded smartphone camera footage. If you see cinematic color grading "
        "or hyper-saturated/glossy hues, you MUST flag it as a 'color' or 'hyperrealism' defect with "
        "a severity of 4 or 5 (meaning it fails approval).\n"
        "CRITICAL MOVEMENT & TRANSITION EVALUATION:\n"
        "- Watch for any unnatural physics, warping, lagging, stuttering, or glitches during actionable scenarios (like running, stretching, walking, or interacting with items like water cups or weights). If hands/items morph or jitter, flag as 'artifact' or 'framing' with high severity.\n"
        "- Watch for visual lagging, frame drop, stuttering, or jumpy discontinuities between scenes, and flag them as 'transition' or 'pacing' defects.\n"
        "List concrete defects, each with: type (one of lip_sync, vocal_audio, "
        "transition, soundtrack, hyperrealism, identity_drift, artifact, color, pacing, "
        "framing), segment (beat id or 'global'), severity 1-5, a description, and a remedy_hint "
        "describing how to fix it. "
        "IMPORTANT — this is a deliberate VOICEOVER UGC style: the talent is usually NOT speaking "
        "to camera (she performs actions while her voice narrates). Do NOT flag lip_sync when she "
        "is not visibly trying to speak synced dialogue to the lens; only flag lip_sync if her "
        "mouth clearly attempts synced speech to camera and fails. "
        "Approve ONLY if overall>=7 AND realism>=7 AND no defect has "
        f"severity>=4. The character should look like: {profile.casting_block()[:160]}... "
        f"and the footage must look real, not AI: {realism.negative_block()}"
    )


# Aligned anti-hyperrealism + filter negative block (the user's canonical list).
NEGATIVE_BLOCK = (
    "--no plastic skin, no airbrushed faces, no over-smooth beauty-filter smoothing, no overly "
    "perfect symmetry, no studio three-point lighting, no glossy cinematic color grade, no floaty "
    "unnatural motion, no HDR over-sharpening, no captions, no subtitles, no watermark, no "
    "on-screen text, no sports bra, no bra, no tight, no midriff, no cleavage, no form-fitting, "
    "no sheer, no see-through, no opaque, no transparency, no show-through, "
    "no saturated colors, no vibrant color grading, no cinematic teal and orange, no studio-graded look, no high-contrast color pop"
)


def build_beat_generation_prompt(beat: dict, profile: CharacterProfile,
                                 realism: RealismProfile = UGC_REALISM,
                                 use_anchor: bool = False) -> str:
    """Assemble the final Veo prompt for one beat. Identity appears ONCE (concise when an
    anchor image is supplied). Native beats get a short-dialogue + lip-sync directive;
    voiceover beats explicitly avoid lip-sync (Sienna's preferred B-roll style)."""
    native = beat.get("sync_mode") == "native"
    identity = profile.casting_block_concise() if use_anchor else profile.casting_block()
    anchor_note = (" The first frame is conditioned on the reference image — keep that exact "
                   "face and identity from every angle.") if use_anchor else ""

    if native:
        perform = ("She speaks a SHORT line directly to camera (under 7 seconds of speech) with "
                   "natural jaw movement and ACCURATE lip-sync to the audio. ")
        line = f'(Sienna, speaking to camera: "{beat.get("dialogue_or_vo","")}")'
    else:
        perform = ("She does NOT look at or speak to the camera — her mouth is closed, she is not speaking, "
                   "no lip-sync or speech movement, voiceover only. ")
        line = ""

    # Structured refinement flag (set by the QA refiner for hyperrealism defects) — appended
    # as a clean directive rather than raw remedy text, to avoid bloating/tripping RAI.
    boost = (" Extra realism: relaxed natural micro-expressions, soft natural eyes (not overly "
             "bright or glassy), subtle natural blinking, no facial stiffness or frozen stare."
             if beat.get("_realism_boost") else "")

    # Structured color desaturation / flattening flag (set by QA refiner for color/hyperrealism defects)
    color_flatten = (" Extra color flattening: flat desaturated color profile, muted natural tones, "
                     "neutral grey/white balance, zero cinematic color grading, raw smartphone camera color science, "
                     "slightly desaturated colors."
                     if beat.get("_color_flatten") else "")

    # Positive description gets the filter-bypass net; the NEGATIVE_BLOCK must stay intact
    # (it intentionally lists the banned words as things to AVOID).
    positive = (
        f"{beat.get('prompt','')}\n"
        f"SUBJECT: {identity}{anchor_note}\n"
        f"CAMERA: {beat.get('camera_movement','handheld')}, {beat.get('lens','phone wide')}, "
        f"angle {beat.get('camera','C1')}. LIGHTING: {beat.get('lighting','natural')}. "
        f"SETTING: {beat.get('background','')}.\n"
        f"PERFORMANCE: {perform}{profile.mannerisms.movement_style}.\n"
        f"{realism.directive_block()}{boost}{color_flatten}\n"
        f"AUDIO: {profile.voice_direction()} Ambient: {beat.get('ambient_audio') or 'natural room tone'}. "
        f"No background music, no sound effects.\n"
        f"{line}"
    )
    return apply_filter_bypass(positive) + "\n" + NEGATIVE_BLOCK
