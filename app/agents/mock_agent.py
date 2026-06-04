import json
from typing import Dict, Any

class MockGeminiAgent:
    """
    A mock class for the LLM agents to support DRY_RUN mode.
    In LIVE_MEDIA or LLM_ONLY, this would be replaced by google.antigravity.Agent
    """
    def __init__(self, role: str):
        self.role = role

    def generate(self, prompt: str, schema: dict = None) -> Any:
        if self.role == "CreativeStrategist":
            return {
                "hook": "Sienna adjusting her hair, looking breathless.",
                "angle": "Tough love motivation with product placement.",
                "cta": "Get after it today."
            }
        elif self.role == "Scriptwriter":
            return {
                "script_text": "Alright team, quick reality check. If your leggings aren't squat-proof, what are we even doing? Let's get after it today.",
                "estimated_duration_seconds": 8
            }
        elif self.role == "TextCritic":
            return {
                "approved": True,
                "feedback": "Perfectly matches Sienna's tone and constraints.",
                "brand_safety_score": 1.0
            }
        elif self.role == "StoryboardDirector":
            return {
                "scenes": [
                    {
                        "scene": 1,
                        "action": "Sienna adjusts ponytail, squats to show leggings, talks to camera.",
                        "camera": "Selfie style, eye level."
                    }
                ]
            }
        elif self.role == "WardrobeLocation":
            return {
                "wardrobe": "Sage green seamless activewear set, white chunky shoes.",
                "location": "Brightly lit modern gym."
            }
        elif self.role == "ShotPromptEngineer":
            return {
                "static_frame_prompt": "A photorealistic portrait of an athletic 26-year-old Australian blonde woman with sun-kissed skin and bright blue eyes. She has messy blonde hair in a claw clip. She is wearing a sage green seamless activewear set. Brightly lit modern gym background. Direct front-facing view, neutral but energetic expression. UGC phone camera style, high quality."
            }
        elif self.role == "ImageCritic":
            return {
                "approved": True,
                "feedback": "Image geometry matches reference anchor perfectly.",
                "fidelity_score": 0.95
            }
        elif self.role == "VideoCritic":
            return {
                "approved": True,
                "feedback": "Motion is smooth, lip sync is accurate.",
                "artifact_risk": "low"
            }
        return {}
