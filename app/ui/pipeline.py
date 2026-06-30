"""
Arrowow Studio — Human-in-the-Loop Pipeline Driver
===================================================

A thin, UI-facing wrapper that runs the REAL ADK pipeline (app/adk) in five
human-reviewable SEGMENTS, sharing a single persistent session across reviews:

    1. script           Intake + PreProductionLoop      (strategy + script)
    2. visual_plan      VisualPlanningSequence           (storyboard + wardrobe + beat prompts)
    3. reference_frame  ReferenceFrameStage (Imagen)     (canonical anchor frame)
    4. render           budget guard + Veo x5 + TTS + compositor (the master cut)
    5. qa               QAReviewer (single vision pass)  (quality report)

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
# Segment catalogue (drives the UI stepper)
# ---------------------------------------------------------------------------
SEGMENTS = [
    {"key": "script",          "label": "Story & Script",   "icon": "📝",
     "doing": "Strategist + Scriptwriter + Brand-safety critic are drafting the 5-beat script…"},
    {"key": "visual_plan",     "label": "Visual Plan",      "icon": "🎬",
     "doing": "Storyboard + Wardrobe + Shot-prompt agents are designing each beat…"},
    {"key": "reference_frame", "label": "Reference Frame",  "icon": "🖼️",
     "doing": "Generating the canonical anchor frame (identity lock)…"},
    {"key": "render",          "label": "Render & Compose", "icon": "🎥",
     "doing": "Rendering 5 beats on Veo 3.1, synthesizing voiceover, and compositing the master…"},
    {"key": "qa",              "label": "Quality Review",   "icon": "✅",
     "doing": "Multimodal QA reviewer is grading the master cut…"},
]
SEGMENT_KEYS = [s["key"] for s in SEGMENTS]


def segment_meta(key: str) -> dict:
    return next(s for s in SEGMENTS if s["key"] == key)


# Projected cost of a full live render (5 beats x 8s x $0.15 + 1 frame).
PROJECTED_RENDER_USD = 5 * 8 * 0.15 + 0.04


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
    session.state["metadata"]["current_stage"] = "visual_plan"


async def _run_reference_frame(session: Session, mode: str, log: Logger) -> None:
    ctx = _ctx(session, mode, log)
    media_tools.generate_reference_frame(ctx)
    _record_spend(session.state, mode)
    session.state["metadata"]["current_stage"] = "reference_frame"


async def _run_render(session: Session, mode: str, log: Logger) -> None:
    state = session.state
    ctx = _ctx(session, mode, log)

    # Dev-spend guard (live only) — never breach the $100 ceiling.
    if mode == "LIVE_MEDIA":
        tracker = DevSpendTracker()
        if tracker.would_exceed(PROJECTED_RENDER_USD):
            log(f"[budget] HALT — a live render (~${PROJECTED_RENDER_USD:.2f}) would exceed the "
                f"${tracker.CEILING_USD:.0f} ceiling (remaining ${tracker.remaining():.2f}).")
            state["production"] = {"status": "halted_budget", "final_uri": None}
            return
        log(f"[budget] OK — remaining ${tracker.remaining():.2f}, this render ≈ ${PROJECTED_RENDER_USD:.2f}.")

    beats = state.get("beat_prompts", {}).get("beats", [])
    # Render each beat (sequential for clear per-beat progress).
    for b in beats:
        bid = b["beat_id"]
        log(f"[render] beat '{bid}' → Veo 3.1…")
        media_tools.make_render_beat_stage(bid)(ctx)

    log("[render] synthesizing voiceover (Cloud TTS)…")
    media_tools.synthesize_voiceover(ctx)

    log("[render] downloading background soundtrack…")
    media_tools.download_soundtrack(ctx)

    # Healing pass — retry any failed beat once with a jittered seed.
    rendered = state.setdefault("beats", {})
    for b in beats:
        bid = b["beat_id"]
        clip = rendered.get(bid, {})
        if not clip or clip.get("status") not in ("success", "mock"):
            log(f"[render] healing failed beat '{bid}' (seed jitter)…")
            b["_seed_jitter"] = b.get("_seed_jitter", 0) + 1
            media_tools.make_render_beat_stage(bid)(ctx)

    log("[render] compositing master (transitions + realism grade)…")
    compositor.composite_timeline(ctx)
    _record_spend(state, mode)
    state["metadata"]["current_stage"] = "render"


async def _run_qa(session: Session, mode: str, log: Logger) -> None:
    ctx = _ctx(session, mode, log)
    from app.adk.improvement import AdversarialRefiner
    
    # Run the ProductionCriticLoop automatically so that UI/interactive runs do
    # the closed-loop adversarial refinement to automatically resolve defects.
    critic_loop = LoopAgent(
        "ProductionCriticLoop",
        [qa_mod.build_qa_agent(), AdversarialRefiner()],
        max_iterations=3,
        should_exit=lambda s: bool(s.get("_critic_exit")))
    
    await critic_loop.run(ctx)
    _record_spend(session.state, mode)
    session.state["metadata"]["current_stage"] = "qa"
    session.state["metadata"]["status"] = "complete"


_RUNNERS = {
    "script": _run_script,
    "visual_plan": _run_visual_plan,
    "reference_frame": _run_reference_frame,
    "render": _run_render,
    "qa": _run_qa,
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
    return bool(path) and os.path.exists(path)


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


def frame_review(state: dict) -> dict:
    rf = state.get("reference_frame", {})
    all_uris = rf.get("all_uris", [])
    uri = rf.get("uri") if not all_uris else all_uris[0]
    
    # Retrieve the start/end frame URIs per beat from the planned beats
    beats = state.get("beat_prompts", {}).get("beats", [])
    beats_frames = []
    for b in beats:
        beats_frames.append({
            "beat_id": b.get("beat_id"),
            "start_uri": b.get("_start_frame_uri"),
            "end_uri": b.get("_end_frame_uri"),
        })

    return {
        "uri": uri,
        "all_uris": all_uris,
        "beats_frames": beats_frames,
        "status": rf.get("status"),
        "exists": _file_ok(uri)
    }


def render_review(state: dict) -> dict:
    prod = state.get("production", {})
    uri = prod.get("final_uri")
    beats = state.get("beats", {})
    return {
        "final_uri": uri,
        "exists": _file_ok(uri),
        "status": prod.get("status"),
        "duration_s": prod.get("duration_s"),
        "beats_used": prod.get("beats_used", []),
        "beat_status": {bid: clip.get("status") for bid, clip in beats.items()},
        "captions_burned": prod.get("captions_burned", False),
        "voiceover_uri": prod.get("voiceover_uri"),
    }


def qa_review(state: dict) -> dict:
    qa = state.get("qa_report", {})
    return {
        "approved": qa.get("approved"),
        "overall": qa.get("overall_score"),
        "realism": qa.get("realism_score"),
        "lip_sync": qa.get("lip_sync_score"),
        "audio": qa.get("audio_score"),
        "continuity": qa.get("continuity_score"),
        "brief_adherence": qa.get("brief_adherence_score"),
        "product_visibility": qa.get("product_visibility_score"),
        "summary": qa.get("summary", ""),
        "defects": qa.get("defects", []),
    }


REVIEWERS = {
    "script": script_review,
    "visual_plan": visual_review,
    "reference_frame": frame_review,
    "render": render_review,
    "qa": qa_review,
}


def review_payload(segment_key: str, state: dict) -> dict:
    return REVIEWERS[segment_key](state)


def cost_summary(state: dict) -> dict:
    cb = cost_breakdown(state)
    cb["dev_remaining_usd"] = DevSpendTracker().remaining()
    return cb
