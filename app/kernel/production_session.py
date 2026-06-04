import os
import uuid
from .blackboard import Blackboard
from .state_validator import StateValidator
from .cost_ledger import CostLedger

class ProductionSession:
    def __init__(self, mode: str, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.session_dir = os.path.join("output", self.session_id)
        
        self.bb = Blackboard(self.session_dir)
        self.bb.state["metadata"]["session_id"] = self.session_id
        self.bb.state["metadata"]["mode"] = mode
        self.bb.save()
        
        self.validator = StateValidator()
        self.cost_ledger = CostLedger(self.bb)

    def is_valid(self) -> bool:
        return self.validator.validate(self.bb.state)
