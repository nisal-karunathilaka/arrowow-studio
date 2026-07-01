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
        "audio_score": 8, "continuity_score": 8, "ending_state_score": 8,
        "brief_adherence_score": 8,
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


def _shot_context(state: dict, beat_id: str) -> str:
    """Light, single-shot context for per-shot VQA: what THIS beat should show + the product."""
    strat = state.get("strategy", {})
    beat = next((b for b in state.get("beat_prompts", {}).get("beats", [])
                 if b.get("beat_id") == beat_id), {})
    pa = (beat.get("product_action") or "").strip()
    if pa:
        product_line = (f"Hero product (must look identical across shots): {strat.get('product', '')} — "
                        f"{strat.get('product_design', '')}\nProduct action in this shot: {pa}")
    else:
        product_line = ("This shot intentionally does NOT feature the hero product (e.g. a 'before'/"
                        "problem shot or a pure lifestyle moment). Score product_visibility=8 and do "
                        "NOT add a 'product' defect for its absence.")
    return (
        f"This shot ('{beat_id}') should show: {beat.get('prompt', '')[:240]}\n"
        f"{product_line}"
    )


def _load_clip_bytes(uri: str) -> bytes | None:
    """Return the clip's raw bytes from a local path OR an https:// GCS signed URL.

    Production returns GCS signed URLs (no local disk on Streamlit Cloud), so a naive
    os.path.exists()/open() treats every real clip as 'missing' and the QA returns all-zeros.
    """
    if not uri or uri.endswith(("error.mp4", "error.png", "missing.mp4", "halted.mp4")):
        return None
    try:
        if uri.startswith("http://") or uri.startswith("https://"):
            import urllib.request
            with urllib.request.urlopen(uri, timeout=90) as r:
                return r.read()
        if os.path.exists(uri):
            with open(uri, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"[qa] could not load clip bytes ({uri[:60]}…): {e}")
    return None


async def review_clip(uri: str, state: dict, segment_label: str = "global") -> dict:
    """Multimodal QA over a SPECIFIC clip (a single beat or the final master) with
    Gemini 3.1 Pro. Returns a QAReport dict. Used by both the orchestrator critic loop
    and the single-beat refinement loop."""
    from google.genai import types
    from . import llm_backend
    from .state.cost_ledger import CostLedger

    profile = resolve_profile(state.get("character", {}).get("character_id", "sienna_fitness_01"))
    clip_bytes = _load_clip_bytes(uri)
    if clip_bytes is None:
        return {"approved": False, "overall_score": 0, "realism_score": 0, "lip_sync_score": 0,
                "audio_score": 0, "continuity_score": 0,
                "defects": [{"type": "artifact", "segment": segment_label, "severity": 5,
                             "description": "video missing", "remedy_hint": "regenerate"}],
                "summary": "No video to review."}

    # Per-shot VQA (a single raw beat clip) uses a VISION-ONLY rubric — audio/voiceover/music and
    # whole-ad brief adherence don't exist on a raw clip and must not be graded. The MASTER review
    # uses the full rubric (audio, brief adherence, product, etc.).
    is_master = segment_label in ("master", "global")
    if is_master:
        no_audio = state.get("brief", {}).get("no_audio_overlay", False)
        system_instruction = prompts.qa_instruction(profile, no_audio_overlay=no_audio)
        user_text = f"Review this assembled UGC master.\n\n{_brief_context(state)}"
    else:
        system_instruction = prompts.shot_qa_instruction(profile)
        user_text = (f"Review ONLY this single raw shot (beat: {segment_label}).\n"
                     f"{_shot_context(state, segment_label)}\n"
                     "Remember: ignore all audio/music/voiceover; judge visuals + ending frame only.")

    client = llm_backend._get_client()
    part = types.Part.from_bytes(data=clip_bytes, mime_type="video/mp4")
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=schemas.QAReport, temperature=0.2)

    resp = await client.aio.models.generate_content(
        model=QA_MODEL, contents=[part, user_text], config=config)

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

