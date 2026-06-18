"""
Arrowow Studio — Media Tools (deterministic FunctionTools)
==========================================================

Wrap the existing providers in app/providers/live_providers.py (reused, not rewritten).
Each is a deterministic stage — never an LLM agent. Generation prompts are assembled
from the character bible + realism profile (prompts.build_beat_generation_prompt), and
every call is cost-recorded via CostLedger with the real/mock flag set by mode.

  • DRY_RUN / LLM_ONLY → mock URIs, cost recorded as $0 (live=False).
  • LIVE_MEDIA        → real Veo / Imagen / Cloud TTS, cost recorded at PriceBook rates.

Seed policy (system design §2): A-roll beats (hook/intro/cta) use profile.seed (+jitter
from the refiner); B-roll beats (action/proof) use seed=None.
"""
from __future__ import annotations

import os
import uuid

from ..core import InvocationContext
from .. import schemas, prompts
from ..profiles.registry import resolve_profile
from ..profiles.realism import UGC_REALISM
from ..state.cost_ledger import CostLedger

VEO_MODEL = "veo-3.1-generate-001"
IMAGE_MODEL = "gemini-3.1-flash-image"
BEAT_SECONDS = 8


def _profile(state: dict):
    return resolve_profile(state.get("character", {}).get("character_id", "sienna_fitness_01"))


def _session_dir(ctx: InvocationContext) -> str:
    sid = ctx.state.get("metadata", {}).get("session_id", "unknown")
    path = os.path.join("output", sid)
    os.makedirs(path, exist_ok=True)
    return path


def _is_live(ctx: InvocationContext) -> bool:
    return ctx.mode == "LIVE_MEDIA"


# ---------------------------------------------------------------------------
# Reference frame (Imagen)
# ---------------------------------------------------------------------------
def generate_reference_frame(ctx: InvocationContext) -> dict:
    profile = _profile(ctx.state)
    prompt = ctx.state.get("beat_prompts", {}).get("reference_frame_prompt") \
        or profile.casting_block()
    prompt = prompts.apply_filter_bypass(prompt)

    if _is_live(ctx):
        from app.providers.live_providers import ImagenProvider
        result = ImagenProvider().generate_image(prompt, reference_image=None,
                                                  output_dir=_session_dir(ctx))
        CostLedger(ctx.state).record_image(IMAGE_MODEL, live=True)
    else:
        result = {"uri": os.path.join(_session_dir(ctx),
                                      f"mock_frame_{uuid.uuid4().hex[:6]}.png"), "status": "mock"}
        CostLedger(ctx.state).record_image(IMAGE_MODEL, live=False)

    ctx.state["reference_frame"] = result
    ctx.log(f"    [tool:generate_reference_frame] -> {result['uri']} ({result['status']})")
    return result


# ---------------------------------------------------------------------------
# Beat render (Veo 3.1)
# ---------------------------------------------------------------------------
def make_render_beat_stage(beat_id: str):
    def _render(ctx: InvocationContext) -> dict:
        profile = _profile(ctx.state)
        beats = ctx.state.get("beat_prompts", {}).get("beats", [])
        beat = next((b for b in beats if b.get("beat_id") == beat_id), None)
        if not beat:
            res = {"uri": "missing.mp4", "status": "skipped", "beat_id": beat_id}
            ctx.state.setdefault("beats", {})[beat_id] = res
            return res

        seed = (profile.seed + beat.get("_seed_jitter", 0)) if beat.get("seed_locked") else None
        # One-Anchor Rule: the single canonical anchor reinforces identity (Veo ASSET
        # reference). No chaining — we never feed a generated frame back as the anchor.
        # ARROWOW_NO_ANCHOR lets us A/B the anchor's effect on RAI / consistency.
        anchor = None if os.environ.get("ARROWOW_NO_ANCHOR") else profile.resolve_anchor()
        use_anchor = anchor is not None
        final_prompt = prompts.build_beat_generation_prompt(
            beat, profile, UGC_REALISM, use_anchor=use_anchor)

        if _is_live(ctx):
            from app.providers.live_providers import VeoVideoProvider
            r = VeoVideoProvider().generate_video(prompt=final_prompt, reference_image=anchor,
                                                  output_dir=_session_dir(ctx), seed=seed)
            result = {"uri": r.get("uri", "error.mp4"), "status": r.get("status", "failed"),
                      "beat_id": beat_id}
            # Charge ONLY for successful renders — RAI-blocked/failed videos are not billed.
            if result["status"] == "success":
                CostLedger(ctx.state).record_video(VEO_MODEL, BEAT_SECONDS, live=True)
        else:
            result = {"uri": os.path.join(_session_dir(ctx),
                                          f"mock_{beat_id}_{uuid.uuid4().hex[:6]}.mp4"),
                      "status": "mock", "beat_id": beat_id}
            CostLedger(ctx.state).record_video(VEO_MODEL, BEAT_SECONDS, live=False)

        ctx.state.setdefault("beats", {})[beat_id] = result
        ctx.log(f"    [tool:render_beat:{beat_id}] seed={seed} sync={beat.get('sync_mode')} "
                f"-> {result['uri']} ({result['status']})")
        return result

    return _render


# ---------------------------------------------------------------------------
# Voiceover (Cloud TTS) — for B-roll beats
# ---------------------------------------------------------------------------
def synthesize_voiceover(ctx: InvocationContext) -> dict:
    profile = _profile(ctx.state)
    beats = ctx.state.get("beat_prompts", {}).get("beats", [])
    vo_text = " ".join(b.get("dialogue_or_vo", "") for b in beats
                       if b.get("sync_mode") == schemas.SYNC_VOICEOVER)
    voice_id = profile.voice.tts_voice_id

    if _is_live(ctx) and vo_text:
        from app.providers.live_providers import GoogleTTSProvider
        result = GoogleTTSProvider().generate_audio(vo_text, voice_id=voice_id,
                                                    output_dir=_session_dir(ctx))
        CostLedger(ctx.state).record_tts(len(vo_text), live=True)
    else:
        result = {"uri": os.path.join(_session_dir(ctx),
                                      f"mock_vo_{uuid.uuid4().hex[:6]}.mp3"), "status": "mock"}
        CostLedger(ctx.state).record_tts(len(vo_text), live=False)

    ctx.state["voiceover"] = result
    ctx.log(f"    [tool:synthesize_voiceover] {len(vo_text)} chars (voice {voice_id}) "
            f"-> {result['uri']} ({result['status']})")
    return result
