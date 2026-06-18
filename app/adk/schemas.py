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
    prompt: str                # the assembled generation prompt
    dialogue_or_vo: str        # spoken line (native) or voiceover (voiceover)


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
    "identity_drift", # face/body differs from the character bible
    "artifact",       # warping, extra fingers, morphing
    "color",          # grade/white-balance/exposure inconsistency
    "pacing",         # beat too long/short, energy mismatch
    "framing",        # composition/camera issues
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
    continuity_score: int = 0  # 0..10 (character + color consistency)
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
