"""
Arrowow Studio — Adversarial Refinement Loop (GAN-style automated improvement)
==============================================================================

The quality engine. We frame iterative improvement as an adversarial game:

  • Generator      = the media pipeline (Veo render + the beat prompt).
  • Discriminator  = the QA agent (qa.py) — scores realism/sync/continuity, finds defects.
  • Refiner        = this module — when the discriminator rejects, it retrieves a remedy
                     for the worst defect (RAG-style from DefectRemedyKB), mutates ONLY the
                     failing beat (prompt + seed), re-renders it, and re-composites.

This repeats (bounded) until QA approves — automated, targeted, cost-aware improvement
that fixes lip-sync / vocal / transition / soundtrack / hyperrealism / identity issues
agent-by-agent rather than regenerating the whole video.
"""
from __future__ import annotations

from .core import BaseAgent, InvocationContext
from .tools import media_tools, compositor


class DefectRemedyKB:
    """A small retrieval knowledge base mapping each defect type to a concrete remediation
    directive. This is the 'RAG' the Refiner consults to fix a specific problem."""

    REMEDIES = {
        "lip_sync": ("shorten and simplify the spoken line to open vowels; keep mouth "
                     "movement minimal; if it persists, convert this beat to voiceover B-roll"),
        "vocal_audio": ("regenerate the voice with the character's exact voice profile "
                        "(Australian accent, natural breaths); slow the pace; remove robotic flatness"),
        "transition": ("match the end posture of the previous beat to the start of this one; "
                       "apply a motion-masked whip-pan or a short xfade to hide the seam"),
        "soundtrack": ("remove any music; keep only natural room tone; normalize dialogue to "
                       "broadcast loudness (~-14 LUFS)"),
        "hyperrealism": ("strengthen realism: real skin pores and texture, handheld micro-shake, "
                         "uneven natural light, film grain; remove cinematic gloss and beauty smoothing"),
        "identity_drift": ("re-apply the character casting block verbatim and the locked seed; "
                           "regenerate from the canonical reference frame"),
        "artifact": ("regenerate with a jittered seed and a tighter negative prompt; reduce "
                     "motion complexity in the shot"),
        "color": ("re-grade to the reference white balance; unify exposure and saturation across beats"),
        "pacing": ("trim or extend the beat to its target duration; align energy to the arc"),
        "framing": ("recompose to the specified camera code; fix headroom and subject placement"),
    }

    def retrieve(self, defect_type: str) -> str:
        return self.REMEDIES.get(defect_type,
                                 "regenerate the failing segment with reinforced directives")


class AdversarialRefiner(BaseAgent):
    """Generator-update step of the adversarial loop. Runs right after the QA discriminator
    inside the production critic LoopAgent."""

    def __init__(self):
        super().__init__("AdversarialRefiner")
        self.kb = DefectRemedyKB()

    async def run(self, ctx: InvocationContext) -> None:
        qa = ctx.state.get("qa_report", {})
        if qa.get("approved"):
            ctx.state["_critic_exit"] = True
            ctx.log("    [AdversarialRefiner] QA approved -> exit loop")
            return

        ctx.state["_critic_exit"] = False
        ledger = ctx.state.setdefault("cost_ledger", {})
        ledger["regenerations"] = ledger.get("regenerations", 0) + 1

        defects = sorted(qa.get("defects", []), key=lambda d: -int(d.get("severity", 0)))
        if not defects:
            ctx.log("    [AdversarialRefiner] rejected but no defects listed -> recomposite")
            compositor.composite_timeline(ctx)
            return

        worst = defects[0]
        dtype, seg = worst.get("type"), worst.get("segment", "global")
        remedy = self.kb.retrieve(dtype)
        ctx.log(f"    [AdversarialRefiner] worst defect: {dtype}@{seg} (sev {worst.get('severity')}) "
                f"-> remedy: {remedy[:70]}...")

        # Targeted beat refinement via STRUCTURED flags (no raw prompt-text append, which
        # bloats the prompt and can trip RAI). Re-render ONLY the failing beat.
        beats = ctx.state.get("beat_prompts", {}).get("beats", [])
        target = next((b for b in beats if b.get("beat_id") == seg), None)
        if target is not None:
            if dtype in ("lip_sync", "vocal_audio") and target.get("sync_mode") == "native":
                target["sync_mode"] = "voiceover"
            elif dtype == "hyperrealism":
                target["_realism_boost"] = True
            elif dtype in ("artifact", "identity_drift"):
                target["_seed_jitter"] = target.get("_seed_jitter", 0) + 1
            media_tools.make_render_beat_stage(seg)(ctx)  # re-render the single beat
        else:
            ctx.log(f"    [AdversarialRefiner] global defect ({dtype}) -> post-production re-pass")

        # Re-composite so the next QA pass sees the corrected master.
        compositor.composite_timeline(ctx)
