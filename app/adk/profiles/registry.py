"""
Arrowow Studio — Character Registry
===================================

Resolves a character id (+ optional brand) to a full CharacterProfile bible.
Single-persona for v1; the registry pattern lets us add personas without touching
the agents.
"""
from __future__ import annotations

from typing import Optional

from .character import CharacterProfile, BrandGuidelines
from .sienna import SIENNA, DEFAULT_BRAND

_REGISTRY = {SIENNA.character_id: SIENNA}


def resolve_profile(character_id: str = "sienna_fitness_01",
                    brand: Optional[BrandGuidelines] = None) -> CharacterProfile:
    profile = _REGISTRY.get(character_id, SIENNA)
    return profile.with_brand(brand or profile.brand or DEFAULT_BRAND)
