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


def resolve_segment_to_beat(seg: str) -> str:
    """Parse time-range or timestamp segment names (e.g., '00:03-00:07' or '12s')
    from the QA critic into the matching beat ID."""
    if not seg:
        return "global"
    seg_lower = str(seg).lower()
    for bid in ["hook", "intro", "action", "proof", "cta"]:
        if bid in seg_lower:
            return bid
    # Try parsing mm:ss or hh:mm:ss timestamp range
    import re
    matches = re.findall(r"(\d+):(\d+)", seg_lower)
    if matches:
        try:
            m, s = map(int, matches[0])
            sec = m * 60 + s
            if sec < 8: return "hook"
            elif sec < 16: return "intro"
            elif sec < 24: return "action"
            elif sec < 32: return "proof"
            else: return "cta"
        except Exception:
            pass
    # Try parsing raw seconds e.g. "12s" or "12 seconds"
    sec_matches = re.findall(r"(\d+)\s*(?:s|sec|second)", seg_lower)
    if sec_matches:
        try:
            sec = int(sec_matches[0])
            if sec < 8: return "hook"
            elif sec < 16: return "intro"
            elif sec < 24: return "action"
            elif sec < 32: return "proof"
            else: return "cta"
        except Exception:
            pass
    return "global"


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
        dtype = worst.get("type")
        raw_seg = worst.get("segment", "global")
        seg = resolve_segment_to_beat(raw_seg)
        remedy = self.kb.retrieve(dtype)
        ctx.log(f"    [AdversarialRefiner] worst defect: {dtype}@{raw_seg} (resolved={seg}) (sev {worst.get('severity')}) "
                f"-> remedy: {remedy[:70]}...")

        # Targeted beat refinement via STRUCTURED flags (no raw prompt-text append, which
        # bloats the prompt and can trip RAI). Re-render ONLY the failing beat.
        beats = ctx.state.get("beat_prompts", {}).get("beats", [])
        target = next((b for b in beats if b.get("beat_id") == seg), None)
        if target is not None:
            if dtype in ("lip_sync", "vocal_audio"):
                if target.get("sync_mode") == "native":
                    target["sync_mode"] = "voiceover"
                else:
                    target["_seed_jitter"] = target.get("_seed_jitter", 0) + 1
            elif dtype in ("hyperrealism", "color"):
                target["_realism_boost"] = True
                target["_color_flatten"] = True
            elif dtype in ("artifact", "identity_drift"):
                target["_seed_jitter"] = target.get("_seed_jitter", 0) + 1
            media_tools.make_render_beat_stage(seg)(ctx)  # re-render the single beat
        else:
            ctx.log(f"    [AdversarialRefiner] global defect ({dtype}) -> adjusting post-production grading")
            vf_params = ctx.state.setdefault("compositor_vf_params", {
                "noise": 7, "saturation": 0.92, "contrast": 0.98, "brightness": -0.01
            })
            if dtype == "color":
                vf_params["saturation"] = max(0.5, vf_params["saturation"] - 0.08)
                vf_params["contrast"] = max(0.8, vf_params["contrast"] - 0.03)
                ctx.log(f"      -> reduced saturation to {vf_params['saturation']:.2f}, contrast to {vf_params['contrast']:.2f}")
            elif dtype == "hyperrealism":
                vf_params["noise"] = min(15, vf_params["noise"] + 3)
                vf_params["saturation"] = max(0.5, vf_params["saturation"] - 0.05)
                vf_params["contrast"] = max(0.8, vf_params["contrast"] - 0.05)
                ctx.log(f"      -> increased noise to {vf_params['noise']}, saturation to {vf_params['saturation']:.2f}")

        # Re-composite so the next QA pass sees the corrected master.
        compositor.composite_timeline(ctx)
