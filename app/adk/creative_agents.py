"""
Arrowow Studio — Creative Agent Factories
=========================================

The 6 schema-bound creative LlmAgents (Strategist, Scriptwriter, TextCritic,
Storyboard, Wardrobe, ShotPrompt). Each has an output_schema + output_key and NO
tools (avoids the ADK output_schema+tools conflict). The QA/critic agent lives in
qa.py.

Every agent's behaviour is driven by the CharacterProfile bible (resolved per run)
and the production-grade instructions in prompts.py. DRY_RUN uses mock_fn; LLM_ONLY/
LIVE_MEDIA uses the async live_fn (structured output only — no regex fallback).
"""
from __future__ import annotations

from .core import LlmAgent
from . import schemas, prompts, llm_backend
from .profiles.registry import resolve_profile
from .profiles import brands

# Back-compat: orchestrator imports ca.CHARACTER_LOCK for the intake stage.
CHARACTER_LOCK = prompts.CHARACTER_LOCK


def _profile(state: dict):
    """Resolve the active character bible for this run, bound to the brand the user
    selected in the UI (stored under brief.brand_id). Falls back to the house brand."""
    cid = state.get("character", {}).get("character_id", "sienna_fitness_01")
    brand_id = state.get("brief", {}).get("brand_id")
    brand = brands.get_brand(brand_id) if brand_id else None
    return resolve_profile(cid, brand=brand)


def _hitl_suffix(state: dict, key: str) -> str:
    """If a human reviewer rejected a previous version of this segment and left notes,
    return a revision directive to append to the agent's input so it regenerates with
    that feedback in context. Empty string when there is no feedback."""
    fb = (state.get("hitl_feedback") or {}).get(key)
    if not fb:
        return ""
    return ("\n\nREVISION REQUEST — a human reviewer rejected the previous version. Apply "
            f"these changes precisely while keeping everything else on-brand and consistent: {fb}")


# ---- mock backends (DRY_RUN) ----------------------------------------------
def _mock_strategist(state: dict) -> dict:
    brand = state.get("brief", {}).get("brand", "the brand")
    return {
        "hook": "Sienna grabs the product, turns to camera, breathless and energized.",
        "angle": "Tough-love motivation: gear that performs as hard as you do.",
        "cta": "Get after it today.",
        "product": f"{brand} hero product from the brief",
        "product_design": "a solid sage-green hero product with a clean matte finish, consistent "
                          "in every shot",
        "key_selling_points": ["performs under pressure", "all-day comfort", "lightweight"],
    }


def _mock_scriptwriter(state: dict) -> dict:
    return {
        "script_text": (
            "[HOOK] Quick reality check, team... [INTRO] if your gear isn't keeping up, what "
            "are we even doing? ... I train HARD, and I need pieces that move with me... "
            "[ACTION] no distractions, just performance... [PROOF] this is what holds up when "
            "you push... [CTA] so let's stop making excuses... and get after it today."
        ),
        "estimated_duration_seconds": 30,
    }


def _mock_text_critic(state: dict) -> dict:
    return {"approved": True, "feedback": "On-tone, high energy, avoids prohibited terms.",
            "brand_safety_score": 1.0}


def _mock_storyboard(state: dict) -> dict:
    return {
        "scene_actions": [
            "Sienna turns to camera, grabs water bottle (hook).",
            "Sienna addresses viewer, states the premise (intro).",
            "Wide shot: Sienna performing a deep athletic knee bend, facing away (action).",
            "Macro: close-up on the fabric stretch and recovery (proof).",
            "Sienna returns to camera with the call to action (cta).",
        ],
        "scene_cameras": ["C2", "C1", "C4", "C3", "C1"],
    }


def _mock_wardrobe(state: dict) -> dict:
    return {"wardrobe": "Solid sage-green seamless activewear set.",
            "location": "Brightly lit modern gym.",
            "hair_style": "sleek high ponytail",
            "makeup": "clean natural no-makeup glow",
            "product_styling": "the hero product worn/held front-and-center as the visual focus."}


def _mock_shot_prompt(state: dict) -> dict:
    profile = _profile(state)
    vo = profile.prefers_voiceover   # Sienna: voiceover-only (no direct-to-camera lip-sync)
    # Identity is injected once by build_beat_generation_prompt; 'prompt' here is the scene action.
    def beat(bid, cam, mv, lens, light, bg, amb, frontal, prompt, line, **extras):
        d = {"beat_id": bid, "camera": cam, "camera_movement": mv, "lens": lens,
             "lighting": light, "background": bg, "ambient_audio": amb,
             "sync_mode": schemas.SYNC_VOICEOVER if (vo or not frontal) else schemas.SYNC_NATIVE,
             "seed_locked": frontal, "prompt": prompt, "dialogue_or_vo": line}
        d.update(extras)
        return d

    gym = "brightly lit modern gym with free weights and equipment — empty, no other people visible"
    product = (state.get("strategy", {}).get("product")
               or f"{state.get('brief', {}).get('brand', 'the brand')} hero product")
    # NOTE: wardrobe is intentionally NOT described in text — the anchor image carries the
    # outfit. Describing fitted activewear in text trips Vertex's RAI filter; the anchor does not.
    return {
        "reference_frame_prompt": (f"Front-facing phone portrait of Sienna matching the "
                                   f"reference image identity exactly, in a {gym}."),
        "beats": [
            beat("hook", "C2", "dynamic handheld follow", "phone wide", "natural window light",
                 gym, "gym ambience, distant weights clinking", True,
                 "Sienna walks briskly into the gym, viewed from behind and to the side. "
                 "Her high ponytail swings — the large tortoiseshell claw clip at the crown "
                 "is clearly visible. She rolls her shoulders with both empty hands. "
                 "No props. She faces away from the camera. Mouth closed.",
                 "Quick reality check, team..."),
            beat("intro", "C1", "slow push-in", "phone wide", "soft natural light", gym,
                 "quiet gym room tone", True,
                 "Sienna stands side-on to the camera and stretches her arms overhead, "
                 "gazing across the gym. From the side, the tortoiseshell claw clip holding "
                 "her high ponytail is clearly visible. Empty hands, no props. "
                 "She looks away from lens. Mouth closed, voiceover only.",
                 "if your gear isn't keeping up, what are we even doing?"),
            beat("action", "C4", "slow tracking", "phone wide", "natural gym light", gym,
                 "footsteps, light breathing, gym ambience", False,
                 "Wide shot: Sienna walks briskly across the gym floor from left to right, "
                 "facing fully away from camera. Her high ponytail with the tortoiseshell "
                 "claw clip at the crown is clearly visible from behind. Empty hands. "
                 "Simple walking, rolling neck. No props, no running. Mouth closed.",
                 "I train hard, and I need pieces that move with me..."),
            beat("proof", "C3", "macro push-in", "phone macro", "natural light", gym,
                 "subtle ambient movement", False,
                 f"Macro hero close-up of the {product} SITTING STILL on a gym bench as the "
                 "visual hero — the product does not move and no hands touch it. Clean static "
                 "product reveal. NO PEOPLE IN FRAME. Object-only shot.",
                 "no distractions, just performance...", _prop_only=True, features_person=False,
                 product_action=f"the {product} is revealed in a clean macro hero shot",
                 on_screen_text="Performs ✅"),
            beat("cta", "C1", "locked handheld", "phone wide", "soft natural light", gym,
                 "quiet gym room tone", True,
                 "Sienna stands in the center of the empty gym near a weight rack, rolls her "
                 "neck slowly and shakes out her hands. She faces sideways, gazing across the "
                 "gym floor — not toward the camera. The tortoiseshell claw clip holding her "
                 "high ponytail is visible from the side. No props. Mouth closed, voiceover only. "
                 "Background is a wall of gym equipment, no reflective surfaces.",
                 "so let's stop making excuses... and get after it today."),
        ],
    }


# ---- live backends (LLM_ONLY / LIVE_MEDIA) --------------------------------
async def _live_strategist(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.strategist_instruction(p),
        f"Brief: {state.get('brief', {})}" + _hitl_suffix(state, "script"),
        schemas.StrategyResponse, state=state)


async def _live_scriptwriter(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.scriptwriter_instruction(p),
        f"Strategy: {state.get('strategy', {})}" + _hitl_suffix(state, "script"),
        schemas.ScriptResponse, state=state)


async def _live_text_critic(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.text_critic_instruction(p), f"Script: {state.get('script', {})}",
        schemas.TextCriticResponse, state=state)


async def _live_storyboard(state: dict) -> dict:
    p = _profile(state)
    no_audio = state.get("brief", {}).get("no_audio_overlay", False)
    context = (f"BRIEF: {state.get('brief', {}).get('scenario', '')}\n"
               f"STRATEGY: {state.get('strategy', {})}\n"
               f"SCRIPT: {state.get('script', {})}")
    return await llm_backend.structured_generate(
        prompts.storyboard_instruction(p, no_audio_overlay=no_audio),
        context + _hitl_suffix(state, "visual_plan"),
        schemas.StoryboardResponse, state=state)


async def _live_wardrobe(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.wardrobe_instruction(p),
        f"Character: {p.archetype}. {p.wardrobe_hint()}" + _hitl_suffix(state, "visual_plan"),
        schemas.WardrobeLocationResponse, state=state)


def _parse_script_dialogue(script_text: str) -> dict[str, str]:
    """Extract per-beat dialogue lines from the LLM script.
    Returns {beat_id: first_sentence_of_that_section}."""
    import re
    beat_map = {"HOOK": "hook", "INTRO": "intro", "ACTION": "action",
                "PROOF": "proof", "CTA": "cta"}
    lines = {}
    for label, bid in beat_map.items():
        m = re.search(rf'\[{label}\](.*?)(?=\[(?:HOOK|INTRO|ACTION|PROOF|CTA)\]|$)',
                      script_text, re.DOTALL | re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # Take the first meaningful sentence (up to . or ...)
            sentence = re.split(r'(?<=[a-zA-Z])\.\.\.|(?<=[a-zA-Z])\.', raw)[0].strip()
            if sentence:
                lines[bid] = sentence[:140]
    return lines


async def _live_shot_prompt(state: dict) -> dict:
    """Generate the 5-beat shot list DYNAMICALLY from the full brief context.

    This is the creative core: the LLM realizes the brief's described beats with the hero
    product featured and the campaign styling applied, anchored to the talent's fixed identity
    (see prompts.shot_prompt_instruction). We no longer substitute a static gym template — the
    brief is followed. Deterministic post-processing then applies the RAI filter-bypass net and
    enforces the voiceover delivery policy for quality."""
    p = _profile(state)
    no_audio = state.get("brief", {}).get("no_audio_overlay", False)

    context = (
        f"BRIEF: {state.get('brief', {}).get('scenario', '')}\n"
        f"STRATEGY (hero product + selling points): {state.get('strategy', {})}\n"
        f"SCRIPT (per-beat voiceover): {state.get('script', {})}\n"
        f"STORYBOARD (scene actions + cameras): {state.get('storyboard', {})}\n"
        f"STYLING (adaptive wardrobe/hair/makeup/product): {state.get('wardrobe', {})}"
    )
    result = await llm_backend.structured_generate(
        prompts.shot_prompt_instruction(p, no_audio_overlay=no_audio),
        context + _hitl_suffix(state, "visual_plan"),
        schemas.BeatPromptsResponse, state=state)

    # Deterministic guardrails: filter-bypass the generated text + enforce the hybrid delivery policy.
    result["reference_frame_prompt"] = prompts.apply_filter_bypass(
        result.get("reference_frame_prompt", ""))
    for b in result.get("beats", []):
        b["prompt"] = prompts.apply_filter_bypass(b.get("prompt", ""))
        bid = b.get("beat_id")
        if no_audio:
            b["sync_mode"] = schemas.SYNC_VOICEOVER
            b["seed_locked"] = False
            b["dialogue_or_vo"] = ""
            b["on_screen_text"] = ""  # natural short-film: no text/caption overlays
            if bid == "proof" and (b.get("camera") == "C3" or "macro" in b.get("camera_movement", "").lower() or not b.get("features_person", True)):
                b["features_person"] = False
                b["_prop_only"] = True
            else:
                b["features_person"] = b.get("features_person", True)
        else:
            if bid in ("hook", "intro", "cta"):
                b["sync_mode"] = schemas.SYNC_VOICEOVER if p.prefers_voiceover else schemas.SYNC_NATIVE
                b["seed_locked"] = True
                b["features_person"] = True
            else: # action, proof
                b["sync_mode"] = schemas.SYNC_VOICEOVER
                b["seed_locked"] = False
                if bid == "proof" and (b.get("camera") == "C3" or "macro" in b.get("camera_movement", "").lower() or not b.get("features_person", True)):
                    b["features_person"] = False
                    b["_prop_only"] = True
                else:
                    b["features_person"] = b.get("features_person", True)
    return result


# ---- factories ------------------------------------------------------------
def build_strategist() -> LlmAgent:
    return LlmAgent("Strategist", schemas.StrategyResponse, "strategy",
                    _mock_strategist, live_fn=_live_strategist)


def build_scriptwriter() -> LlmAgent:
    return LlmAgent("Scriptwriter", schemas.ScriptResponse, "script",
                    _mock_scriptwriter, live_fn=_live_scriptwriter)


def build_text_critic() -> LlmAgent:
    return LlmAgent("TextCritic", schemas.TextCriticResponse, "text_critic",
                    _mock_text_critic, live_fn=_live_text_critic)


def build_storyboard() -> LlmAgent:
    return LlmAgent("Storyboard", schemas.StoryboardResponse, "storyboard",
                    _mock_storyboard, live_fn=_live_storyboard)


def build_wardrobe() -> LlmAgent:
    return LlmAgent("Wardrobe", schemas.WardrobeLocationResponse, "wardrobe",
                    _mock_wardrobe, live_fn=_live_wardrobe)


def build_shot_prompt() -> LlmAgent:
    return LlmAgent("ShotPrompt", schemas.BeatPromptsResponse, "beat_prompts",
                    _mock_shot_prompt, live_fn=_live_shot_prompt)
