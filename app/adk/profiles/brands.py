"""
Arrowow Studio — Brand Presets
==============================

A small registry of brand profiles (BrandGuidelines) the UI can bind to a character
via CharacterProfile.with_brand(). Keeping these in the profiles package (not the UI)
means the agents can resolve the selected brand from session state without the domain
layer depending on the UI layer.

For v1 these are fitness / activewear brands, since the only character bible is Sienna
(fitness & lifestyle). Add a brand here and it appears in the UI dropdown automatically.
"""
from __future__ import annotations

from typing import Dict, List

from .character import BrandGuidelines
from .sienna import DEFAULT_BRAND

# ---------------------------------------------------------------------------
# Presets — id -> BrandGuidelines. `arrowow` is the house default.
# ---------------------------------------------------------------------------
BRAND_PRESETS: Dict[str, BrandGuidelines] = {
    "arrowow": DEFAULT_BRAND,
    "gymshark": BrandGuidelines(
        brand_name="Gymshark",
        product="performance gym & training activewear",
        values=["conditioning the physical and mental", "community", "progressive overload",
                "be a visionary"],
        tone_do=["bold and motivational", "gym-culture authentic", "show real effort and sweat",
                 "community-driven 'we' language"],
        tone_dont=["corporate or stiff", "luxury/elitist", "passive or low-energy"],
    ),
    "lululemon": BrandGuidelines(
        brand_name="lululemon",
        product="premium yoga, training & lifestyle activewear",
        values=["mindful movement", "quality and feel", "wellbeing and balance",
                "sweatlife community"],
        tone_do=["calm and premium", "wellness-forward", "emphasise fabric feel and fit",
                 "inclusive and grounded"],
        tone_dont=["hype-bro energy", "cheap or discount-driven", "aggressive sales push"],
    ),
    "nike_training": BrandGuidelines(
        brand_name="Nike Training",
        product="performance training gear and footwear",
        values=["just do it", "athlete-first", "relentless performance", "self-belief"],
        tone_do=["iconic and punchy", "empowering", "athlete mindset", "short, confident lines"],
        tone_dont=["wordy or soft", "apologetic", "generic fitness clichés"],
    ),
    "alo_yoga": BrandGuidelines(
        brand_name="Alo Yoga",
        product="studio-to-street yoga and lifestyle activewear",
        values=["mindful living", "studio aesthetic", "elevated minimalism", "presence"],
        tone_do=["serene and aspirational", "aesthetic and minimal", "mind-body language",
                 "soft confident delivery"],
        tone_dont=["loud or aggressive", "cluttered", "hard-sell"],
    ),
}

DEFAULT_BRAND_ID = "arrowow"


def list_brands() -> List[dict]:
    """UI helper: ordered list of {id, name, product} for the dropdown."""
    return [{"id": bid, "name": b.brand_name, "product": b.product}
            for bid, b in BRAND_PRESETS.items()]


def get_brand(brand_id: str | None) -> BrandGuidelines:
    """Resolve a brand id to its BrandGuidelines (falls back to the house brand)."""
    return BRAND_PRESETS.get(brand_id or DEFAULT_BRAND_ID, DEFAULT_BRAND)
