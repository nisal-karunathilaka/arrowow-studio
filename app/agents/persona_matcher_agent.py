import os
import json
from typing import Dict, Any

class PersonaMatcherAgent:
    def __init__(self, vault_dir: str = "app/persona_vault"):
        self.vault_dir = vault_dir

    def resolve_persona(self, character_id: str) -> Dict[str, Any]:
        """
        Deterministically resolves the character ID to their vault profile.
        Does not use an LLM to prevent hallucination.
        """
        if not character_id:
            raise ValueError("character_id is required")
            
        profile_path = os.path.join(self.vault_dir, character_id, "profile.json")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Persona profile not found for {character_id} at {profile_path}")
            
        with open(profile_path, 'r') as f:
            persona_data = json.load(f)
            
        # Ensure the character is locked
        persona_data["locked"] = True
        return persona_data
