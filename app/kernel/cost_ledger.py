import os
import json

class CostLedger:
    def __init__(self, blackboard):
        self.bb = blackboard
        self.ledger = self.bb.get("cost_ledger")
        
        # Ensure new fields exist for legacy files
        if "tts_characters" not in self.ledger:
            self.ledger["tts_characters"] = 0
            
    def add_tokens(self, input_tokens: int, output_tokens: int):
        self.ledger["estimated_input_tokens"] += input_tokens
        self.ledger["estimated_output_tokens"] += output_tokens
        self._update_status()

    def add_image_generation(self):
        self.ledger["image_generations"] += 1
        self._update_status()

    def add_video_generation(self):
        self.ledger["video_generations"] += 1
        self._update_status()
        
    def add_tts_generation(self, character_count: int):
        self.ledger["tts_characters"] += character_count
        self._update_status()

    def _update_status(self):
        # Basic budget rule: max 2 video gens, max 5 image gens, max 100k tokens
        if self.ledger["video_generations"] > 2 or self.ledger["estimated_input_tokens"] > 100000:
            self.ledger["budget_status"] = "exceeded"
        elif self.ledger["video_generations"] == 2 or self.ledger["estimated_input_tokens"] > 80000:
            self.ledger["budget_status"] = "warning"
        else:
            self.ledger["budget_status"] = "within_limit"
        self.bb.update("cost_ledger", self.ledger)
        self.save_cost_breakdown()

    def save_cost_breakdown(self):
        mode = self.bb.get("metadata", {}).get("mode", "DRY_RUN")
        session_id = self.bb.get("metadata", {}).get("session_id", "unknown")
        
        # Define unit prices (in USD)
        is_live = (mode == "LIVE_MEDIA")
        
        # Gemini 2.0 Flash is Free on Google AI Studio
        gemini_price = 0.0 
        
        # Vertex AI Imagen 3 pricing: $0.03 per image
        imagen_price = 0.03 if is_live else 0.0
        
        # Vertex AI Cloud TTS Journey Voice pricing: $0.000016 per char
        tts_price = 0.000016 if is_live else 0.0
        
        # Vertex AI Veo 2.0 pricing: $0.07 per 5-second video
        veo_price = 0.07 if is_live else 0.0
        
        # Calculate totals
        gemini_cost = 0.0
        imagen_cost = self.ledger["image_generations"] * imagen_price
        tts_cost = self.ledger["tts_characters"] * tts_price
        veo_cost = self.ledger["video_generations"] * veo_price
        
        total_cost = gemini_cost + imagen_cost + tts_cost + veo_cost
        
        breakdown = {
            "session_id": session_id,
            "mode": mode,
            "billing_type": "GCP Free Trial ($300)" if is_live else "Simulation (DRY_RUN)",
            "itemized_costs": {
                "gemini_llm_tokens": {
                    "input_tokens": self.ledger["estimated_input_tokens"],
                    "output_tokens": self.ledger["estimated_output_tokens"],
                    "unit_price_per_1k_usd": gemini_price,
                    "cost_usd": gemini_cost
                },
                "imagen3_image_generation": {
                    "count": self.ledger["image_generations"],
                    "unit_price_usd": imagen_price,
                    "cost_usd": imagen_cost
                },
                "google_tts_voiceover": {
                    "characters": self.ledger["tts_characters"],
                    "unit_price_per_char_usd": tts_price,
                    "cost_usd": tts_cost
                },
                "veo_video_generation": {
                    "count": self.ledger["video_generations"],
                    "unit_price_usd": veo_price,
                    "cost_usd": veo_cost
                }
            },
            "total_estimated_cost_usd": total_cost,
            "budget_status": self.ledger["budget_status"]
        }
        
        breakdown_file = os.path.join(self.bb.session_dir, "cost_breakdown.json")
        os.makedirs(self.bb.session_dir, exist_ok=True)
        with open(breakdown_file, "w") as f:
            json.dump(breakdown, f, indent=2)
