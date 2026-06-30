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
from ..profiles import brands
from ..profiles.realism import UGC_REALISM
from ..state.cost_ledger import CostLedger

VEO_MODEL = "veo-3.1-generate-001"
IMAGE_MODEL = "gemini-3.1-flash-image"
BEAT_SECONDS = 8


def _profile(state: dict):
    cid = state.get("character", {}).get("character_id", "sienna_fitness_01")
    brand_id = state.get("brief", {}).get("brand_id")
    brand = brands.get_brand(brand_id) if brand_id else None
    return resolve_profile(cid, brand=brand)


def _aspect_ratio(state: dict) -> str:
    """The output aspect ratio selected in the UI (Veo-native: 16:9 or 9:16)."""
    ar = state.get("brief", {}).get("aspect_ratio", "16:9")
    return ar if ar in ("16:9", "9:16") else "16:9"


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
    beats = ctx.state.get("beat_prompts", {}).get("beats", [])
    
    # HITL: if a reviewer rejected the previous anchor frame, fold their notes into the prompt.
    fb = (ctx.state.get("hitl_feedback") or {}).get("reference_frame")
    feedback_str = f" Reviewer adjustments: {fb}." if fb else ""

    base_prompt = profile.casting_block() + " "
    
    frames_to_gen = []
    # Map from (beat_id, "start"|"end") to index in frames_to_gen
    frame_mapping = {}
    
    if beats:
        for i, b in enumerate(beats):
            bid = b.get("beat_id")
            start_p = b.get("start_frame_prompt", "").strip()
            end_p = b.get("end_frame_prompt", "").strip()
            
            # Start frame mapping
            shared = False
            if i > 0:
                prev_b = beats[i-1]
                prev_end_p = prev_b.get("end_frame_prompt", "").strip()
                if start_p == prev_end_p and start_p != "":
                    # Share the previous end frame
                    prev_idx = frame_mapping[(prev_b.get("beat_id"), "end")]
                    frame_mapping[(bid, "start")] = prev_idx
                    shared = True
                    
            if not shared:
                idx = len(frames_to_gen)
                frames_to_gen.append(base_prompt + start_p)
                frame_mapping[(bid, "start")] = idx
                
            # End frame mapping
            idx = len(frames_to_gen)
            frames_to_gen.append(base_prompt + end_p)
            frame_mapping[(bid, "end")] = idx
    else:
        # Fallback if no beats planned
        frames_to_gen.append(base_prompt + (ctx.state.get("beat_prompts", {}).get("reference_frame_prompt") or ""))
        frame_mapping[("unknown", "start")] = 0
        frame_mapping[("unknown", "end")] = 0

    prompts_list = [prompts.apply_filter_bypass(p + feedback_str) for p in frames_to_gen]

    results = []
    canonical_anchor = profile.resolve_anchor() if not os.environ.get("ARROWOW_NO_ANCHOR") else None

    if _is_live(ctx):
        from app.providers.live_providers import ImagenProvider
        provider = ImagenProvider()
        for i, p in enumerate(prompts_list):
            # Always refer directly to the canonical locked anchor image to prevent cumulative multi-step identity drift
            res = provider.generate_image(p, reference_image=canonical_anchor, output_dir=_session_dir(ctx))
            results.append(res)
            CostLedger(ctx.state).record_image(IMAGE_MODEL, live=True)
    else:
        for i, p in enumerate(prompts_list):
            res = {"uri": os.path.join(_session_dir(ctx),
                                       f"mock_frame_{i}_{uuid.uuid4().hex[:6]}.png"), "status": "mock"}
            results.append(res)
            CostLedger(ctx.state).record_image(IMAGE_MODEL, live=False)

    ctx.state["reference_frames"] = results
    ctx.log(f"    [tool:generate_reference_frame] generated {len(results)} keyframes (from {len(prompts_list)} unique prompts).")
    
    # Store keyframe URIs directly inside beats for easy retrieval
    if beats:
        for b in beats:
            bid = b.get("beat_id")
            start_idx = frame_mapping.get((bid, "start"), 0)
            end_idx = frame_mapping.get((bid, "end"), 0)
            b["_start_frame_uri"] = results[start_idx]["uri"] if start_idx < len(results) else None
            b["_end_frame_uri"] = results[end_idx]["uri"] if end_idx < len(results) else None
            
    result = {"uri": results[0]["uri"] if results else "error.png", "status": "success", "all_uris": [r["uri"] for r in results]}
    ctx.state["reference_frame"] = result
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
        
        base_anchor = profile.resolve_anchor() if not os.environ.get("ARROWOW_NO_ANCHOR") else None
        
        # Retrieve the keyframe URIs stored directly in the beat dictionary
        start_frame = beat.get("_start_frame_uri") or base_anchor
        end_frame = beat.get("_end_frame_uri")

        # If the start and end frame prompts are different (e.g., wardrobe/setting transition),
        # disable last-frame conditioning to prevent Veo from trying to morph outfits/locations,
        # which causes visual glitches and triggers person safety filters.
        start_p = beat.get("start_frame_prompt", "").strip()
        end_p = beat.get("end_frame_prompt", "").strip()
        if start_p != end_p:
            end_frame = None

        # Always use the start frame as the anchor for image-to-video generation
        # to ensure visual continuity and prevent Veo interpolation code error (requires both start and end if end is set).
        anchor = start_frame
        use_anchor = anchor is not None
        product_design = ctx.state.get("strategy", {}).get("product_design", "")
        final_prompt = prompts.build_beat_generation_prompt(
            beat, profile, UGC_REALISM, use_anchor=use_anchor, product_design=product_design)

        if _is_live(ctx):
            from app.providers.live_providers import VeoVideoProvider
            # generate_audio=True: keep Veo's ambient bed (footsteps, room tone) for realism. The
            # scripted TTS voiceover is muxed in post as the PRIMARY audio with the ambient ducked
            # under it. Because the talent is never posed "talking to camera" (voiceover action
            # shots, mouth closed), Veo produces ambient rather than clashing speech.
            r = VeoVideoProvider().generate_video(prompt=final_prompt, reference_image=anchor,
                                                  last_frame=end_frame,
                                                  output_dir=_session_dir(ctx), seed=seed,
                                                  generate_audio=True,
                                                  aspect_ratio=_aspect_ratio(ctx.state))
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

import urllib.request

def download_soundtrack(ctx: InvocationContext) -> dict:
    soundtrack_id = ctx.state.get("strategy", {}).get("soundtrack", "fast_electronic")
    SOUNDTRACK_URLS = {
        "fast_electronic": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "hip_hop": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "serene_instrumental": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"
    }
    url = SOUNDTRACK_URLS.get(soundtrack_id, SOUNDTRACK_URLS["fast_electronic"])
    
    target_dir = os.path.join(os.getcwd(), "app", "resources", "soundtracks")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, f"{soundtrack_id}.mp3")
    
    if not os.path.exists(target_path):
        try:
            print(f"Downloading soundtrack {soundtrack_id}...")
            urllib.request.urlretrieve(url, target_path)
        except Exception as e:
            print(f"Failed to download soundtrack: {e}")
            return {"uri": "error.mp3", "status": "failed"}
            
    ctx.state["soundtrack_file"] = {"uri": target_path, "status": "success"}
    ctx.log(f"    [tool:download_soundtrack] -> {target_path}")
    return {"uri": target_path, "status": "success"}

