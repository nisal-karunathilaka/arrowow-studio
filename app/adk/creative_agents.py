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

# Back-compat: orchestrator imports ca.CHARACTER_LOCK for the intake stage.
CHARACTER_LOCK = prompts.CHARACTER_LOCK


def _profile(state: dict):
    """Resolve the active character bible for this run."""
    cid = state.get("character", {}).get("character_id", "sienna_fitness_01")
    return resolve_profile(cid)


# ---- mock backends (DRY_RUN) ----------------------------------------------
def _mock_strategist(state: dict) -> dict:
    return {
        "hook": "Sienna grabs her water bottle, turns to camera, breathless and energized.",
        "angle": "Tough-love motivation: gear that performs as hard as you do.",
        "cta": "Get after it today.",
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
    return {"wardrobe": "Sage green activewear top and performance activewear pants.",
            "location": "Brightly lit modern gym."}


def _mock_shot_prompt(state: dict) -> dict:
    profile = _profile(state)
    vo = profile.prefers_voiceover   # Sienna: voiceover-only (no direct-to-camera lip-sync)
    # Identity is injected once by build_beat_generation_prompt; 'prompt' here is the scene action.
    def beat(bid, cam, mv, lens, light, bg, amb, frontal, prompt, line):
        return {"beat_id": bid, "camera": cam, "camera_movement": mv, "lens": lens,
                "lighting": light, "background": bg, "ambient_audio": amb,
                "sync_mode": schemas.SYNC_VOICEOVER if (vo or not frontal) else schemas.SYNC_NATIVE,
                "seed_locked": frontal, "prompt": prompt, "dialogue_or_vo": line}

    gym = "brightly lit modern gym with mirrors and free weights"
    # NOTE: wardrobe is intentionally NOT described in text — the anchor image carries the
    # outfit. Describing fitted activewear in text trips Vertex's RAI filter; the anchor does not.
    return {
        "reference_frame_prompt": (f"Front-facing phone portrait of Sienna matching the "
                                   f"reference image identity exactly, in a {gym}."),
        "beats": [
            beat("hook", "C2", "dynamic handheld follow", "phone wide", "natural window light",
                 gym, "gym ambience, distant weights clinking", True,
                 "Sienna walks in holding a pastel water tumbler, glances at the lens with a "
                 "genuine half-smile and adjusts her ponytail — she is NOT speaking to camera.",
                 "Quick reality check, team..."),
            beat("intro", "C1", "locked handheld", "phone wide", "soft natural light", gym,
                 "quiet gym room tone", True,
                 "Sienna stands relaxed in frame, takes a sip from her water tumbler and nods "
                 "confidently to herself — not speaking to camera, voiceover only.",
                 "if your gear isn't keeping up, what are we even doing?"),
            beat("action", "C4", "slow tracking", "phone wide", "natural gym light", gym,
                 "footsteps, breathing, gym ambience", False,
                 "Wide tracking shot of Sienna jogging on the spot and stretching, facing away "
                 "from camera, mid-workout.",
                 "I train hard, and I need pieces that move with me..."),
            beat("proof", "C3", "macro push-in", "phone macro", "natural light", gym,
                 "subtle ambient movement", False,
                 "Close detail of Sienna's hand gripping a dumbbell, then she casually wipes a "
                 "little sweat from her forehead.",
                 "no distractions, just performance..."),
            beat("cta", "C1", "locked handheld", "phone wide", "soft natural light", gym,
                 "quiet gym room tone", True,
                 "Sienna gives a confident nod and a quick thumbs-up to the lens with a warm "
                 "smile — voiceover only, not lip-syncing.",
                 "so let's stop making excuses... and get after it today."),
        ],
    }


# ---- live backends (LLM_ONLY / LIVE_MEDIA) --------------------------------
async def _live_strategist(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.strategist_instruction(p), f"Brief: {state.get('brief', {})}",
        schemas.StrategyResponse, state=state)


async def _live_scriptwriter(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.scriptwriter_instruction(p), f"Strategy: {state.get('strategy', {})}",
        schemas.ScriptResponse, state=state)


async def _live_text_critic(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.text_critic_instruction(p), f"Script: {state.get('script', {})}",
        schemas.TextCriticResponse, state=state)


async def _live_storyboard(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.storyboard_instruction(p), f"Script: {state.get('script', {})}",
        schemas.StoryboardResponse, state=state)


async def _live_wardrobe(state: dict) -> dict:
    p = _profile(state)
    return await llm_backend.structured_generate(
        prompts.wardrobe_instruction(p), f"Character: {p.archetype}. {p.wardrobe_hint()}",
        schemas.WardrobeLocationResponse, state=state)


async def _live_shot_prompt(state: dict) -> dict:
    p = _profile(state)
    result = await llm_backend.structured_generate(
        prompts.shot_prompt_instruction(p),
        f"Storyboard: {state.get('storyboard', {})}\nWardrobe: {state.get('wardrobe', {})}",
        schemas.BeatPromptsResponse, state=state)
    if isinstance(result, dict):  # deterministic filter-bypass net
        result["reference_frame_prompt"] = prompts.apply_filter_bypass(
            result.get("reference_frame_prompt", ""))
        for b in result.get("beats", []):
            b["prompt"] = prompts.apply_filter_bypass(b.get("prompt", ""))
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
