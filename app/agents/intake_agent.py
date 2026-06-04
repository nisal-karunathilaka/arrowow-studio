import json
from typing import Dict, Any

class IntakeAgent:
    def __init__(self, blackboard):
        self.bb = blackboard

    def run(self, raw_brief: dict):
        """
        Normalizes the intake brief and attempts to resolve the persona.
        """
        character_id = raw_brief.get("character_id", "sienna_fitness_01") # Defaulting for MVP
        
        # Load into blackboard
        self.bb.update("brief", raw_brief)
        
        from .persona_matcher_agent import PersonaMatcherAgent
        matcher = PersonaMatcherAgent()
        
        try:
            persona_data = matcher.resolve_persona(character_id)
            self.bb.update("character", persona_data)
            self.bb.state["metadata"]["status"] = "intake_complete"
            self.bb.save()
            return True
        except Exception as e:
            self.bb.state["errors"].append(str(e))
            self.bb.state["metadata"]["status"] = "failed"
            self.bb.save()
            return False
