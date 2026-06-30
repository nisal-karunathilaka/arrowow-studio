"""
Arrowow Studio — Phase-by-phase self-test (no GCP, no credits)
==============================================================

    python -m app.adk.selftest

Verifies, without any live API calls:
  1. DRY_RUN  — full graph runs end-to-end on mocks (Phase 1 regression).
  2. LLM_ONLY — the LIVE creative path is taken, using a STUBBED structured backend
                (proves the wiring + that live results, not mocks, populate state),
                and the deterministic filter-bypass net scrubs banned terms.
  3. Contract — a schema-invalid backend result RAISES (no regex/JSON fallback).

Exit code 0 = all pass.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.adk import creative_agents, llm_backend, qa
from app.adk.app import build_director
from app.adk.core import InvocationContext
from app.adk.state import session as session_state
from app.adk.state import cost_ledger


# A canned, schema-valid response per agent schema — stands in for Vertex Gemini.
# Note: one beat prompt intentionally contains 'tight' to test the filter-bypass net.
_CANNED = {
    "StrategyResponse": {"hook": "LIVE-hook", "angle": "LIVE-angle", "cta": "LIVE-cta"},
    "ScriptResponse": {"script_text": "LIVE script ... GET after it.", "estimated_duration_seconds": 30},
    "TextCriticResponse": {"approved": True, "feedback": "LIVE-ok", "brand_safety_score": 1.0},
    "StoryboardResponse": {"scene_actions": ["a1", "a2", "a3", "a4", "a5"],
                            "scene_cameras": ["C2", "C1", "C4", "C3", "C1"]},
    "WardrobeLocationResponse": {"wardrobe": "activewear top", "location": "gym"},
    "BeatPromptsResponse": {
        "reference_frame_prompt": "LIVE portrait of Sienna",
        "beats": [
            {"beat_id": "hook", "camera": "C2", "sync_mode": "native", "seed_locked": True,
             "prompt": "hook shot in tight leggings", "dialogue_or_vo": "Quick check..."},
            {"beat_id": "intro", "camera": "C1", "sync_mode": "native", "seed_locked": True,
             "prompt": "intro shot", "dialogue_or_vo": "here's the deal"},
            {"beat_id": "action", "camera": "C4", "sync_mode": "voiceover", "seed_locked": False,
             "prompt": "action wide", "dialogue_or_vo": "I train hard"},
            {"beat_id": "proof", "camera": "C3", "sync_mode": "voiceover", "seed_locked": False,
             "prompt": "macro detail", "dialogue_or_vo": "just performance"},
            {"beat_id": "cta", "camera": "C1", "sync_mode": "native", "seed_locked": True,
             "prompt": "cta shot", "dialogue_or_vo": "get after it"},
        ],
    },
}


async def _fake_generate(system_instruction, user_prompt, output_schema, state=None, model=None):
    return dict(_CANNED[output_schema.__name__])


async def _fake_invalid(system_instruction, user_prompt, output_schema, state=None, model=None):
    return {}  # missing required fields -> must fail schema validation


def _run(mode: str) -> dict:
    director = build_director(autonomous=True)
    sess = session_state.make_session(mode=mode, scenario="selftest scenario")
    ctx = InvocationContext(sess, mode=mode, logger=lambda *_: None)
    return asyncio.run(director.run(ctx)), sess.state


def main() -> int:
    failures = []

    # 1. DRY_RUN regression
    summary, state = _run("DRY_RUN")
    if summary["status"] != "complete" or len(summary["beats"]) != 5:
        failures.append(f"DRY_RUN did not complete with 5 beats: {summary['status']}, {summary['beats']}")
    if state["strategy"].get("hook", "").startswith("LIVE-"):
        failures.append("DRY_RUN unexpectedly used the live path")
    print(f"  [1] DRY_RUN: status={summary['status']} beats={len(summary['beats'])}")

    # 2. LLM_ONLY with stubbed live backend
    original = llm_backend.structured_generate
    creative_agents.llm_backend.structured_generate = _fake_generate
    try:
        summary, state = _run("LLM_ONLY")
    finally:
        creative_agents.llm_backend.structured_generate = original

    if state["strategy"].get("hook") != "LIVE-hook":
        failures.append(f"LLM_ONLY did not take the live path: strategy={state['strategy']}")
    if summary["status"] != "complete" or len(summary["beats"]) != 5:
        failures.append(f"LLM_ONLY did not complete with 5 beats: {summary['status']}")
    hook_prompt = next(b["prompt"] for b in state["beat_prompts"]["beats"] if b["beat_id"] == "hook")
    if "tight" in hook_prompt.lower():
        failures.append(f"filter-bypass failed to scrub 'tight': {hook_prompt!r}")
    print(f"  [2] LLM_ONLY (stubbed): live-path={state['strategy'].get('hook')!r} "
          f"hook_prompt_scrubbed={'tight' not in hook_prompt.lower()}")

    # 3. No-fallback contract: invalid structured output must raise
    creative_agents.llm_backend.structured_generate = _fake_invalid
    raised = False
    try:
        _run("LLM_ONLY")
    except Exception as e:
        raised = True
        err = type(e).__name__
    finally:
        creative_agents.llm_backend.structured_generate = original
    if not raised:
        failures.append("invalid structured output did NOT raise (fallback contract broken)")
    print(f"  [3] no-fallback contract: invalid output raised={raised}"
          + (f" ({err})" if raised else ""))

    # 4. Budget guard: unit thresholds + director halt when pre-exceeded
    if cost_ledger.evaluate_budget({"video_seconds": 100}) != "exceeded":
        failures.append("budget guard did not flag 'exceeded' at 100s")
    if cost_ledger.evaluate_budget({"video_seconds": 40}) != "within_limit":
        failures.append("budget guard wrongly flagged 40s")
    director = build_director(autonomous=True)
    sess = session_state.make_session(mode="DRY_RUN", scenario="budget test")
    sess.state["cost_ledger"]["video_seconds"] = 100  # pre-exceed before any stage
    ctx = InvocationContext(sess, mode="DRY_RUN", logger=lambda *_: None)
    bsummary = asyncio.run(director.run(ctx))
    if bsummary["status"] != "halted_budget" or bsummary["beats"]:
        failures.append(f"budget guard did not halt the run: {bsummary['status']}, beats={bsummary['beats']}")
    print(f"  [4] budget guard: thresholds ok, director halted={bsummary['status']=='halted_budget'}")

    # 5. PreProduction refinement: a rejecting TextCritic forces the loop to max iterations
    calls = {"n": 0}
    def _reject_critic(state):
        calls["n"] += 1
        return {"approved": False, "feedback": "rejected", "brand_safety_score": 0.3}
    orig_tc = creative_agents._mock_text_critic
    creative_agents._mock_text_critic = _reject_critic
    try:
        _run("DRY_RUN")
    finally:
        creative_agents._mock_text_critic = orig_tc
    if calls["n"] != 3:
        failures.append(f"PreProductionLoop did not iterate to max 3 on rejection (ran {calls['n']})")
    print(f"  [5] preprod refinement loop: critic-rejections iterated={calls['n']}/3")

    # 6. Adversarial loop: a rejecting QA reviewer routes targeted regenerations to max
    def _reject_qa(state):
        return {"approved": False, "overall_score": 4, "realism_score": 4, "lip_sync_score": 4,
                "audio_score": 5, "continuity_score": 5,
                "defects": [{"type": "hyperrealism", "segment": "intro", "severity": 4,
                             "description": "looks too AI/plastic", "remedy_hint": "add grain"}],
                "summary": "rejected"}
    orig_qa = qa._mock_qa
    qa._mock_qa = _reject_qa
    try:
        _, vstate = _run("DRY_RUN")
    finally:
        qa._mock_qa = orig_qa
    regens = vstate["cost_ledger"].get("regenerations", 0)
    if regens != 3:
        failures.append(f"AdversarialRefiner did not route regenerations to max 3 (got {regens})")
    print(f"  [6] adversarial refine loop: regenerations={regens}/3")

    print("-" * 50)
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS — Phases 1–2 verified: graph, live-path, filter-bypass, no-fallback, "
          "budget guard, refinement loop, defect routing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
