import json
from .mock_agent import MockGeminiAgent
from .live_agents import LiveCreativeStrategist, LiveScriptwriter, LiveTextCritic

class PreProductionPipeline:
    def __init__(self, blackboard, mode: str):
        self.bb = blackboard
        self.mode = mode
        
        if self.mode in ["LIVE_MEDIA", "LLM_ONLY"]:
            self.strategist = LiveCreativeStrategist(self.bb)
            self.scriptwriter = LiveScriptwriter(self.bb)
            self.text_critic = LiveTextCritic(self.bb)
        else:
            self.strategist = MockGeminiAgent("CreativeStrategist")
            self.scriptwriter = MockGeminiAgent("Scriptwriter")
            self.text_critic = MockGeminiAgent("TextCritic")

    def run(self) -> bool:
        """
        Executes Strategy -> Script -> QA, with up to 3 retries if the QA Critic rejects the script.
        """
        brief = self.bb.get("brief", {})
        persona = self.bb.get("character", {})
        
        strategy = None
        script = None
        critic_report = None
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            print(f"[PreProduction] Running Creative Strategist (Attempt {attempt}/{max_attempts})...")
            strategy_input = dict(brief)
            if critic_report and not critic_report.get("approved", False):
                strategy_input["previous_qa_feedback"] = critic_report.get("feedback")
            strategy = self.strategist.generate(strategy_input, persona)
            
            print(f"[PreProduction] Running Scriptwriter (Attempt {attempt}/{max_attempts})...")
            script_strategy_input = dict(strategy)
            if critic_report and not critic_report.get("approved", False):
                script_strategy_input["previous_qa_feedback"] = critic_report.get("feedback")
            script = self.scriptwriter.generate(script_strategy_input, persona)
            
            print(f"[PreProduction] Running Text Critic (Attempt {attempt}/{max_attempts})...")
            critic_report = self.text_critic.generate(script, persona)
            
            if critic_report.get("approved", False):
                print(f"[PreProduction] Approved on Attempt {attempt}!")
                break
            else:
                print(f"[PreProduction] Rejected on Attempt {attempt}. Feedback: {critic_report.get('feedback')}")
        
        pre_prod_state = {
            "strategy": strategy,
            "script": script,
            "text_critic_report": critic_report,
            "approval_gate_1": {"status": "pending"}
        }
        
        self.bb.update("pre_production", pre_prod_state)
        self.bb.state["metadata"]["status"] = "pre_production_complete"
        self.bb.save()
        
        return critic_report.get("approved", False)
