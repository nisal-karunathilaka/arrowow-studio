"""
Live validation harness — render a scenario end-to-end and capture it for inspection.
====================================================================================

Runs the full dynamic pipeline in LIVE_MEDIA for one scenario, prints the QA report +
real cost, and extracts one frame per beat (plus the assembled Veo prompts) so the
output can be visually inspected and the prompts iterated.

Usage:
    python3 -m tests.live_validate <scenario_key>

Scenarios are defined in SCENARIOS below. Frames + a report land in
output/<session_id>/_inspect/.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

from app.ui import pipeline as P

# ---------------------------------------------------------------------------
# Scenario catalogue
# ---------------------------------------------------------------------------
SHOE_BRIEF = (
    "Create a 30-second high-energy commercial for a new seamless TRAINING SHOE, targeting women "
    "20-35 getting into fitness. Urgent, motivating 'tough-love bestie' tone, fast cuts, bright "
    "lighting, low camera angle to keep the SHOES the visual hero. "
    "[0:00-0:05 Hook] holding an old clunky sneaker, cut to slipping on the sleek seamless shoe. "
    "VO: 'Stop ruining your workouts with heavy clunky sneakers that give you blisters.' Text: Ditch clunky shoes. "
    "[0:05-0:12 Performance] explosive box jumps and lateral lunges, zoom on the sole gripping the floor. "
    "VO: 'No slipping, no sliding, zero foot pain.' Text: Lock-in support. "
    "[0:12-0:18 Product close-up] bending the flexible knit and pressing the bouncy sole. "
    "VO: 'Ultra-lightweight, molds to your foot, handles your toughest gym days.' Text: Performs + Flexes. "
    "[0:18-0:25 Lifestyle] walking outside on pavement, styled casually. VO: 'The cushion is so soft you can "
    "wear them all day.' Text: All-day cushion. "
    "[0:25-0:30 CTA] smiling at camera pointing to a link. VO: 'Hit the link and shop the drop today!' Text: SHOP THE DROP."
)

LEGGINGS_BRIEF = (
    "30-second commercial for new high-waisted sculpting LEGGINGS in a calm, premium tone. Targeting "
    "women 20-35. Show: the leggings on as she moves through a flowing warm-up, a close-up of the "
    "high waistband and soft fabric, a confident mirror moment, and a soft CTA to shop the new drop. "
    "Bright airy studio. On-screen text: 'Sculpt + support', 'Buttery soft', 'Move freely', 'Shop now'."
)

YOGA_MAT_BRIEF = (
    "20-second serene commercial for a new grippy non-slip YOGA MAT. Mindful, premium tone. Show the mat "
    "unrolling, a smooth flow proving the no-slip grip, a macro of the textured surface as the hero "
    "product, and a soft CTA. On-screen text: 'Zero slip', 'Stay grounded', 'Shop the mat'."
)

ALO_SET_BRIEF = (
    "Create a premium, high-energy 30-second commercial for the new Alo Yoga Seamless Training Set, "
    "targeting active women 20-35 into fitness. Dynamic, upbeat modern soundtrack with clean cinematic "
    "transitions. Voiceover and on-screen text deliver a motivating, lifestyle-driven 'tough-love bestie' "
    "tone. Visually contrast an initial shot of the character in distracting, ill-fitting OLD gym clothing "
    "with a dramatic aesthetic cut into a sleek, matching Alo Yoga seamless set. Show her moving confidently "
    "through dynamic gym movements like squats and sprints, focusing closely on the fabric flexibility, "
    "performance, and a high-waist band that stays perfectly in place. Transition to a stylish studio-to-"
    "street lifestyle look, walking outdoors looking comfortable and effortlessly styled. Conclude with a "
    "strong confident focus on the character, directing viewers to shop the new product drop. "
    "Voiceover lines: 'Girl, look at me. Stop ruining your workouts—and your aesthetic—with cheap gear that "
    "distracts you. No rolling down, no pinching, and absolutely zero mid-squat adjustments. Alo actually "
    "engineered this seamless rib to perform like a second skin. The best part? It is so comfortable you "
    "will wear it 24/7 for running errands. Stop making excuses for bad activewear. Hit the link and shop "
    "the new Alo drop today!' On-screen text: 'Stop distracting yourself', 'Zero adjustments', "
    "'Performs + Sculpts', 'Studio-to-Street Comfort', 'SHOP THE ALO DROP TODAY'."
)

SCENARIOS = {
    "shoe":     {"brand_id": "nike_training", "aspect_ratio": "9:16",
                 "platform": "Instagram Reels", "user_brief": SHOE_BRIEF},
    "leggings": {"brand_id": "lululemon", "aspect_ratio": "9:16",
                 "platform": "Instagram Reels", "user_brief": LEGGINGS_BRIEF},
    "yogamat":  {"brand_id": "alo_yoga", "aspect_ratio": "9:16",
                 "platform": "TikTok", "user_brief": YOGA_MAT_BRIEF},
    "aloset":   {"brand_id": "alo_yoga", "aspect_ratio": "9:16",
                 "platform": "Instagram Reels", "user_brief": ALO_SET_BRIEF},
}

BEAT_MID = {"hook": 3, "intro": 11, "action": 18, "proof": 25, "cta": 33}


def _extract_frames(master: str, inspect_dir: str) -> list[str]:
    os.makedirs(inspect_dir, exist_ok=True)
    paths = []
    for bid, t in BEAT_MID.items():
        out = os.path.join(inspect_dir, f"frame_{bid}_{t}s.png")
        r = subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", master, "-frames:v", "1", out],
                           capture_output=True)
        if os.path.exists(out):
            paths.append(out)
    return paths


async def run(scenario_key: str, suffix: str = ""):
    sc = SCENARIOS[scenario_key]
    sid = f"live_{scenario_key}{('_' + suffix) if suffix else ''}"
    cfg = {"brand_id": sc["brand_id"], "character_id": "sienna_fitness_01",
           "platform": sc["platform"], "aspect_ratio": sc["aspect_ratio"],
           "user_brief": sc["user_brief"], "mode": "LIVE_MEDIA",
           "session_id": sid}

    print(f"=== LIVE VALIDATE: {scenario_key} · {sc['brand_id']} · {sc['aspect_ratio']} ===")
    print(f"budget remaining before: ${P.DevSpendTracker().remaining():.2f}")
    sess = P.new_production_session(cfg)
    log = lambda m: print(m, flush=True)

    for seg in P.SEGMENT_KEYS:
        await P.run_segment(seg, sess, "LIVE_MEDIA", log)

    from app.adk.state import session as _ss
    _ss.persist_state(sess.state)  # so the master can be re-composited without re-rendering Veo
    st = sess.state
    inspect_dir = os.path.join("output", cfg["session_id"], "_inspect")
    os.makedirs(inspect_dir, exist_ok=True)

    # Dump the assembled Veo prompts + key creative state for inspection.
    dump = {
        "scenario": scenario_key,
        "product": st.get("strategy", {}).get("product"),
        "selling_points": st.get("strategy", {}).get("key_selling_points"),
        "wardrobe": st.get("wardrobe", {}),
        "script": st.get("script", {}).get("script_text"),
        "beats": [{"beat_id": b["beat_id"], "camera": b.get("camera"),
                   "product_action": b.get("product_action"), "on_screen_text": b.get("on_screen_text"),
                   "prompt": b.get("prompt")}
                  for b in st.get("beat_prompts", {}).get("beats", [])],
        "render": P.render_review(st),
        "qa": P.qa_review(st),
        "cost": P.cost_summary(st),
    }
    with open(os.path.join(inspect_dir, "report.json"), "w") as f:
        json.dump(dump, f, indent=2)

    master = st.get("production", {}).get("final_uri")
    frames = _extract_frames(master, inspect_dir) if master and os.path.exists(master) else []

    print("\n=== RESULT ===")
    print("product:", dump["product"])
    print("master:", master)
    print("beat status:", dump["render"]["beat_status"])
    print("QA:", json.dumps(dump["qa"], indent=2))
    print("frames:", frames)
    print("cost:", dump["cost"]["total_estimated_cost_usd"], "| remaining:", dump["cost"]["dev_remaining_usd"])
    print("inspect dir:", inspect_dir)


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "shoe"
    suffix = sys.argv[2] if len(sys.argv) > 2 else ""
    asyncio.run(run(key, suffix))
