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


def _ffmpeg_concat_grade(clip_paths: list[str], out_path: str) -> bool:
    """Concat clips (with audio) and apply the realism grade. Returns success."""
    existing = [p for p in clip_paths if p and os.path.exists(p)]
    if not existing:
        return False
    cmd = ["ffmpeg", "-y"]
    for p in existing:
        cmd += ["-i", p]
    n = len(existing)
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filtergraph = (f"{streams}concat=n={n}:v=1:a=1[cv][a];"
                   f"[cv]{REALISM_VF}[v]")
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

    status = "mock"
    if ctx.mode == "LIVE_MEDIA":
        ok = _ffmpeg_concat_grade([c.get("uri") for c in clips], final_uri)
        status = "success" if ok else "failed"

    result = {
        "final_uri": final_uri if status != "failed" else None,
        "duration_s": len(clips) * 8,
        "beats_used": [c.get("beat_id") for c in clips],
        "transition_plan": transition_plan,
        "realism_grade": grade,
        "voiceover_uri": ctx.state.get("voiceover", {}).get("uri"),
        "status": status,
    }
    ctx.state["production"] = result
    ctx.log(f"    [tool:composite_timeline] {len(clips)} beats, grade={grade} "
            f"-> {final_uri} ({status})")
    return result
