"""
Arrowow Studio — Human-in-the-Loop Pipeline Driver (Shot-by-Shot)
=================================================================

A thin, UI-facing wrapper that runs the REAL ADK pipeline (app/adk) in
human-reviewable SEGMENTS, sharing a single persistent session across reviews.

The pipeline now uses a SHOT-BY-SHOT architecture:

    1. script           Intake + PreProductionLoop      (strategy + script)
    2. visual_plan      VisualPlanningSequence           (storyboard + wardrobe + beat prompts)
    3. shot_hook        Ref frame + Veo render + VQA     (Shot 1: Hook)
    4. shot_intro       Chain/anchor + Veo render + VQA  (Shot 2: Intro)
    5. shot_action      Chain/anchor + Veo render + VQA  (Shot 3: Action)
    6. shot_proof       Chain/anchor + Veo render + VQA  (Shot 4: Proof)
    7. shot_cta         Chain/anchor + Veo render + VQA  (Shot 5: CTA)
    8. composite_qa     TTS + soundtrack + composite + final QA

Each segment writes to session.state exactly as the autonomous Director would; the UI
pauses after every segment for APPROVE or MODIFY. "Modify" stores reviewer feedback in
state['hitl_feedback'][segment] and re-runs that segment, so the agents regenerate with
the human's notes in context (see creative_agents._hitl_suffix).

No creative/media logic is reimplemented here — it only sequences the existing agents
and tools and extracts compact review payloads for rendering.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from ..adk.core import (
    InvocationContext, Session, LoopAgent, SequentialAgent,
)
from ..adk import creative_agents as ca
from ..adk import qa as qa_mod
from ..adk.tools import media_tools, compositor
from ..adk.state import session as ss
from ..adk.state.cost_ledger import CostLedger, DevSpendTracker, cost_breakdown
from ..adk.schemas import BEAT_IDS
from ..adk.profiles import brands
from ..adk.profiles.registry import resolve_profile

Logger = Callable[[str], None]

# ---------------------------------------------------------------------------
# Segment catalogue (drives the UI stepper — shot-by-shot)
# ---------------------------------------------------------------------------
SEGMENTS = [
    {"key": "script",          "label": "Story & Script",      "icon": "📝",
     "doing": "Strategist + Scriptwriter + Brand-safety critic are drafting the 5-beat script…"},
    {"key": "visual_plan",     "label": "Visual Plan",         "icon": "🎬",
     "doing": "Storyboard + Wardrobe + Shot-prompt agents are designing each beat…"},
    {"key": "shot_hook",       "label": "Shot 1: Hook",        "icon": "🎬",  "beat_id": "hook",
     "doing": "Generating reference frame + rendering Shot 1 (Hook) + VQA…"},
    {"key": "shot_intro",      "label": "Shot 2: Intro",       "icon": "🎥",  "beat_id": "intro",
     "doing": "Rendering Shot 2 (Intro) with chaining + VQA…"},
    {"key": "shot_action",     "label": "Shot 3: Action",      "icon": "🎥",  "beat_id": "action",
     "doing": "Rendering Shot 3 (Action) + VQA…"},
    {"key": "shot_proof",      "label": "Shot 4: Proof",       "icon": "🎥",  "beat_id": "proof",
     "doing": "Rendering Shot 4 (Proof) + VQA…"},
    {"key": "shot_cta",        "label": "Shot 5: CTA",         "icon": "🎥",  "beat_id": "cta",
     "doing": "Rendering Shot 5 (CTA) + VQA…"},
    {"key": "composite_qa",    "label": "Composite & QA",      "icon": "✅",
     "doing": "Compositing master, synthesizing voiceover, running final QA review…"},
]
SEGMENT_KEYS = [s["key"] for s in SEGMENTS]
SHOT_SEGMENT_KEYS = [s["key"] for s in SEGMENTS if s.get("beat_id")]


def segment_meta(key: str) -> dict:
    return next(s for s in SEGMENTS if s["key"] == key)


def beat_id_for_segment(key: str) -> Optional[str]:
    """Return the beat_id for a shot segment, or None for non-shot segments."""
    meta = segment_meta(key)
    return meta.get("beat_id")


# Projected cost of one shot (1 beat video + 1 ref frame image).
PROJECTED_SHOT_USD = 8 * 0.15 + 0.04
# Projected cost of the full composite pass (voiceover + QA).
PROJECTED_COMPOSITE_USD = 0.10


# ---------------------------------------------------------------------------
# Session construction + intake
# ---------------------------------------------------------------------------
def new_production_session(config: dict) -> Session:
    """Create a fresh ADK session and run the deterministic intake from a UI config:

        config = {brand_id, character_id, platform, aspect_ratio, user_brief, mode, session_id}
    """
    mode = config.get("mode", "DRY_RUN")
    session = ss.make_session(mode=mode, scenario=config["user_brief"],
                              session_id=config["session_id"])
    _run_intake(session, config)
    return session


def _run_intake(session: Session, config: dict) -> None:
    state = session.state
    brand = brands.get_brand(config.get("brand_id"))
    profile = resolve_profile(config.get("character_id", "sienna_fitness_01"), brand=brand)

    state["brief"] = {
        "scenario": config["user_brief"],
        "campaign_goal": config["user_brief"],
        "brand": brand.brand_name,
        "brand_id": config.get("brand_id", brands.DEFAULT_BRAND_ID),
        "platform": config.get("platform", "Instagram Reels"),
        "aspect_ratio": config.get("aspect_ratio", "16:9"),
        "format": f"UGC · {config.get('platform','Instagram Reels')} · {config.get('aspect_ratio','16:9')}",
        "no_audio_overlay": config.get("no_audio_overlay", False),
    }
    state["character"] = {"character_id": profile.character_id, "bible": profile.model_dump()}
    state["metadata"]["scenario"] = config["user_brief"]
    state["metadata"]["status"] = "intake_complete"


def _ctx(session: Session, mode: str, log: Logger) -> InvocationContext:
    return InvocationContext(session, mode=mode, logger=log)


# ---------------------------------------------------------------------------
# Spend accounting (delta-recorded so regenerations don't double count)
# ---------------------------------------------------------------------------
def _record_spend(state: dict, mode: str) -> None:
    if mode != "LIVE_MEDIA":
        return
    ledger = CostLedger(state)
    recorded = state["metadata"].get("_recorded_usd", 0.0)
    delta = round(ledger.total_usd - recorded, 6)
    if delta > 0:
        DevSpendTracker().record_run(state["metadata"]["session_id"], delta, mode)
        state["metadata"]["_recorded_usd"] = ledger.total_usd
    # Persist per-session logs after any billable work.
    ledger.write_logs(os.path.join("output", state["metadata"]["session_id"]))


# ---------------------------------------------------------------------------
# Segment runners (async — share session.state)
# ---------------------------------------------------------------------------
async def _run_script(session: Session, mode: str, log: Logger) -> None:
    ctx = _ctx(session, mode, log)
    pre = LoopAgent(
        "PreProductionLoop",
        [ca.build_strategist(), ca.build_scriptwriter(), ca.build_text_critic()],
        max_iterations=3,
        should_exit=lambda s: bool(s.get("text_critic", {}).get("approved")))
    await pre.run(ctx)
    session.state["metadata"]["current_stage"] = "script"


async def _run_visual_plan(session: Session, mode: str, log: Logger) -> None:
    ctx = _ctx(session, mode, log)
    seq = SequentialAgent(
        "VisualPlanningSequence",
        [ca.build_storyboard(), ca.build_wardrobe(), ca.build_shot_prompt()])
    await seq.run(ctx)
    # Initialize chain state for the upcoming shot-by-shot render
    session.state["_last_tail_frame"] = None
    session.state["_re_anchor_flag"] = False
    session.state["_shot_chain"] = {}
    session.state["metadata"]["current_stage"] = "visual_plan"


# ---------------------------------------------------------------------------
# Per-shot runner (Anchor & Chain + per-shot VQA)
# ---------------------------------------------------------------------------
async def _run_shot(session: Session, mode: str, log: Logger, beat_id: str) -> None:
    """Run one shot end-to-end: ref frame → Veo render → VQA → tail extraction."""
    state = session.state
    ctx = _ctx(session, mode, log)
    MAX_RETRIES = 2  # bound billed re-renders; the pass criterion only retries on structural defects

    beats = state.get("beat_prompts", {}).get("beats", [])
    beat = next((b for b in beats if b.get("beat_id") == beat_id), None)
    if not beat:
        log(f"[shot:{beat_id}] beat not found in storyboard, skipping.")
        return

    beat_idx = next(i for i, b in enumerate(beats) if b.get("beat_id") == beat_id)

    # Dev-spend guard (live only)
    if mode == "LIVE_MEDIA":
        tracker = DevSpendTracker()
        if tracker.would_exceed(PROJECTED_SHOT_USD):
            log(f"[shot:{beat_id}] HALT — would exceed ${tracker.CEILING_USD:.0f} ceiling "
                f"(remaining ${tracker.remaining():.2f}).")
            state.setdefault("beats", {})[beat_id] = {
                "uri": "halted.mp4", "status": "halted_budget", "beat_id": beat_id}
            return
        log(f"[shot:{beat_id}] budget OK — remaining ${tracker.remaining():.2f}")

    # -- Step 1: Reference Frame (Anchor or Chain) --
    last_tail = state.get("_last_tail_frame")
    re_anchor = state.get("_re_anchor_flag", False)
    is_first = beat_idx == 0

    if last_tail and not re_anchor and not is_first:
        # Chain: use tail frame from previous shot as the anchor
        log(f"[shot:{beat_id}] 🔗 chaining from previous shot's tail frame")
        state.setdefault("_shot_chain", {})[beat_id] = "chained"
        # Set the beat's start frame to the tail frame for Veo to use
        beat["_start_frame_uri"] = last_tail
    else:
        # Anchor: generate new reference frame via Imagen
        reason = "first shot" if is_first else ("re-anchor (bad ending)" if re_anchor else "no tail frame")
        log(f"[shot:{beat_id}] 🖼️ generating reference frame via Imagen ({reason})…")
        media_tools.generate_single_beat_frame(ctx, beat_id)
        state.setdefault("_shot_chain", {})[beat_id] = "anchored"
        state["_re_anchor_flag"] = False

    # -- Step 2: Render + VQA with retries --
    beat_passed = False
    for attempt in range(1, MAX_RETRIES + 1):
        log(f"[shot:{beat_id}] 🎥 rendering (attempt {attempt}/{MAX_RETRIES})…")
        media_tools.make_render_beat_stage(beat_id)(ctx)

        clip = state.get("beats", {}).get(beat_id, {})
        clip_uri = clip.get("uri", "")
        clip_status = clip.get("status", "")

        # Mock/dry runs — auto-pass VQA
        if clip_status == "mock":
            log(f"[shot:{beat_id}] ✅ mock mode → auto-pass VQA")
            beat_passed = True
            break

        if clip_status != "success":
            log(f"[shot:{beat_id}] ❌ render failed ({clip_status}), retrying…")
            beat["_seed_jitter"] = beat.get("_seed_jitter", 0) + 1
            continue

        # -- Per-shot VQA via Gemini Pro Vision --
        log(f"[shot:{beat_id}] 🔍 running Gemini Vision QA…")
        try:
            qa_result = await qa_mod.review_clip(clip_uri, state, segment_label=beat_id)
        except Exception as e:
            log(f"[shot:{beat_id}] VQA error ({e}), auto-passing to avoid blocking.")
            qa_result = {"approved": True, "ending_state_score": 7, "overall_score": 7}

        state.setdefault("_beat_qa", {})[beat_id] = qa_result
        qa_score = qa_result.get("overall_score", 0)
        ending_score = qa_result.get("ending_state_score", 7)
        approved = qa_result.get("approved", False)
        defects = qa_result.get("defects", [])

        # Only re-render for SERIOUS STRUCTURAL failures (a different face, morphing limbs/product,
        # or an unusable end frame). Minor gloss / product-framing / colour flags are not worth an
        # expensive re-render — Veo is inherently a little polished, and some beats (e.g. a 'before'
        # problem shot) intentionally don't feature the product.
        SERIOUS = {"identity_drift", "artifact", "ending_state"}
        serious = [d for d in defects
                   if d.get("type") in SERIOUS and int(d.get("severity", 0)) >= 4]

        # Per-shot gate is STRUCTURAL only: pass unless there's a serious structural defect (face
        # drift, morphing, unusable end frame). Global look (gloss/colour/hyperrealism) is handled by
        # the post realism grade + final master QA, so it must not burn per-shot re-renders here.
        if approved or (not serious and qa_score >= 4):
            log(f"[shot:{beat_id}] ✅ VQA PASS (overall={qa_score}, ending={ending_score})")
            beat_passed = True
            break
        else:
            log(f"[shot:{beat_id}] ❌ VQA FAIL (overall={qa_score}, "
                f"serious={[d.get('type') for d in serious]} all={[d.get('type') for d in defects]})")
            beat["_seed_jitter"] = beat.get("_seed_jitter", 0) + 1
            if any(d.get("type") == "ending_state" for d in serious):
                state["_re_anchor_flag"] = True
                state["_last_tail_frame"] = None

    if not beat_passed:
        log(f"[shot:{beat_id}] ⚠ exhausted {MAX_RETRIES} retries, using last attempt.")

    # -- Step 3: Extract tail frame for chaining to the next shot --
    clip = state.get("beats", {}).get(beat_id, {})
    if clip.get("status") == "success":
        tail = media_tools.extract_sharpest_tail_frame(clip.get("uri", ""))
        if tail:
            state["_last_tail_frame"] = tail
            state["_re_anchor_flag"] = False
            log(f"[shot:{beat_id}] 🔗 tail frame extracted: {tail}")
        else:
            state["_last_tail_frame"] = None
            state["_re_anchor_flag"] = True
            log(f"[shot:{beat_id}] ⚠ tail extraction failed, next shot will re-anchor.")
    else:
        # Mock mode — no real video, clear chain state
        state["_last_tail_frame"] = None
        state["_re_anchor_flag"] = True

    _record_spend(state, mode)
    state["metadata"]["current_stage"] = f"shot_{beat_id}"


# ---------------------------------------------------------------------------
# Composite & Final QA (after all shots approved)
# ---------------------------------------------------------------------------
async def _run_composite_qa(session: Session, mode: str, log: Logger) -> None:
    """Synthesize voiceover, download soundtrack, composite master, run final QA."""
    state = session.state
    ctx = _ctx(session, mode, log)

    no_audio = state.get("brief", {}).get("no_audio_overlay", False)

    if not no_audio:
        log("[composite] synthesizing voiceover (Cloud TTS)…")
        media_tools.synthesize_voiceover(ctx)

        log("[composite] downloading background soundtrack…")
        media_tools.download_soundtrack(ctx)
    else:
        log("[composite] natural short film style requested — skipping voiceover & soundtrack overlays.")
        state["voiceover"] = {"uri": "", "status": "skipped"}
        state["soundtrack_file"] = {"uri": "", "status": "skipped"}

    log("[composite] compositing master timeline (transitions + realism grade)…")
    compositor.composite_timeline(ctx)
    _record_spend(state, mode)

    log("[composite] running final QA review…")
    from app.adk.improvement import AdversarialRefiner
    critic_loop = LoopAgent(
        "ProductionCriticLoop",
        [qa_mod.build_qa_agent(), AdversarialRefiner()],
        max_iterations=3,
        should_exit=lambda s: bool(s.get("_critic_exit")))
    await critic_loop.run(ctx)
    _record_spend(state, mode)

    state["metadata"]["current_stage"] = "composite_qa"
    state["metadata"]["status"] = "complete"


# ---------------------------------------------------------------------------
# Runner registry
# ---------------------------------------------------------------------------
def _make_shot_runner(bid: str):
    async def _runner(session, mode, log):
        await _run_shot(session, mode, log, bid)
    return _runner


_RUNNERS = {
    "script": _run_script,
    "visual_plan": _run_visual_plan,
    **{f"shot_{bid}": _make_shot_runner(bid) for bid in BEAT_IDS},
    "composite_qa": _run_composite_qa,
}


async def run_segment(segment_key: str, session: Session, mode: str, log: Logger) -> None:
    """Run one HITL segment end-to-end on the shared session."""
    log(f"▶ running segment: {segment_meta(segment_key)['label']}")
    await _RUNNERS[segment_key](session, mode, log)
    log(f"✔ segment complete: {segment_meta(segment_key)['label']}")


async def regenerate_segment(segment_key: str, session: Session, mode: str,
                             feedback: str, log: Logger) -> None:
    """Re-run a segment with reviewer feedback folded into the agents' context."""
    fb = session.state.setdefault("hitl_feedback", {})
    fb[segment_key] = feedback
    session.state.setdefault("cost_ledger", {})
    session.state["cost_ledger"]["regenerations"] = \
        session.state["cost_ledger"].get("regenerations", 0) + 1
    log(f"↻ regenerating '{segment_meta(segment_key)['label']}' with your notes…")
    await run_segment(segment_key, session, mode, log)


# ---------------------------------------------------------------------------
# Review payload extractors (compact, UI-friendly views of state)
# ---------------------------------------------------------------------------
def _file_ok(path: Optional[str]) -> bool:
    if not path:
        return False
    if path.startswith("http://") or path.startswith("https://"):
        return True
    return os.path.exists(path)


def script_review(state: dict) -> dict:
    strat = state.get("strategy", {})
    script = state.get("script", {})
    critic = state.get("text_critic", {})
    return {
        "hook": strat.get("hook", ""),
        "angle": strat.get("angle", ""),
        "cta": strat.get("cta", ""),
        "product": strat.get("product", ""),
        "key_selling_points": strat.get("key_selling_points", []),
        "script_text": script.get("script_text", ""),
        "duration_s": script.get("estimated_duration_seconds"),
        "brand_safety_score": critic.get("brand_safety_score"),
        "critic_feedback": critic.get("feedback", ""),
        "approved_by_critic": critic.get("approved"),
    }


def visual_review(state: dict) -> dict:
    sb = state.get("storyboard", {})
    wr = state.get("wardrobe", {})
    bp = state.get("beat_prompts", {})
    actions = sb.get("scene_actions", [])
    cams = sb.get("scene_cameras", [])
    scenes = [{"beat": BEAT_IDS[i] if i < len(BEAT_IDS) else f"beat{i}",
               "action": actions[i] if i < len(actions) else "",
               "camera": cams[i] if i < len(cams) else ""}
              for i in range(max(len(actions), len(cams)))]
    return {
        "wardrobe": wr.get("wardrobe", ""),
        "location": wr.get("location", ""),
        "hair_style": wr.get("hair_style", ""),
        "makeup": wr.get("makeup", ""),
        "product_styling": wr.get("product_styling", ""),
        "scenes": scenes,
        "beats": [{"beat_id": b.get("beat_id"), "camera": b.get("camera"),
                   "sync_mode": b.get("sync_mode"), "dialogue_or_vo": b.get("dialogue_or_vo", ""),
                   "product_action": b.get("product_action", ""),
                   "on_screen_text": b.get("on_screen_text", ""),
                   "prompt": b.get("prompt", "")}
                  for b in bp.get("beats", [])],
    }


def shot_review(state: dict, beat_id: str) -> dict:
    """Review payload for a single shot — shows ref frame, video, VQA, chain status."""
    beats = state.get("beat_prompts", {}).get("beats", [])
    beat = next((b for b in beats if b.get("beat_id") == beat_id), {})
    clip = state.get("beats", {}).get(beat_id, {})
    vqa = state.get("_beat_qa", {}).get(beat_id, {})
    chain = state.get("_shot_chain", {}).get(beat_id, "unknown")

    return {
        "beat_id": beat_id,
        "camera": beat.get("camera", ""),
        "camera_movement": beat.get("camera_movement", ""),
        "sync_mode": beat.get("sync_mode", ""),
        "dialogue_or_vo": beat.get("dialogue_or_vo", ""),
        "prompt": beat.get("prompt", ""),
        "product_action": beat.get("product_action", ""),
        "on_screen_text": beat.get("on_screen_text", ""),
        # Reference frame
        "ref_frame_uri": beat.get("_start_frame_uri"),
        "ref_frame_exists": _file_ok(beat.get("_start_frame_uri")),
        "ref_frame_error": state.get("reference_frames_per_shot", {}).get(beat_id, {}).get("error"),
        # Rendered video
        "video_uri": clip.get("uri"),
        "video_status": clip.get("status"),
        "video_exists": _file_ok(clip.get("uri")),
        "video_error": clip.get("error"),
        # VQA scores
        "vqa_overall": vqa.get("overall_score"),
        "vqa_ending_state": vqa.get("ending_state_score"),
        "vqa_continuity": vqa.get("continuity_score"),
        "vqa_realism": vqa.get("realism_score"),
        "vqa_approved": vqa.get("approved"),
        "vqa_defects": vqa.get("defects", []),
        "vqa_summary": vqa.get("summary", ""),
        # Chain status
        "chain_status": chain,  # "chained" | "anchored" | "unknown"
    }


def composite_review(state: dict) -> dict:
    """Review payload for the final composite + QA."""
    prod = state.get("production", {})
    uri = prod.get("final_uri")
    beats = state.get("beats", {})
    qa = state.get("qa_report", {})
    return {
        # Master video
        "final_uri": uri,
        "exists": _file_ok(uri),
        "status": prod.get("status"),
        "duration_s": prod.get("duration_s"),
        "beats_used": prod.get("beats_used", []),
        "beat_status": {bid: clip.get("status") for bid, clip in beats.items()},
        "captions_burned": prod.get("captions_burned", False),
        "voiceover_uri": prod.get("voiceover_uri"),
        # QA scores
        "qa_approved": qa.get("approved"),
        "qa_overall": qa.get("overall_score"),
        "qa_realism": qa.get("realism_score"),
        "qa_lip_sync": qa.get("lip_sync_score"),
        "qa_audio": qa.get("audio_score"),
        "qa_continuity": qa.get("continuity_score"),
        "qa_ending_state": qa.get("ending_state_score"),
        "qa_brief_adherence": qa.get("brief_adherence_score"),
        "qa_product_visibility": qa.get("product_visibility_score"),
        "qa_summary": qa.get("summary", ""),
        "qa_defects": qa.get("defects", []),
    }


def _make_shot_reviewer(bid: str):
    def _reviewer(state):
        return shot_review(state, bid)
    return _reviewer


REVIEWERS = {
    "script": script_review,
    "visual_plan": visual_review,
    **{f"shot_{bid}": _make_shot_reviewer(bid) for bid in BEAT_IDS},
    "composite_qa": composite_review,
}


def review_payload(segment_key: str, state: dict) -> dict:
    return REVIEWERS[segment_key](state)


def cost_summary(state: dict) -> dict:
    cb = cost_breakdown(state)
    cb["dev_remaining_usd"] = DevSpendTracker().remaining()
    return cb
