"""
Functional tests for the DYNAMIC, brief-driven creative engine (LLM_ONLY).
=========================================================================

These run the REAL creative agents (Gemini Flash) — not mocks — and assert that the
pipeline follows the user's brief: extracts the hero product, realizes the brief's beats,
features the product, locks identity while adapting styling, and honors HITL feedback.

No video is rendered (LLM_ONLY) so cost is a few thousand Flash tokens (~$0.002/run).

Run:  python3 -m tests.test_dynamic_pipeline
"""
from __future__ import annotations

import asyncio
import sys

from app.ui import pipeline as P
from app.adk import prompts
from app.adk.profiles.registry import resolve_profile
from app.adk.profiles import brands

MODE = "LLM_ONLY"

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

YOGA_BRIEF = (
    "20-second calm, premium commercial for a new grippy non-slip YOGA MAT. Tone: serene, mindful. "
    "Show the mat unrolling, a smooth flow sequence proving the no-slip grip, a close-up of the textured "
    "surface, and a soft CTA to shop the new mat."
)

PASSED, FAILED = [], []


def check(name: str, cond: bool, detail: str = ""):
    (PASSED if cond else FAILED).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  ·  {detail}" if detail and not cond else ""))


async def run_creative(brief: str, brand_id: str) -> P.Session:
    cfg = {"brand_id": brand_id, "character_id": "sienna_fitness_01",
           "platform": "Instagram Reels", "aspect_ratio": "9:16",
           "user_brief": brief, "mode": MODE, "session_id": f"ft_{brand_id}"}
    sess = P.new_production_session(cfg)
    log = lambda m: None
    await P.run_segment("script", sess, MODE, log)
    await P.run_segment("visual_plan", sess, MODE, log)
    return sess


def assert_shoe(sess):
    st = sess.state
    strat = st["strategy"]
    beats = st["beat_prompts"]["beats"]
    allprompts = " ".join(b.get("prompt", "") for b in beats).lower()
    profile = resolve_profile("sienna_fitness_01", brand=brands.get_brand("nike_training"))

    print("\n[SHOE] strategy.product:", strat.get("product"))
    print("[SHOE] selling points:", strat.get("key_selling_points"))
    print("[SHOE] wardrobe:", st["wardrobe"].get("wardrobe"), "| hair:", st["wardrobe"].get("hair_style"))
    for b in beats:
        print(f"   - {b['beat_id']}: PA='{b.get('product_action','')[:60]}' "
              f"OST='{b.get('on_screen_text','')}' :: {b.get('prompt','')[:90]}")

    check("product is the shoe", "shoe" in (strat.get("product", "")).lower(),
          strat.get("product", ""))
    check("selling points extracted", len(strat.get("key_selling_points", [])) >= 2)
    check("beats reference the shoe/sole (brief fidelity)",
          sum(t in allprompts for t in ["shoe", "sole", "sneaker", "footwear", "knit"]) >= 1, allprompts[:120])
    check("brief-specific actions present (jump/lunge/grip/flex/walk)",
          any(t in allprompts for t in ["jump", "lunge", "grip", "flex", "pavement", "walk", "lace", "slip"]),
          allprompts[:120])
    check("product_action populated on >=2 beats",
          sum(bool(b.get("product_action")) for b in beats) >= 2)
    check("on_screen_text carried from brief on >=1 beat",
          sum(bool(b.get("on_screen_text")) for b in beats) >= 1)
    check("all beats native talking-head (she speaks in her own voice)",
          all(b.get("sync_mode") == "native" for b in beats))
    check("exactly 5 beats in order",
          [b["beat_id"] for b in beats] == ["hook", "intro", "action", "proof", "cta"],
          str([b["beat_id"] for b in beats]))

    # Final assembled Veo prompt must carry the immutable identity lock + product.
    proof = next(b for b in beats if b["beat_id"] == "proof")
    final = prompts.build_beat_generation_prompt(proof, profile, use_anchor=False)
    check("assembled prompt carries FIXED identity lock", "FIXED FACE" in final)
    check("assembled prompt carries the negative/anti-AI block", "--no plastic skin" in final)


def assert_styling_adapts(shoe_sess, yoga_sess):
    sw = shoe_sess.state["wardrobe"]
    yw = yoga_sess.state["wardrobe"]
    print("\n[ADAPT] shoe location:", sw.get("location"))
    print("[ADAPT] yoga location:", yw.get("location"))
    check("wardrobe present for both", bool(sw.get("wardrobe")) and bool(yw.get("wardrobe")))
    check("hair_style present (adaptive styling field used)",
          bool(sw.get("hair_style")) and bool(yw.get("hair_style")))
    check("styling/location differs between shoe vs yoga campaign",
          (sw.get("location", "").lower() != yw.get("location", "").lower())
          or (sw.get("wardrobe", "").lower() != yw.get("wardrobe", "").lower()))


def assert_identity_constant(shoe_sess, yoga_sess):
    # The immutable identity lock must be byte-identical regardless of campaign/brand.
    p_shoe = resolve_profile("sienna_fitness_01", brand=brands.get_brand("nike_training"))
    p_yoga = resolve_profile("sienna_fitness_01", brand=brands.get_brand("alo_yoga"))
    check("identity lock is campaign-independent (face/voice constant)",
          p_shoe.identity_lock() == p_yoga.identity_lock())


async def assert_hitl(brief: str):
    sess = await run_creative(brief, "nike_training")
    before = sess.state["script"]["script_text"]
    log = lambda m: None
    await P.regenerate_segment(
        "script", sess, MODE,
        "Open the hook with a shocking statistic about foot injuries, and make it punchier.", log)
    after = sess.state["script"]["script_text"]
    print("\n[HITL] before[:80]:", before[:80])
    print("[HITL] after [:80]:", after[:80])
    check("HITL feedback changed the script", before.strip() != after.strip())


async def main():
    print("=== Functional test: dynamic brief-driven engine (LLM_ONLY) ===")
    print("\n--- Running SHOE brief (Nike Training) ---")
    shoe = await run_creative(SHOE_BRIEF, "nike_training")
    assert_shoe(shoe)

    print("\n--- Running YOGA brief (Alo Yoga) for styling adaptivity ---")
    yoga = await run_creative(YOGA_BRIEF, "alo_yoga")
    assert_styling_adapts(shoe, yoga)
    assert_identity_constant(shoe, yoga)

    print("\n--- HITL regeneration ---")
    await assert_hitl(SHOE_BRIEF)

    print(f"\n=== RESULT: {len(PASSED)} passed, {len(FAILED)} failed ===")
    if FAILED:
        print("FAILED:", FAILED)
        sys.exit(1)
    print("ALL FUNCTIONAL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
