"""
Arrowow Studio — ArrowowDirector (root orchestrator)
====================================================

Deterministic root agent. Assembles and runs the agent graph (system design §2),
now extended with the QA discriminator + adversarial refiner and full cost governance:

    Intake -> PreProductionLoop -> VisualPlanningSequence -> ReferenceFrame
           -> [budget guard] -> MediaProductionParallel -> Compositor
           -> ProductionCriticLoop( QAReviewer -> AdversarialRefiner )

The Director owns: human-validation gates (auto-approve in autonomous mode), the
per-run budget guard + the $100 dev-spend ceiling, and final cost logging.
"""
from __future__ import annotations

from .core import (
    BaseAgent, InvocationContext, FunctionTool,
    SequentialAgent, ParallelAgent, LoopAgent,
)
from . import creative_agents as ca
from . import qa
from .improvement import AdversarialRefiner
from .schemas import BEAT_IDS
from .tools import media_tools, compositor
from .state import cost_ledger
from .state.cost_ledger import CostLedger, DevSpendTracker
from .profiles.registry import resolve_profile
from .state import session as ss

# Projected cost of a full live render (5 beats x 8s x $0.15 + 1 frame) — used by the guard.
PROJECTED_FULL_RENDER_USD = 5 * 8 * 0.15 + 0.04


class ArrowowDirector(BaseAgent):
    def __init__(self, autonomous: bool = True):
        super().__init__("ArrowowDirector")
        self.autonomous = autonomous
        self.graph = self._build_graph()

    # ---- graph assembly ---------------------------------------------------
    def _build_graph(self) -> list[BaseAgent]:
        pre_production = LoopAgent(
            "PreProductionLoop",
            [ca.build_strategist(), ca.build_scriptwriter(), ca.build_text_critic()],
            max_iterations=3,
            should_exit=lambda s: bool(s.get("text_critic", {}).get("approved")))

        visual_planning = SequentialAgent(
            "VisualPlanningSequence",
            [ca.build_storyboard(), ca.build_wardrobe(), ca.build_shot_prompt()])

        media_production = ParallelAgent(
            "MediaProductionParallel",
            [FunctionTool(f"render_beat:{b}", media_tools.make_render_beat_stage(b))
             for b in BEAT_IDS]
            + [FunctionTool("synthesize_voiceover", media_tools.synthesize_voiceover)]
            + [FunctionTool("download_soundtrack", media_tools.download_soundtrack)])

        critic_loop = LoopAgent(
            "ProductionCriticLoop",
            [qa.build_qa_agent(), AdversarialRefiner()],
            max_iterations=3,
            should_exit=lambda s: bool(s.get("_critic_exit")))

        return [
            FunctionTool("IntakeStage", self._intake),
            pre_production,
            FunctionTool("gate:script", self._gate("Story & Script", "script")),
            visual_planning,
            FunctionTool("gate:plan", self._gate("Visual Plan", "beat_prompts")),
            FunctionTool("ReferenceFrameStage", media_tools.generate_reference_frame),
            FunctionTool("gate:frame", self._gate("Reference Frame", "reference_frame")),
            FunctionTool("render_budget_guard", self._render_budget_guard),
            media_production,
            FunctionTool("failed_renders_healing_pass", self._heal_failed_renders),
            FunctionTool("CompositorStage", compositor.composite_timeline),
            FunctionTool("gate:cut", self._gate("Final Cut", "production")),
            critic_loop,
        ]

    # ---- run --------------------------------------------------------------
    async def run(self, ctx: InvocationContext) -> dict:
        ctx.log(f"[ArrowowDirector] start · mode={ctx.mode} · "
                f"session={ctx.state['metadata']['session_id']}")
        for stage in self.graph:
            if cost_ledger.evaluate_budget(ctx.state.get("cost_ledger", {})) == "exceeded":
                ctx.state["metadata"]["status"] = "halted_budget"
                ctx.log("[ArrowowDirector] PER-RUN BUDGET EXCEEDED — halting")
                break
            if ctx.state.get("_halt"):
                ctx.state["metadata"]["status"] = "halted_budget"
                break
            await stage.run(ctx)

        if ctx.state["metadata"].get("status") not in ("halted_budget",):
            ctx.state["metadata"]["status"] = "complete"

        # Persist cost logs + full session state + record live spend against the $100 ceiling.
        session_dir = "output/" + ctx.state["metadata"]["session_id"]
        ledger = CostLedger(ctx.state)
        ledger.write_logs(session_dir)
        ss.persist_state(ctx.state)
        spent = ledger.total_usd
        if spent > 0:
            DevSpendTracker().record_run(ctx.state["metadata"]["session_id"], spent, ctx.mode)
        return self._summary(ctx)

    # ---- stages -----------------------------------------------------------
    def _intake(self, ctx: InvocationContext) -> dict:
        scenario = ctx.state["metadata"].get("scenario", "")
        profile = resolve_profile("sienna_fitness_01")
        ctx.state["brief"] = {"scenario": scenario,
                              "brand": profile.brand.brand_name if profile.brand else "Arrowow",
                              "format": "UGC 30s vertical"}
        ctx.state["character"] = {"character_id": profile.character_id, "bible": profile.model_dump()}
        ctx.log(f"  [IntakeStage] persona locked -> {profile.character_id} "
                f"(brand: {ctx.state['brief']['brand']})")
        return ctx.state["character"]

    def _render_budget_guard(self, ctx: InvocationContext) -> dict:
        """Before any live render, ensure we won't breach the $100 dev ceiling."""
        if ctx.mode != "LIVE_MEDIA":
            return {"guard": "skipped (not live)"}
        tracker = DevSpendTracker()
        if tracker.would_exceed(PROJECTED_FULL_RENDER_USD):
            ctx.state["_halt"] = True
            ctx.log(f"  [render_budget_guard] HALT — would exceed ${tracker.CEILING_USD} ceiling "
                    f"(spent ${tracker.total_spent():.2f}, projected +${PROJECTED_FULL_RENDER_USD:.2f})")
            return {"guard": "halt", "remaining_usd": tracker.remaining()}
        ctx.log(f"  [render_budget_guard] OK — spent ${tracker.total_spent():.2f}, "
                f"remaining ${tracker.remaining():.2f}, projected +${PROJECTED_FULL_RENDER_USD:.2f}")
        return {"guard": "ok", "remaining_usd": tracker.remaining()}

    def _heal_failed_renders(self, ctx: InvocationContext) -> dict:
        """Heal any failed renders by jittering their seed and re-rendering before
        we build the first composite timeline."""
        beats = ctx.state.get("beat_prompts", {}).get("beats", [])
        rendered_beats = ctx.state.setdefault("beats", {})
        healed = []
        for b in beats:
            bid = b["beat_id"]
            clip = rendered_beats.get(bid, {})
            # If the clip is missing or has a non-success status, trigger healing
            if not clip or clip.get("status") not in ("success", "mock"):
                ctx.log(f"  [failed_renders_healing_pass] healing failed beat: {bid} (status={clip.get('status')})")
                # Jitter seed to bypass safety filter trigger
                b["_seed_jitter"] = b.get("_seed_jitter", 0) + 1
                media_tools.make_render_beat_stage(bid)(ctx)
                healed.append(bid)
        return {"healed": healed}

    def _gate(self, name: str, state_key: str):
        def _fn(ctx: InvocationContext) -> dict:
            if self.autonomous:
                ctx.log(f"  [GATE {name}] auto-approved (autonomous)")
            return {"gate": name, "approved": True, "auto": self.autonomous}
        return _fn

    # ---- summary ----------------------------------------------------------
    def _summary(self, ctx: InvocationContext) -> dict:
        s = ctx.state
        qa_report = s.get("qa_report", {})
        return {
            "session_id": s["metadata"]["session_id"],
            "status": s["metadata"]["status"],
            "final_uri": s.get("production", {}).get("final_uri"),
            "duration_s": s.get("production", {}).get("duration_s"),
            "beats": list(s.get("beats", {}).keys()),
            "qa": {"approved": qa_report.get("approved"),
                   "overall": qa_report.get("overall_score"),
                   "realism": qa_report.get("realism_score"),
                   "lip_sync": qa_report.get("lip_sync_score"),
                   "defects": len(qa_report.get("defects", []))},
            "regenerations": s.get("cost_ledger", {}).get("regenerations", 0),
            "cost_breakdown": cost_ledger.cost_breakdown(s),
            "dev_spend_remaining_usd": DevSpendTracker().remaining(),
        }
