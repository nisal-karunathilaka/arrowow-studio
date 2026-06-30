"""
Arrowow Studio — Data Contracts (Pydantic)
==========================================

Single source of truth for every agent's structured output (system design §4),
extended for Phase 3 with scene-by-scene detail and a full QA defect taxonomy.

Pre-production / planning schemas are reused from Phases 1-2; BeatPrompt is enriched
into a full per-scene spec, and QAReport replaces the thin video-critic output.
"""
from __future__ import annotations

from typing import List

import pydantic


# ---- Pre-production -------------------------------------------------------
class StrategyResponse(pydantic.BaseModel):
    hook: str
    angle: str
    cta: str
    product: str = pydantic.Field(
        default="",
        description="The exact hero product/item being advertised, taken verbatim from the brief "
                    "(e.g. 'seamless training shoe', 'high-waisted leggings'). This is the visual "
                    "hero the camera must feature in every relevant beat.")
    product_design: str = pydantic.Field(
        default="",
        description="A PRECISE, FIXED visual description of the hero product so it looks IDENTICAL "
                    "in every shot (colour, material, silhouette, sole/details). E.g. 'a solid "
                    "sage-green knit running shoe with a smooth white foam midsole, no visible "
                    "holes, white laces'. Pick concrete choices and commit — this is the product's "
                    "identity lock.")
    key_selling_points: List[str] = pydantic.Field(
        default_factory=list,
        description="3-5 concrete product benefits the visuals must demonstrate (e.g. 'grippy "
                    "sole', 'flexible knit', 'all-day cushion'), drawn from the brief.")
    soundtrack: str = pydantic.Field(
        default="fast_electronic",
        description="The background soundtrack category that matches the campaign tone "
                    "(e.g., 'fast_electronic', 'hip_hop', 'serene_instrumental').")


class ScriptResponse(pydantic.BaseModel):
    script_text: str
    estimated_duration_seconds: int


class TextCriticResponse(pydantic.BaseModel):
    approved: bool
    feedback: str
    brand_safety_score: float


# ---- Visual planning ------------------------------------------------------
class StoryboardResponse(pydantic.BaseModel):
    scene_actions: List[str]
    scene_cameras: List[str]


class WardrobeLocationResponse(pydantic.BaseModel):
    wardrobe: str
    location: str
    hair_style: str = pydantic.Field(
        default="",
        description="Context-appropriate HAIR STYLING only (e.g. 'sleek high ponytail', 'loose "
                    "beach waves'). Adapts to the campaign; the hair COLOUR/length/texture are "
                    "fixed by the character bible and must not change.")
    makeup: str = pydantic.Field(
        default="",
        description="Context-appropriate makeup look (e.g. 'clean natural no-makeup glow', 'soft "
                    "dewy'). Adapts to the campaign; facial FEATURES stay fixed.")
    product_styling: str = pydantic.Field(
        default="",
        description="How the hero product is worn/held/placed so it reads as the visual hero.")


BEAT_IDS = ["hook", "intro", "action", "proof", "cta"]
SYNC_NATIVE = "native"        # on-camera dialogue, Veo native sync, seed-locked
SYNC_VOICEOVER = "voiceover"  # masked motion, Cloud TTS voiceover, seed unlocked


class BeatPrompt(pydantic.BaseModel):
    """A full per-scene specification (camera, lens, lighting, background, audio)."""
    beat_id: str               # one of BEAT_IDS
    camera: str                # C1..C4 angle code
    camera_movement: str = "locked phone handheld"
    lens: str = "phone wide-angle"
    lighting: str = "natural available light"
    background: str = ""       # the setting / environment
    ambient_audio: str = ""    # background/room audio bed
    sync_mode: str             # native | voiceover
    seed_locked: bool
    prompt: str                # the assembled generation prompt (visuals realizing the brief beat)
    dialogue_or_vo: str        # spoken line (native) or voiceover (voiceover)
    start_frame_prompt: str = pydantic.Field(
        default="",
        description="The visual prompt explicitly describing the STARTING frame for this beat.")
    end_frame_prompt: str = pydantic.Field(
        default="",
        description="The visual prompt explicitly describing the ENDING frame for this beat. Must exactly match the start frame of the next beat.")
    product_action: str = pydantic.Field(
        default="",
        description="What the hero product does / how it is featured in this beat (e.g. 'sole grips "
                    "the floor on the box-jump landing', 'creator slips the shoe on'). Empty only "
                    "if the product genuinely cannot appear in this beat.")
    on_screen_text: str = pydantic.Field(
        default="",
        description="Caption/overlay text for this beat, taken from the brief if specified "
                    "(e.g. 'Lock-in support 🔥'). Rendered as a post-production overlay, not by Veo.")
    features_person: bool = pydantic.Field(
        default=True,
        description="True if the talent (her face or body) appears in this beat — the identity "
                    "anchor image is then applied to keep her consistent. Set False ONLY for a pure "
                    "product-only object shot with NO human visible (then no anchor is used).")


class BeatPromptsResponse(pydantic.BaseModel):
    reference_frame_prompt: str
    beats: List[BeatPrompt]    # exactly 5, in timeline order


# ---- QA / Production critique (full taxonomy) -----------------------------
# Defect dimensions a commercial-video QA reviewer checks, each maps to a remedy.
DEFECT_TYPES = [
    "lip_sync",       # mouth not matching audio
    "vocal_audio",    # voice quality, accent, robotic TTS, clipping
    "transition",     # jarring/seam between beats
    "soundtrack",     # music/ambient bed issues, levels
    "hyperrealism",   # looks too AI/plastic/uncanny (anti-realism)
    "identity_drift", # FACE/voice/core features differ from the bible (NOT wardrobe — that may adapt)
    "artifact",       # warping, extra fingers, morphing
    "color",          # grade/white-balance/exposure inconsistency
    "pacing",         # beat too long/short, energy mismatch
    "framing",        # composition/camera issues
    "brief_adherence",# the video fails to realize what the brief described for this beat
    "product",        # the hero product is missing, wrong, or not the visual hero
    "ending_state",   # the final frame of the clip is blurry, occluded, or morphed (prevents chaining)
]


class QADefect(pydantic.BaseModel):
    type: str                  # one of DEFECT_TYPES
    segment: str               # beat id or "global"
    severity: int              # 1 (minor) .. 5 (blocking)
    description: str = ""
    remedy_hint: str = ""


class QAReport(pydantic.BaseModel):
    approved: bool
    overall_score: int = 0     # 0..10
    realism_score: int = 0     # 0..10 (anti-hyperrealism — higher = more human)
    lip_sync_score: int = 0    # 0..10
    audio_score: int = 0       # 0..10
    continuity_score: int = 0  # 0..10 (FACE/voice identity + colour consistency across beats)
    ending_state_score: int = pydantic.Field(
        default=0, description="0..10 — how sharp, clean, and unoccluded the final frame of the video is. Crucial for chaining shots.")
    brief_adherence_score: int = pydantic.Field(
        default=0, description="0..10 — how faithfully the video realizes the brief's described "
                               "beats, actions, and message. Low if described visuals are missing.")
    product_visibility_score: int = pydantic.Field(
        default=0, description="0..10 — how clearly the hero product is shown and framed as the "
                               "visual hero across the ad.")
    defects: List[QADefect] = []
    summary: str = ""


# ---- Legacy aliases (kept for back-compat) --------------------------------
class Defect(pydantic.BaseModel):
    type: str
    segment: str
    severity: int


class VideoCriticResponse(pydantic.BaseModel):
    approved: bool
    defects: List[Defect] = []
    production_grade_score: int = 0
