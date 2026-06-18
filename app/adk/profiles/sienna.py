"""
Arrowow Studio — Concrete Character: Sienna (sienna_fitness_01)
==============================================================

The canonical fitness/lifestyle UGC creator, defined as a full character bible.
Skin texture, freckles, and vocal imperfections are deliberate — they are what make
generated footage read as a REAL person rather than an airbrushed AI avatar.

Use `SIENNA` directly, or `SIENNA.with_brand(<BrandGuidelines>)` to play any brand.
"""
from __future__ import annotations

from .character import (
    CharacterProfile, FacialIdentity, HairIdentity, BodyIdentity, VoiceProfile,
    WardrobeSystem, Mannerisms, PersonaVoice, BrandGuidelines,
)

SIENNA = CharacterProfile(
    character_id="sienna_fitness_01",
    display_name="Sienna",
    archetype="authentic fitness & lifestyle creator (girl-next-door, not a model)",
    age=26,
    gender="female",
    nationality="Australian",
    ethnicity="fair-skinned Caucasian, sun-kissed",
    face=FacialIdentity(
        face_shape="soft oval face, natural cheekbones",
        skin_tone="warm sun-kissed fair",
        skin_texture="visible natural pores, subtle skin texture, faint sun freckles "
                     "across the nose, NOT airbrushed or plastic",
        distinguishing_marks="light freckling across the nose and cheeks, a small beauty "
                             "mark near the left jaw",
        eyes="bright blue, almond-shaped, with natural lashes",
        eyebrows="full, lightly groomed dark-blonde brows",
        nose="straight, slightly rounded tip",
        lips="medium-full, natural rosy tone, minimal gloss",
        jawline="soft defined jawline",
    ),
    hair=HairIdentity(
        color="natural dark blonde with sun-lightened ends",
        length="long",
        style="messy high ponytail held with a tortoiseshell claw clip, a few loose "
              "face-framing strands",
        texture="straight-to-slightly-wavy, fine, natural movement",
    ),
    body=BodyIdentity(
        build="athletic and toned but natural, not bodybuilder",
        height="around 168 cm",
        proportions="balanced athletic proportions",
        posture="upright, confident, relaxed shoulders",
    ),
    voice=VoiceProfile(
        accent="native Australian (Sydney, casual, energetic — not exaggerated)",
        timbre="warm, slightly bright",
        pitch="mid",
        pace="fast and punchy, high-retention, optimized for Reels/TikTok",
        energy="high energy, encouraging, authentic, slightly breathless as if mid-workout",
        vocal_quirks="natural breaths between phrases, occasional slight vocal fry, "
                     "real conversational imperfection",
        tts_voice_id="en-AU-Neural2-A",
    ),
    wardrobe=WardrobeSystem(
        style="matching seamless activewear sets (Gymshark/Lululemon aesthetic); or an "
              "oversized vintage graphic tee (pump cover) over biker shorts; white chunky "
              "running shoes with high white socks",
        allowed_items=["seamless activewear set", "activewear top", "training tee",
                       "oversized graphic tee", "biker shorts", "joggers", "zip jacket",
                       "white chunky running shoes", "high white socks", "cap"],
        color_palette=["sage green", "baby blue", "classic black", "warm beige", "soft white"],
        forbidden_items=["sports bra", "bra", "tight", "midriff", "cleavage",
                         "form-fitting", "sheer", "see-through"],
    ),
    mannerisms=Mannerisms(
        signature_gestures=["adjusts ponytail or clips hair right before speaking",
                            "takes a sip from a massive pastel Stanley cup",
                            "casually wipes a little sweat from her forehead",
                            "holds the camera selfie-style in one hand while walking"],
        micro_expressions=["genuine half-smile", "raised brow on emphasis", "quick eye contact "
                           "with lens then away"],
        energy="hype girl / tough-love fitness bestie, high but grounded",
        movement_style="natural athletic movement, slight imperfection, never robotic",
    ),
    persona=PersonaVoice(
        traits=["encouraging", "tough-love but warm", "down-to-earth", "no-BS"],
        speaking_tone="conversational, like talking to a friend mid-workout",
        vocabulary="casual, energetic, light fitness slang, no corporate jargon",
        audience="women 20-35 into fitness, wellness and athleisure",
    ),
    brand=None,  # bind per campaign via SIENNA.with_brand(...)
    seed=427819,
    prohibited_terms=["squat", "squats", "squat-proof", "sheer", "see-through", "opaque",
                      "opacity", "show-through", "transparency", "sports bra", "bra", "tight",
                      "midriff", "cleavage", "form-fitting", "chest up", "chest"],
    anchor_image_uri="app/persona_vault/sienna_fitness_01/anchor_front.png",
    # CRITICAL persona rule: prefer voiceover B-roll over direct-to-camera lip-sync.
    prefers_voiceover=True,
    catchphrases=["Alright team,", "Quick reality check:", "Let's get after it today,"],
    settings=["brightly lit modern gym with mirrors and free weights",
              "sunny outdoor running track or beach promenade",
              "minimalist aesthetic apartment living room with a yoga mat"],
)


# Example brand binding (used by mock/intake when no brand supplied).
DEFAULT_BRAND = BrandGuidelines(
    brand_name="Arrowow",
    product="performance activewear",
    values=["authentic performance", "everyday confidence", "movement without limits"],
    tone_do=["real and relatable", "high energy", "show the product in action"],
    tone_dont=["overproduced", "objectifying", "fake or salesy"],
)
