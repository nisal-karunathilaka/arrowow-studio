import json
import os
import uuid
from typing import Any, Dict

class Blackboard:
    def __init__(self, session_dir: str):
        self.session_dir = session_dir
        self.state_file = os.path.join(session_dir, "session_state.json")
        self.state: Dict[str, Any] = self._initialize_state()

    def _initialize_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "metadata": {
                "session_id": str(uuid.uuid4()),
                "mode": "DRY_RUN",
                "status": "intake",
                "current_stage": "initialized"
            },
            "brief": {},
            "character": {},
            "pre_production": {},
            "visual_plan": {},
            "static_frame": {},
            "production": {},
            "post_production": {},
            "cost_ledger": {
                "estimated_input_tokens": 0,
                "estimated_output_tokens": 0,
                "image_generations": 0,
                "video_generations": 0,
                "regenerations": 0,
                "budget_status": "within_limit"
            },
            "errors": []
        }

    def save(self):
        os.makedirs(self.session_dir, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def update(self, key: str, value: Any):
        self.state[key] = value
        self.save()
        
    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)
