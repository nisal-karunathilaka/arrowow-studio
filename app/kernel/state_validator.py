import json
import jsonschema
import os

class StateValidator:
    def __init__(self, schema_path: str = "schemas/session_state.schema.json"):
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)

    def validate(self, state: dict) -> bool:
        try:
            jsonschema.validate(instance=state, schema=self.schema)
            return True
        except jsonschema.exceptions.ValidationError as e:
            print(f"[StateValidator] Error: {e.message}")
            return False
