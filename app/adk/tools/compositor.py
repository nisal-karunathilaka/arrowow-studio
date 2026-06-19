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
import re
import subprocess
import uuid

from ..core import InvocationContext
from ..profiles.realism import UGC_REALISM

BEAT_ORDER = ["hook", "intro", "action", "proof", "cta"]
TRANSITIONS = {"intro": "match_cut", "action": "whip_pan", "proof": "macro_zoom", "cta": "xfade"}

# Each beat occupies ~7.5s of the crossfaded timeline (8s clip - 0.5s overlap).
BEAT_SPAN_S = 7.5
# macOS bold font for caption rendering (Pillow). Falls back to the default font if absent.
_CAPTION_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿️]",
    flags=re.UNICODE)

# Realism grade: subtle sensor noise + slight desaturation/contrast (no HDR pop).
REALISM_VF = "noise=alls=7:allf=t,eq=saturation=0.92:contrast=0.98:brightness=-0.01"


def _ordered_clips(state: dict) -> list[dict]:
    beats = state.get("beats", {})
    return [beats[b] for b in BEAT_ORDER if beats.get(b) and beats[b].get("status") != "skipped"]


def _clip_has_audio(path: str) -> bool:
    """Check if a clip has an audio track via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10)
        return "audio" in r.stdout
    except Exception:
        return False


def _ffmpeg_concat_grade(clip_paths: list[str], out_path: str, filter_vf: str) -> bool:
    """Concat clips, apply professional crossfade transitions (0.5s overlap), and grade.
    Handles clips that may not have an audio track (e.g., voiceover-mode Veo clips)
    by inserting a silent anullsrc for those positions."""
    existing = [p for p in clip_paths if p and os.path.exists(p)]
    if not existing:
        return False

    has_audio = [_clip_has_audio(p) for p in existing]
    any_audio = any(has_audio)

    cmd = ["ffmpeg", "-y"]
    for p in existing:
        cmd += ["-i", p]
    n = len(existing)

    if n == 1:
        if any_audio:
            filtergraph = f"[0:v]{filter_vf}[v];[0:a]anull[a]"
        else:
            filtergraph = f"[0:v]{filter_vf}[v];anullsrc=r=44100:cl=stereo[a]"
    else:
        v_parts = []
        a_parts = []

        # Build audio labels — use anullsrc for clips without an audio track.
        audio_labels = []
        null_idx = 0
        for i, has_a in enumerate(has_audio):
            if has_a:
                audio_labels.append(f"[{i}:a]")
            else:
                lbl = f"[null{null_idx}]"
                a_parts.insert(0, f"anullsrc=r=44100:cl=stereo:d=8{lbl}")
                audio_labels.append(lbl)
                null_idx += 1

        # Video crossfade chain
        v_parts.append(f"[0:v][1:v]xfade=transition=fade:duration=0.5:offset=7.5[v0]")
        for i in range(2, n):
            offset = 7.5 + (i - 1) * 7.5
            v_parts.append(f"[v{i-2}][{i}:v]xfade=transition=fade:duration=0.5:offset={offset}[v{i-1}]")

        # Audio crossfade chain using the (possibly-null) audio labels
        a_parts.append(f"{audio_labels[0]}{audio_labels[1]}acrossfade=d=0.5:c1=tri:c2=tri[a0]")
        for i in range(2, n):
            a_parts.append(f"[a{i-2}]{audio_labels[i]}acrossfade=d=0.5:c1=tri:c2=tri[a{i-1}]")

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


def _probe_dims(path: str) -> tuple[int, int]:
    """Return (width, height) of a video via ffprobe; default to 1080x1920 (9:16)."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path],
            capture_output=True, text=True, timeout=10)
        w, h = r.stdout.strip().split("x")
        return int(w), int(h)
    except Exception:
        return 1080, 1920


def _clean_caption(text: str) -> str:
    """Strip emoji (the caption font can't render colour glyphs) and tidy whitespace."""
    return " ".join(_EMOJI_RE.sub("", text or "").split()).strip()


def _make_caption_png(text: str, w: int, h: int, out_path: str) -> bool:
    """Render a full-frame transparent PNG with the caption in a dark rounded pill near the
    lower third (UGC caption style). Returns True on success."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = max(28, int(h * 0.040))
    try:
        font = ImageFont.truetype(_CAPTION_FONT, size)
    except Exception:
        font = ImageFont.load_default()

    # Wrap to ~90% width.
    words, lines, cur = text.split(), [], ""
    max_w = int(w * 0.86)
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = word
    if cur:
        lines.append(cur)

    line_h = int(size * 1.32)
    pad_x, pad_y = int(size * 0.7), int(size * 0.5)
    block_w = min(max_w + 2 * pad_x,
                  int(max((draw.textlength(l, font=font) for l in lines), default=0)) + 2 * pad_x)
    block_h = line_h * len(lines) + 2 * pad_y
    x0 = (w - block_w) // 2
    y0 = int(h * 0.78) - block_h // 2
    radius = int(size * 0.55)
    draw.rounded_rectangle([x0, y0, x0 + block_w, y0 + block_h], radius=radius,
                           fill=(0, 0, 0, 165))
    cy = y0 + pad_y
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text(((w - lw) // 2, cy), line, font=font, fill=(255, 255, 255, 240))
        cy += line_h
    img.save(out_path)
    return True


def _burn_captions(master_path: str, captions: list[tuple[str, float, float]],
                   session_dir: str, out_path: str) -> bool:
    """Overlay time-windowed caption PNGs onto the master (drawtext is unavailable in this
    ffmpeg build, so we composite Pillow-rendered PNGs with the overlay filter)."""
    w, h = _probe_dims(master_path)
    pngs = []
    for i, (text, _s, _e) in enumerate(captions):
        png = os.path.join(session_dir, f"_cap_{i}.png")
        if _make_caption_png(text, w, h, png):
            pngs.append((png, captions[i][1], captions[i][2]))
    if not pngs:
        return False

    cmd = ["ffmpeg", "-y", "-i", master_path]
    for png, _s, _e in pngs:
        cmd += ["-i", png]
    chain, prev = [], "[0:v]"
    for i, (_png, s, e) in enumerate(pngs):
        out_lbl = f"[v{i}]"
        chain.append(f"{prev}[{i+1}:v]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'{out_lbl}")
        prev = out_lbl
    filtergraph = ";".join(chain)
    cmd += ["-filter_complex", filtergraph, "-map", prev, "-map", "0:a?",
            "-c:a", "copy", "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return os.path.exists(out_path)
    except Exception as e:
        print(f"[compositor] caption burn-in failed: {e}")
        return False


def _mux_voiceover(video_path: str, vo_path: str, out_path: str) -> bool:
    """Mux the scripted TTS voiceover onto the master as the PRIMARY audio, ducking the Veo
    clip ambient under it. Without this the master plays Veo's own generated clip audio and the
    scripted voiceover is lost (a real bug found in live validation)."""
    if not (vo_path and os.path.exists(vo_path)):
        return False
    has_ambient = _clip_has_audio(video_path)
    if has_ambient:
        # VO at full level over ambient ducked to ~18%; cut to the video length.
        fc = ("[0:a]volume=0.18[amb];[1:a]volume=1.35[vo];"
              "[amb][vo]amix=inputs=2:duration=first:dropout_transition=0[a]")
        amap = "[a]"
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", vo_path,
               "-filter_complex", fc, "-map", "0:v", "-map", amap]
    else:
        # No ambient track — use the VO directly as the master audio.
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", vo_path,
               "-map", "0:v", "-map", "1:a", "-shortest"]
    cmd += ["-c:v", "copy", "-c:a", "aac", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        return os.path.exists(out_path)
    except Exception as e:
        print(f"[compositor] voiceover mux failed: {e}")
        return False


def _caption_windows(state: dict) -> list[tuple[str, float, float]]:
    """Map each rendered beat's on_screen_text to its time window in the master."""
    beats_meta = {b.get("beat_id"): b for b in state.get("beat_prompts", {}).get("beats", [])}
    used = [b for b in BEAT_ORDER
            if state.get("beats", {}).get(b)
            and state["beats"][b].get("status") != "skipped"]
    windows = []
    for idx, bid in enumerate(used):
        text = _clean_caption(beats_meta.get(bid, {}).get("on_screen_text", ""))
        if text:
            start = idx * BEAT_SPAN_S + 0.4
            end = (idx + 1) * BEAT_SPAN_S - 0.4
            windows.append((text, start, end))
    return windows


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
        # The talent speaks natively (Veo generates her voice + lip-sync), so the master is simply
        # the graded concatenation of the native clips — NO separate voiceover audio overlay and NO
        # on-screen-text/caption overlay (the character and product carry the ad).
        ok = _ffmpeg_concat_grade([c.get("uri") for c in clips], final_uri, filter_vf)
        status = "success" if ok else "failed"

    result = {
        "final_uri": final_uri if status != "failed" else None,
        "duration_s": len(clips) * 8,
        "beats_used": [c.get("beat_id") for c in clips],
        "transition_plan": transition_plan,
        "realism_grade": grade,
        "ffmpeg_filter_vf": filter_vf,
        "captions_burned": False,
        "voiceover_muxed": False,
        "status": status,
    }
    ctx.state["production"] = result
    ctx.log(f"    [tool:composite_timeline] {len(clips)} beats, grade={grade} "
            f"native-audio, no overlays -> {final_uri} ({status})")
    return result
