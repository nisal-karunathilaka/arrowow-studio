"""
Arrowow Studio — Post-Production Compositor
===========================================

Assembles the 5 beat clips into the final master and applies post-production:
  • transition plan (match-cut / whip-pan motion-mask / xfade — masked by the A/B-roll design),
  • a realism GRADE (subtle film grain + slight desaturation/contrast) that fights the
    over-clean "AI look" (anti-hyperrealism, per RealismProfile.grade),
  • audio carried from each beat's native Veo track.

  • DRY_RUN / LLM_ONLY → returns a plan + mock master URI.
  • LIVE_MEDIA        → real ffmpeg concat + grade, producing a real master mp4.
"""
from __future__ import annotations

import os
import subprocess
import uuid

from ..core import InvocationContext
from ..profiles.realism import UGC_REALISM

BEAT_ORDER = ["hook", "intro", "action", "proof", "cta"]
TRANSITIONS = {"intro": "match_cut", "action": "whip_pan", "proof": "macro_zoom", "cta": "xfade"}

# Realism grade: subtle sensor noise + slight desaturation/contrast (no HDR pop).
REALISM_VF = "noise=alls=7:allf=t,eq=saturation=0.92:contrast=0.98:brightness=-0.01"


def _ordered_clips(state: dict) -> list[dict]:
    beats = state.get("beats", {})
    return [beats[b] for b in BEAT_ORDER if beats.get(b) and beats[b].get("status") != "skipped"]


def _ffmpeg_concat_grade(clip_paths: list[str], out_path: str, filter_vf: str) -> bool:
    """Concat clips (with audio), apply professional crossfade transitions (0.5s overlap),
    and execute the realism grade. Returns success."""
    existing = [p for p in clip_paths if p and os.path.exists(p)]
    if not existing:
        return False
    cmd = ["ffmpeg", "-y"]
    for p in existing:
        cmd += ["-i", p]
    n = len(existing)

    if n == 1:
        filtergraph = f"[0:v]{filter_vf}[v];[0:a]anull[a]"
    else:
        v_parts = []
        a_parts = []
        # Construct the video crossfade chain (each clip is 8.0 seconds)
        v_parts.append("[0:v][1:v]xfade=transition=fade:duration=0.5:offset=7.5[v0]")
        for i in range(2, n):
            offset = 7.5 + (i - 1) * 7.5
            v_parts.append(f"[v{i-2}][{i}:v]xfade=transition=fade:duration=0.5:offset={offset}[v{i-1}]")
        
        # Construct the audio crossfade chain
        a_parts.append("[0:a][1:a]acrossfade=d=0.5:c1=tri:c2=tri[a0]")
        for i in range(2, n):
            a_parts.append(f"[a{i-2}][{i}:a]acrossfade=d=0.5:c1=tri:c2=tri[a{i-1}]")
        
        last_idx = n - 2
        filtergraph = (
            ";".join(v_parts) + ";" +
            ";".join(a_parts) + ";" +
            f"[v{last_idx}]{filter_vf}[v];[a{last_idx}]anull[a]"
        )

    cmd += ["-filter_complex", filtergraph, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return os.path.exists(out_path)
    except Exception as e:
        print(f"[compositor] ffmpeg failed: {e}")
        return False


def composite_timeline(ctx: InvocationContext) -> dict:
    clips = _ordered_clips(ctx.state)
    transition_plan = [{"into": b, "transition": TRANSITIONS.get(b, "cut")} for b in BEAT_ORDER]
    grade = UGC_REALISM.grade_directives()

    session_dir = os.path.join("output", ctx.state.get("metadata", {}).get("session_id", "unknown"))
    os.makedirs(session_dir, exist_ok=True)
    final_uri = os.path.join(session_dir, f"master_{uuid.uuid4().hex[:6]}.mp4")

    # Get dynamic video filter parameters from state or set defaults
    vf_params = ctx.state.setdefault("compositor_vf_params", {
        "noise": 7,
        "saturation": 0.92,
        "contrast": 0.98,
        "brightness": -0.01
    })
    noise_val = vf_params.get("noise", 7)
    sat_val = vf_params.get("saturation", 0.92)
    con_val = vf_params.get("contrast", 0.98)
    br_val = vf_params.get("brightness", -0.01)
    filter_vf = f"noise=alls={noise_val}:allf=t,eq=saturation={sat_val:.2f}:contrast={con_val:.2f}:brightness={br_val:.2f}"

    status = "mock"
    if ctx.mode == "LIVE_MEDIA":
        ok = _ffmpeg_concat_grade([c.get("uri") for c in clips], final_uri, filter_vf)
        status = "success" if ok else "failed"

    result = {
        "final_uri": final_uri if status != "failed" else None,
        "duration_s": len(clips) * 8,
        "beats_used": [c.get("beat_id") for c in clips],
        "transition_plan": transition_plan,
        "realism_grade": grade,
        "ffmpeg_filter_vf": filter_vf,
        "voiceover_uri": ctx.state.get("voiceover", {}).get("uri"),
        "status": status,
    }
    ctx.state["production"] = result
    ctx.log(f"    [tool:composite_timeline] {len(clips)} beats, grade={grade} vf={filter_vf} "
            f"-> {final_uri} ({status})")
    return result
