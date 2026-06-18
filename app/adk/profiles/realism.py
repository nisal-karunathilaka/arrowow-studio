"""
Arrowow Studio — Realism Profile (Anti-Hyperrealism)
====================================================

The single biggest "tell" of AI video is that it looks TOO perfect — glossy skin,
floaty motion, flawless lighting, cinematic gloss. Our goal is the opposite: footage
that reads as a REAL person filming themselves on a phone.

This profile injects deliberate, controlled imperfection into every generation prompt
(positive directives) and a negative block (what to avoid). It is applied on top of the
character bible — identity stays locked, but the *capture* looks authentically human.

Reference practice: UGC / handheld vlog realism, not cinema. Phone optics, natural
light, real skin, room tone, micro-shake, subtle grain.
"""
from __future__ import annotations

from typing import List

import pydantic


class RealismProfile(pydantic.BaseModel):
    name: str
    camera: List[str]      # capture device + handling
    skin: List[str]        # texture realism
    lighting: List[str]    # natural light behavior
    motion: List[str]      # natural movement / framing
    audio: List[str]       # acoustic realism
    grade: List[str]       # color/grain finishing
    avoid: List[str]       # the anti-AI negative block

    def directive_block(self) -> str:
        """Positive realism directives appended to a generation prompt."""
        return (
            "REALISM (make it look like real phone-recorded footage, not AI/cinema): "
            f"Camera — {'; '.join(self.camera)}. "
            f"Skin — {'; '.join(self.skin)}. "
            f"Lighting — {'; '.join(self.lighting)}. "
            f"Motion — {'; '.join(self.motion)}. "
            f"Audio — {'; '.join(self.audio)}."
        )

    def negative_block(self) -> str:
        """Negative directives — what must NOT appear."""
        return "AVOID (anti-AI tells): " + "; ".join(self.avoid) + "."

    def grade_directives(self) -> List[str]:
        """Post-production grade/grain steps for the compositor."""
        return self.grade


# Default UGC realism profile — the house style for authentic-looking footage.
UGC_REALISM = RealismProfile(
    name="ugc_handheld_v1",
    camera=[
        "shot on a modern smartphone front/rear camera",
        "natural handheld micro-shake, occasional tiny reframing",
        "slight rolling-shutter and brief autofocus hunt",
        "realistic phone lens (mild wide-angle, natural perspective)",
    ],
    skin=[
        "real skin with natural texture and subtle imperfections",
        "no airbrushing, no plastic or waxy skin, no beauty-filter smoothing",
    ],
    lighting=[
        "available/natural light (window, sun, gym practicals)",
        "slightly uneven exposure, natural soft shadows",
        "mixed color temperature, not studio-perfect",
        "flat desaturated color science, neutral white balance, raw phone camera colors",
    ],
    motion=[
        "natural human movement with slight imperfection",
        "occasional imperfect framing then small correction",
        "real motion blur on fast movement",
    ],
    audio=[
        "natural room tone and ambient background",
        "no studio polish, no obvious noise gate",
    ],
    grade=[
        "subtle film grain / sensor noise",
        "slightly reduced saturation and contrast (no HDR pop)",
        "very mild handheld stabilization residue",
    ],
    avoid=[
        "plastic or airbrushed skin", "over-smooth beauty-filter look",
        "uncanny-valley face", "overly perfect symmetry",
        "glossy cinematic color grade", "floaty unnatural motion",
        "studio three-point lighting", "HDR over-sharpening",
        "captions, subtitles, watermark, on-screen text",
        "saturated colors", "vibrant color grading", "cinematic teal and orange LUT",
        "studio-graded look", "high-contrast color pop",
    ],
)
