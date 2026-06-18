"""
Arrowow Studio — Single-Beat Closed-Loop QA Refinement (GAN-style)
==================================================================

Perfect ONE beat before any full render. Each iteration is an adversarial round:

    Generator (Veo + anchor + seed)  ->  Discriminator (Gemini 3.1 Pro QA)  ->
    Refiner (retrieve remedy for worst defect, mutate the prompt / convert lip-sync
             beats to voiceover / jitter the seed)  ->  regenerate.

Loops until QA approves or the iteration / budget cap is hit. Every render + QA call is
cost-logged and guarded against the $100 dev ceiling. The best-scoring clip is reported.

    python -m app.adk.refine_beat --beat intro --iters 3            # live
    python -m app.adk.refine_beat --beat action --mode DRY_RUN      # wiring smoke test
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.adk.core import InvocationContext
from app.adk.state import session as ss
from app.adk.state.cost_ledger import CostLedger, DevSpendTracker
from app.adk import creative_agents as ca, qa
from app.adk.tools import media_tools
from app.adk.improvement import DefectRemedyKB
from app.adk.profiles.registry import resolve_profile

RENDER_USD = 8 * 0.15          # one beat
QA_USD = 0.05                  # rough per QA pass
ITER_USD = RENDER_USD + QA_USD


def _apply_remedy(beat: dict, defect: dict, kb: DefectRemedyKB, log) -> str:
    """Apply STRUCTURED changes per defect (flags/fields, not raw prompt text — raw appends
    bloat the prompt and can trip Vertex RAI)."""
    dtype, sev = defect.get("type"), int(defect.get("severity", 0))
    remedy = kb.retrieve(dtype)
    if dtype in ("lip_sync", "vocal_audio") and beat.get("sync_mode") == "native":
        beat["sync_mode"], beat["seed_locked"] = "voiceover", True
        log("    -> CONVERTING to VOICEOVER B-roll (eliminates lip-sync / robotic-TTS risk)")
    elif dtype == "hyperrealism":
        beat["_realism_boost"] = True
        log("    -> realism boost (relax stiffness, soften eyes)")
    elif dtype in ("identity_drift", "artifact"):
        beat["_seed_jitter"] = beat.get("_seed_jitter", 0) + 1
        log("    -> seed jitter for fresh structure while keeping the anchor")
    return remedy


async def refine(beat_id: str, max_iters: int, mode: str) -> None:
    profile = resolve_profile()
    sess = ss.make_session(mode, f"refine {beat_id}")
    state = sess.state
    state["character"] = {"character_id": profile.character_id}
    state["beat_prompts"] = ca._mock_shot_prompt(state)
    beat = next(b for b in state["beat_prompts"]["beats"] if b["beat_id"] == beat_id)
    ctx = InvocationContext(sess, mode, print)
    kb, tracker = DefectRemedyKB(), DevSpendTracker()

    anchor = profile.resolve_anchor()
    print(f"[setup] beat={beat_id} · anchor={'YES ('+anchor+')' if anchor else 'none'} · "
          f"prefers_voiceover={profile.prefers_voiceover} · dev spend ${tracker.total_spent():.2f}/$100")

    history, best = [], None
    for i in range(1, max_iters + 1):
        if mode == "LIVE_MEDIA" and tracker.total_spent() + CostLedger(state).total_usd + ITER_USD > tracker.CEILING_USD:
            print("[budget] HALT — next iteration would breach the $100 ceiling."); break

        print(f"\n========== ITERATION {i}/{max_iters} "
              f"(sync={beat['sync_mode']}, seed_locked={beat['seed_locked']}) ==========")
        media_tools.make_render_beat_stage(beat_id)(ctx)
        clip = state["beats"].get(beat_id, {})
        if clip.get("status") not in ("success", "mock"):
            print(f"[render] failed: {clip}"); continue
        uri = clip["uri"]

        report = await qa.review_clip(uri, state, beat_id) if mode == "LIVE_MEDIA" else qa._mock_qa(state)
        score = report.get("overall_score", 0)
        print(f"[QA] approved={report.get('approved')} overall={score} "
              f"realism={report.get('realism_score')} lip_sync={report.get('lip_sync_score')} "
              f"audio={report.get('audio_score')} continuity={report.get('continuity_score')}")
        for d in report.get("defects", []):
            print(f"     defect: {d.get('type')}@{d.get('segment')} sev{d.get('severity')} — "
                  f"{(d.get('description') or '')[:90]}")
        if report.get("summary"):
            print(f"     summary: {report['summary'][:160]}")

        history.append({"iter": i, "uri": uri, "qa": report})
        if best is None or score > best["qa"].get("overall_score", 0):
            best = history[-1]
        if report.get("approved"):
            print("\n✅ QA APPROVED — beat is production-grade."); break

        defects = sorted(report.get("defects", []), key=lambda d: -int(d.get("severity", 0)))
        if defects:
            print(f"[refine] worst defect: {defects[0].get('type')} -> applying remedy")
            _apply_remedy(beat, defects[0], kb, print)

    # cost accounting
    session_dir = "output/" + state["metadata"]["session_id"]
    ledger = CostLedger(state)
    ledger.write_logs(session_dir)
    spent = ledger.total_usd
    if spent > 0:
        DevSpendTracker().record_run(state["metadata"]["session_id"], spent, mode)

    print("\n===================== REFINEMENT SUMMARY =====================")
    for h in history:
        q = h["qa"]
        print(f"  iter {h['iter']}: overall={q.get('overall_score')} realism={q.get('realism_score')} "
              f"lip_sync={q.get('lip_sync_score')} approved={q.get('approved')} -> {h['uri']}")
    if best:
        print(f"\n  BEST CLIP : {best['uri']}  (overall={best['qa'].get('overall_score')})")
    print(f"  run cost  : ${spent:.4f}")
    print(f"  dev spend : ${DevSpendTracker().total_spent():.2f} / ${DevSpendTracker.CEILING_USD:.0f} "
          f"(remaining ${DevSpendTracker().remaining():.2f})")
    print("==============================================================")


def main():
    ap = argparse.ArgumentParser(description="Single-beat closed-loop QA refinement")
    ap.add_argument("--beat", default="intro", help="hook|intro|action|proof|cta")
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--mode", default="LIVE_MEDIA", choices=["DRY_RUN", "LIVE_MEDIA"])
    args = ap.parse_args()
    asyncio.run(refine(args.beat, args.iters, args.mode))


if __name__ == "__main__":
    main()
