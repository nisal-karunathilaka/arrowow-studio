"""
Arrowow Studio — QA Agent (the Discriminator)
=============================================

A senior commercial-video QA reviewer implemented as a multimodal LlmAgent. It watches
the assembled master and returns a structured QAReport: per-dimension scores (overall,
realism, lip-sync, audio, continuity) plus a typed defect list with remedy hints.

It is the "discriminator" in the adversarial refinement loop (see improvement.py):
its rejection + defects drive targeted, automated regeneration of the failing beat.

  • DRY_RUN / LLM_ONLY → mock (no video to analyze).
  • LIVE_MEDIA        → Gemini 3.1 Pro multimodal over the final mp4.
"""
from __future__ import annotations

import json
import os

from .core import LlmAgent
from . import schemas, prompts
from .profiles.registry import resolve_profile

QA_MODEL = "gemini-3.1-pro-preview"   # multimodal video understanding (system design §1)


def _mock_qa(state: dict) -> dict:
    return {
        "approved": True, "overall_score": 8, "realism_score": 8, "lip_sync_score": 8,
        "audio_score": 8, "continuity_score": 8, "brief_adherence_score": 8,
        "product_visibility_score": 8, "defects": [],
        "summary": "Mock QA pass: brief realized, product featured, face/voice consistent.",
    }


def _brief_context(state: dict) -> str:
    """Compact text view of the brief + planned beats so the QA reviewer can grade brief
    adherence and product visibility against what was actually requested."""
    brief = state.get("brief", {})
    strat = state.get("strategy", {})
    beats = state.get("beat_prompts", {}).get("beats", [])
    beat_lines = "\n".join(
        f"  - {b.get('beat_id')}: {b.get('prompt','')[:160]} "
        f"| product: {b.get('product_action','')} | text: {b.get('on_screen_text','')}\n"
        f"    [Boundary Start]: {b.get('start_frame_prompt', '')}\n"
        f"    [Boundary End]: {b.get('end_frame_prompt', '')}"
        for b in beats)
    return (
        f"CAMPAIGN BRIEF: {brief.get('scenario','')}\n"
        f"HERO PRODUCT: {strat.get('product','(infer from brief)')}\n"
        f"SELLING POINTS: {strat.get('key_selling_points', [])}\n"
        f"PLANNED BEATS:\n{beat_lines}\n"
        "Grade the video against this: are these beats and this product actually realized on screen?"
    )


async def review_clip(uri: str, state: dict, segment_label: str = "global") -> dict:
    """Multimodal QA over a SPECIFIC clip (a single beat or the final master) with
    Gemini 3.1 Pro. Returns a QAReport dict. Used by both the orchestrator critic loop
    and the single-beat refinement loop."""
    from google.genai import types
    from . import llm_backend
    from .state.cost_ledger import CostLedger

    profile = resolve_profile(state.get("character", {}).get("character_id", "sienna_fitness_01"))
    if not uri or not os.path.exists(uri):
        return {"approved": False, "overall_score": 0, "realism_score": 0, "lip_sync_score": 0,
                "audio_score": 0, "continuity_score": 0,
                "defects": [{"type": "artifact", "segment": segment_label, "severity": 5,
                             "description": "video missing", "remedy_hint": "regenerate"}],
                "summary": "No video to review."}

    client = llm_backend._get_client()
    with open(uri, "rb") as f:
        part = types.Part.from_bytes(data=f.read(), mime_type="video/mp4")
    config = types.GenerateContentConfig(
        system_instruction=prompts.qa_instruction(profile),
        response_mime_type="application/json",
        response_schema=schemas.QAReport, temperature=0.2)

    resp = await client.aio.models.generate_content(
        model=QA_MODEL,
        contents=[part, f"Review this UGC clip (segment: {segment_label}).\n\n{_brief_context(state)}"],
        config=config)

    usage = getattr(resp, "usage_metadata", None)
    if usage:
        CostLedger(state).record_llm("gemini-3.1-pro",
                                     getattr(usage, "prompt_token_count", 0) or 0,
                                     getattr(usage, "candidates_token_count", 0) or 0)

    parsed = getattr(resp, "parsed", None)
    return parsed.model_dump() if parsed is not None else json.loads(resp.text)


async def _live_qa(state: dict) -> dict:
    """QA the assembled master (orchestrator critic loop)."""
    return await review_clip(state.get("production", {}).get("final_uri", ""), state, "master")


def build_qa_agent() -> LlmAgent:
    return LlmAgent("QAReviewer", schemas.QAReport, "qa_report", _mock_qa, live_fn=_live_qa)

