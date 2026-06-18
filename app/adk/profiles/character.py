"""
Arrowow Studio — Character Bible
================================

A production-grade, reusable character profile ("the bible") following standard AI
film-making casting practice. It is the single source of truth for identity and is
injectable into ANY model (image, video, TTS) to hold character consistency across
shots — the professional evolution of "Latent-Space Casting".

Design goals:
  • Granular, immutable physical identity → consistent face/body across renders.
  • A voice profile → consistent vocal identity for TTS / audio direction.
  • A wardrobe SYSTEM (rules, not one outfit) → brand-safe variety without drift.
  • Mannerisms / persona → consistent performance and verbal tone.
  • Brand-guideline slots → drop in any brand and "play" the character on-brand.
  • Filter-safe rendering helpers → casting_block() / voice_direction() etc.

Every field is typed so the bible can be serialized, versioned, and handed to a model.
"""
from __future__ import annotations

from typing import List, Optional

import pydantic


class FacialIdentity(pydantic.BaseModel):
    face_shape: str
    skin_tone: str
    skin_texture: str               # realism: pores/freckles/fine lines, NOT airbrushed
    distinguishing_marks: str       # freckles, beauty mark — identity anchors
    eyes: str                       # color + shape
    eyebrows: str
    nose: str
    lips: str
    jawline: str


class HairIdentity(pydantic.BaseModel):
    color: str
    length: str
    style: str
    texture: str


class BodyIdentity(pydantic.BaseModel):
    build: str
    height: str
    proportions: str
    posture: str


class VoiceProfile(pydantic.BaseModel):
    accent: str
    timbre: str                     # warm/bright/raspy
    pitch: str
    pace: str
    energy: str
    vocal_quirks: str               # breath, slight vocal fry, natural imperfection
    tts_voice_id: str               # concrete Cloud TTS voice


class WardrobeSystem(pydantic.BaseModel):
    style: str
    allowed_items: List[str]        # filter-safe vocabulary
    color_palette: List[str]
    forbidden_items: List[str]      # words that trip RAI filters


class Mannerisms(pydantic.BaseModel):
    signature_gestures: List[str]
    micro_expressions: List[str]
    energy: str
    movement_style: str


class PersonaVoice(pydantic.BaseModel):
    """The VERBAL persona (how she talks), distinct from the acoustic VoiceProfile."""
    traits: List[str]
    speaking_tone: str
    vocabulary: str
    audience: str


class BrandGuidelines(pydantic.BaseModel):
    brand_name: str
    product: str
    values: List[str]
    tone_do: List[str]
    tone_dont: List[str]


class CharacterProfile(pydantic.BaseModel):
    character_id: str
    display_name: str
    archetype: str
    age: int
    gender: str
    nationality: str
    ethnicity: str

    face: FacialIdentity
    hair: HairIdentity
    body: BodyIdentity
    voice: VoiceProfile
    wardrobe: WardrobeSystem
    mannerisms: Mannerisms
    persona: PersonaVoice
    brand: Optional[BrandGuidelines] = None

    seed: int                       # consistency anchor for seed-locked A-roll
    prohibited_terms: List[str]

    # Consistency / behaviour anchors (system: One-Anchor Rule + voiceover style)
    anchor_image_uri: Optional[str] = None   # single canonical reference image
    prefers_voiceover: bool = False          # True -> avoid direct-to-camera lip-sync
    catchphrases: List[str] = []
    settings: List[str] = []

    # ---- render helpers (what gets injected into prompts) -----------------
    def resolve_anchor(self) -> Optional[str]:
        """Return the local anchor-image path if it exists (else None)."""
        import os
        for p in [self.anchor_image_uri,
                  f"app/persona_vault/{self.character_id}/anchor_front.png",
                  "app/adk/profiles/anchor_front.png"]:
            if p and os.path.exists(p):
                return p
        return None

    def casting_block_concise(self) -> str:
        """Short identity block for use WHEN an anchor image is supplied (the image
        carries the face; text just reinforces the non-negotiable identity cues)."""
        f, h, b = self.face, self.hair, self.body
        return (
            f"{self.display_name} — a {self.age}-year-old {self.nationality} {self.gender}, "
            f"{f.skin_tone} skin with {f.distinguishing_marks}, {f.eyes}, "
            f"{h.color} hair in a {h.style}, {b.build} build. "
            f"Match the reference image identity EXACTLY."
        )

    def casting_block(self) -> str:
        """Immutable physical-identity block for image/video prompts. Filter-safe and
        detailed enough to hold the same face/body across shots."""
        f, h, b = self.face, self.hair, self.body
        return (
            f"{self.display_name}: a {self.age}-year-old {self.nationality} {self.gender}, "
            f"{self.ethnicity}. Face: {f.face_shape}, {f.skin_tone} skin with {f.skin_texture}, "
            f"{f.distinguishing_marks}; {f.eyes}; {f.eyebrows}; {f.nose}; {f.lips}; {f.jawline}. "
            f"Hair: {h.color}, {h.length}, {h.style}, {h.texture}. "
            f"Body: {b.build} build, {b.height}, {b.proportions}, {b.posture}."
        )

    def voice_direction(self) -> str:
        """Acoustic direction for TTS / audio (and the audio block of video prompts)."""
        v = self.voice
        return (f"{v.accent} accent, {v.timbre} timbre, {v.pitch} pitch, {v.pace} pace, "
                f"{v.energy} energy, with {v.vocal_quirks}.")

    def persona_direction(self) -> str:
        p = self.persona
        return (f"Speaks as {', '.join(p.traits)}; tone {p.speaking_tone}; "
                f"vocabulary {p.vocabulary}; for an audience of {p.audience}.")

    def wardrobe_hint(self) -> str:
        w = self.wardrobe
        return (f"{w.style}; choose from: {', '.join(w.allowed_items)}; "
                f"palette: {', '.join(w.color_palette)}.")

    def brand_block(self) -> str:
        if not self.brand:
            return ""
        bd = self.brand
        return (f"BRAND: {bd.brand_name} — {bd.product}. Values: {', '.join(bd.values)}. "
                f"Do: {', '.join(bd.tone_do)}. Don't: {', '.join(bd.tone_dont)}.")

    def with_brand(self, brand: BrandGuidelines) -> "CharacterProfile":
        """Return a copy of the bible bound to a brand (so the same character plays for
        any brand)."""
        return self.model_copy(update={"brand": brand})
