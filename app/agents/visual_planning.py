import json
from .mock_agent import MockGeminiAgent
from .live_agents import LiveStoryboardDirector, LiveWardrobeLocation, LiveShotPromptEngineer

class VisualPlanningPipeline:
    def __init__(self, blackboard, mode: str):
        self.bb = blackboard
        self.mode = mode
        
        if self.mode in ["LIVE_MEDIA", "LLM_ONLY"]:
            self.storyboard_dir = LiveStoryboardDirector(self.bb)
            self.wardrobe = LiveWardrobeLocation(self.bb)
            self.prompt_eng = LiveShotPromptEngineer(self.bb)
        else:
            self.storyboard_dir = MockGeminiAgent("StoryboardDirector")
            self.wardrobe = MockGeminiAgent("WardrobeLocation")
            self.prompt_eng = MockGeminiAgent("ShotPromptEngineer")

    def run(self) -> bool:
        script = self.bb.get("pre_production", {}).get("script", {})
        persona = self.bb.get("character", {})
        
        print("[VisualPlanning] Generating Storyboard...")
        storyboard = None
        for attempt in range(3):
            try:
                storyboard = self.storyboard_dir.generate(script)
                break
            except ValueError:
                print(f"[VisualPlanning] Storyboard generation failed attempt {attempt+1}/3. Retrying...")
        if not storyboard: raise ValueError("Storyboard generation failed after 3 attempts.")
        
        print("[VisualPlanning] Generating Wardrobe & Location...")
        wl = None
        for attempt in range(3):
            try:
                wl = self.wardrobe.generate(persona)
                break
            except ValueError:
                print(f"[VisualPlanning] Wardrobe generation failed attempt {attempt+1}/3. Retrying...")
        if not wl: raise ValueError("Wardrobe generation failed after 3 attempts.")
        
        print("[VisualPlanning] Generating Prompts...")
        prompts = None
        for attempt in range(3):
            try:
                prompts = self.prompt_eng.generate(storyboard, wl)
                break
            except ValueError as e:
                print(f"[VisualPlanning] Prompt generation failed attempt {attempt+1}/3. Retrying...")
        if not prompts: raise ValueError("Prompt generation failed after 3 attempts.")
        
        plan = {
            "storyboard": storyboard,
            "wardrobe_location": wl,
            "static_frame_prompt": prompts,
            "approval_gate_2a": {"status": "pending"}
        }
        
        self.bb.update("visual_plan", plan)
        self.bb.state["metadata"]["status"] = "visual_planning_complete"
        self.bb.save()
        return True
