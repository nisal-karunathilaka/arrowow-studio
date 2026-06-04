import json
from ..agents.mock_agent import MockGeminiAgent
from ..agents.live_agents import LiveTextCritic
from ..providers.base import MockImageProvider
from ..providers.live_providers import ImagenProvider

class StaticFramePipeline:
    def __init__(self, blackboard, mode: str):
        self.bb = blackboard
        self.mode = mode
        
        if self.mode == "LIVE_MEDIA":
            self.provider = ImagenProvider()
            self.critic = LiveTextCritic() # We use TextCritic class structurally, but it should be an ImageCritic. Let's stick to mock critic for image for now, or use Gemini 1.5 Pro multimodal.
        else:
            self.provider = MockImageProvider()
        
        self.critic = MockGeminiAgent("ImageCritic") # Keeping image critic mocked for MVP safety

    def run(self) -> bool:
        visual_plan_prompt = self.bb.get("visual_plan", {}).get("static_frame_prompt", {})
        prompt = ""
        if isinstance(visual_plan_prompt, str):
            prompt = visual_plan_prompt
        elif isinstance(visual_plan_prompt, dict):
            prompt = (visual_plan_prompt.get("static_frame_prompt") or 
                      visual_plan_prompt.get("prompt") or 
                      visual_plan_prompt.get("image_generation_prompt") or 
                      visual_plan_prompt.get("image_prompt") or 
                      visual_plan_prompt.get("visual_prompt") or "")
        
        if not prompt:
            script_data = self.bb.get("pre_production", {}).get("script", {})
            prompt = script_data.get("script_text", "A high quality cinematic portrait of a fitness influencer in a modern gym.")
        anchor = self.bb.get("character", {}).get("visual_identity", {}).get("latent_anchor_urls", [""])[0]
        
        result = self.provider.generate_image(prompt, anchor, output_dir=self.bb.session_dir)
        
        from .cost_ledger import CostLedger
        CostLedger(self.bb).add_image_generation()
        
        print("[StaticFrame] Running Image Critic...")
        report = self.critic.generate("Critique image against anchor")
        
        state = {
            "prompt": prompt,
            "provider": "mock" if self.mode == "DRY_RUN" else "live",
            "asset_uri": result["uri"],
            "image_critic_report": report,
            "approval_gate_2b": {"status": "pending"}
        }
        
        self.bb.update("static_frame", state)
        self.bb.state["metadata"]["status"] = "static_frame_complete"
        self.bb.save()
        return report.get("approved", False)
