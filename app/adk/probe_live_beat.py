"""
Arrowow Studio — Single Live Beat Probe (cost-gated)
====================================================

Renders ONE beat live on Veo 3.1 to validate auth/params/quality + cost BEFORE any
full 5-beat render. Uses the mock shot list (no LLM cost) so the only spend is the
single Veo call (~$1.20 for 8s). Enforces the $100 dev-spend ceiling.

    python -m app.adk.probe_live_beat            # renders the 'intro' beat
    python -m app.adk.probe_live_beat action     # renders a specific beat
"""
from __future__ import annotations

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.adk.core import InvocationContext
from app.adk.state import session as ss
from app.adk.state.cost_ledger import CostLedger, DevSpendTracker
from app.adk import creative_agents as ca, prompts
from app.adk.tools import media_tools
from app.adk.profiles.registry import resolve_profile
from app.adk.profiles.realism import UGC_REALISM


def main():
    beat_id = sys.argv[1] if len(sys.argv) > 1 else "intro"
    profile = resolve_profile("sienna_fitness_01")

    sess = ss.make_session("LIVE_MEDIA", f"single beat probe ({beat_id})")
    state = sess.state
    state["character"] = {"character_id": profile.character_id}
    state["beat_prompts"] = ca._mock_shot_prompt(state)   # mock shot list — no LLM cost
    ctx = InvocationContext(sess, "LIVE_MEDIA", print)

    # --- dev-spend guard ---
    tracker = DevSpendTracker()
    projected = 8 * 0.15
    print(f"[budget] spent ${tracker.total_spent():.2f} / ${tracker.CEILING_USD:.0f} · "
          f"remaining ${tracker.remaining():.2f} · this beat ~${projected:.2f}")
    if tracker.would_exceed(projected):
        print("[budget] HALT — would exceed the dev ceiling."); return

    beat = next(b for b in state["beat_prompts"]["beats"] if b["beat_id"] == beat_id)
    final_prompt = prompts.build_beat_generation_prompt(beat, profile, UGC_REALISM)
    print("\n================= FINAL VEO PROMPT =================")
    print(final_prompt)
    print("===================================================\n")
    print(f"[render] beat={beat_id} seed_locked={beat['seed_locked']} "
          f"sync={beat['sync_mode']} — calling Veo 3.1 (1-3 min)...\n")

    media_tools.make_render_beat_stage(beat_id)(ctx)

    # --- cost accounting ---
    session_dir = "output/" + state["metadata"]["session_id"]
    ledger = CostLedger(state)
    ledger.write_logs(session_dir)
    spent = ledger.total_usd
    total = DevSpendTracker().record_run(state["metadata"]["session_id"], spent, "LIVE_MEDIA")

    print("\n===================== RESULT ======================")
    print(json.dumps(state["beats"].get(beat_id, {}), indent=2))
    print(f"actual beat cost : ${spent:.4f}")
    print(f"dev spend total  : ${total:.2f} / ${DevSpendTracker.CEILING_USD:.0f}  "
          f"(remaining ${DevSpendTracker().remaining():.2f})")
    print(f"artifacts        : {session_dir}/")
    print("===================================================")


if __name__ == "__main__":
    main()
