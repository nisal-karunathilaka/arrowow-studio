"""
Arrowow Studio — Cost Accounting (PriceBook · CostLedger · DevSpendTracker)
==========================================================================

Three responsibilities, cleanly separated:

  • PriceBook        — the configured 2026 unit rates for every billable model.
  • CostLedger       — per-RUN accounting: records each API call (units × rate = USD),
                       writes cost_log.jsonl + cost_breakdown.json, evaluates the run budget.
  • DevSpendTracker  — cumulative CROSS-run spend vs the $100 development ceiling, with a
                       hard guard that blocks live calls that would breach it.

Every live call is logged with ACTUAL units and computed USD, so the run output carries
real numbers (system requirement: "actual cost per each try, log properly").

⚠️ Rates are configured estimates — verify against the GCP billing console. Cost is
computed as units × rate because the generation APIs do not return a price field.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# PriceBook — configured USD rates (VERIFY against billing)
# ---------------------------------------------------------------------------
class PriceBook:
    LLM = {  # per 1M tokens
        "gemini-3.5-flash":       {"in": 0.075, "out": 0.30},
        "gemini-3.1-flash":       {"in": 0.075, "out": 0.30},
        "gemini-3.1-pro":         {"in": 1.25,  "out": 5.00},
        "gemini-3.1-pro-preview": {"in": 1.25,  "out": 5.00},
    }
    VIDEO = {"veo-3.1-generate-001": 0.15, "veo-3.1": 0.15}   # per second
    IMAGE = {"gemini-3.1-flash-image": 0.04, "imagen": 0.04}  # per image
    TTS = {"cloud-tts-neural2": 0.000016}                     # per character

    @classmethod
    def llm_cost(cls, model: str, in_tok: int, out_tok: int) -> float:
        r = cls.LLM.get(model, {"in": 0.10, "out": 0.40})
        return (in_tok / 1_000_000) * r["in"] + (out_tok / 1_000_000) * r["out"]

    @classmethod
    def video_cost(cls, model: str, seconds: float) -> float:
        return seconds * cls.VIDEO.get(model, 0.15)

    @classmethod
    def image_cost(cls, model: str, n: int = 1) -> float:
        return n * cls.IMAGE.get(model, 0.04)

    @classmethod
    def tts_cost(cls, chars: int) -> float:
        return chars * cls.TTS["cloud-tts-neural2"]


def new_ledger() -> dict:
    """Fresh per-run ledger structure (stored under state['cost_ledger'])."""
    return {
        "calls": [],            # one record per billable API call
        "total_usd": 0.0,
        "estimated_input_tokens": 0,
        "estimated_output_tokens": 0,
        "image_generations": 0,
        "video_generations": 0,
        "video_seconds": 0,
        "tts_characters": 0,
        "regenerations": 0,
        "budget_status": "within_limit",
    }


# ---------------------------------------------------------------------------
# CostLedger — per-run accounting (wraps the session-state ledger dict)
# ---------------------------------------------------------------------------
class CostLedger:
    """Records each billable call against the run's state['cost_ledger']."""

    def __init__(self, state: dict):
        self.state = state
        if "cost_ledger" not in state or "calls" not in state["cost_ledger"]:
            state["cost_ledger"] = new_ledger()
        self.led = state["cost_ledger"]

    def _add_call(self, kind: str, model: str, units: float, unit_label: str,
                  cost: float, live: bool) -> float:
        self.led["calls"].append({
            "ts": round(time.time(), 3), "kind": kind, "model": model,
            "units": units, "unit": unit_label, "cost_usd": round(cost, 6), "live": live,
        })
        self.led["total_usd"] = round(self.led["total_usd"] + cost, 6)
        return cost

    def record_llm(self, model: str, in_tok: int, out_tok: int, live: bool = True) -> float:
        self.led["estimated_input_tokens"] += in_tok
        self.led["estimated_output_tokens"] += out_tok
        cost = PriceBook.llm_cost(model, in_tok, out_tok) if live else 0.0
        return self._add_call("llm", model, in_tok + out_tok, "tokens", cost, live)

    def record_video(self, model: str, seconds: float, live: bool = True) -> float:
        self.led["video_generations"] += 1
        self.led["video_seconds"] += seconds
        cost = PriceBook.video_cost(model, seconds) if live else 0.0
        return self._add_call("video", model, seconds, "seconds", cost, live)

    def record_image(self, model: str, n: int = 1, live: bool = True) -> float:
        self.led["image_generations"] += n
        cost = PriceBook.image_cost(model, n) if live else 0.0
        return self._add_call("image", model, n, "images", cost, live)

    def record_tts(self, chars: int, model: str = "cloud-tts-neural2", live: bool = True) -> float:
        self.led["tts_characters"] += chars
        cost = PriceBook.tts_cost(chars) if live else 0.0
        return self._add_call("tts", model, chars, "chars", cost, live)

    @property
    def total_usd(self) -> float:
        return self.led["total_usd"]

    def write_logs(self, session_dir: str) -> None:
        os.makedirs(session_dir, exist_ok=True)
        with open(os.path.join(session_dir, "cost_log.jsonl"), "w") as f:
            for c in self.led["calls"]:
                f.write(json.dumps(c) + "\n")
        with open(os.path.join(session_dir, "cost_breakdown.json"), "w") as f:
            json.dump(cost_breakdown(self.state), f, indent=2)


# ---------------------------------------------------------------------------
# Per-run budget guard (kept dict-based for the orchestrator + selftest)
# ---------------------------------------------------------------------------
MAX_VIDEO_SECONDS_PER_RUN = 60        # 5 beats x 8s + headroom for one regen
MAX_USD_PER_RUN = 12.0                # ~2 full renders worth, hard run ceiling


def evaluate_budget(ledger: dict) -> str:
    seconds = ledger.get("video_seconds", 0)
    usd = ledger.get("total_usd", 0.0)
    if seconds > MAX_VIDEO_SECONDS_PER_RUN or usd > MAX_USD_PER_RUN:
        status = "exceeded"
    elif seconds >= MAX_VIDEO_SECONDS_PER_RUN - 8 or usd >= MAX_USD_PER_RUN * 0.8:
        status = "warning"
    else:
        status = "within_limit"
    ledger["budget_status"] = status
    return status


def cost_breakdown(state: dict) -> dict:
    led = state.get("cost_ledger", {})
    return {
        "session_id": state.get("metadata", {}).get("session_id"),
        "mode": state.get("metadata", {}).get("mode"),
        "total_estimated_cost_usd": round(led.get("total_usd", 0.0), 4),
        "calls": len(led.get("calls", [])),
        "tokens": {"in": led.get("estimated_input_tokens", 0),
                   "out": led.get("estimated_output_tokens", 0)},
        "video_seconds": led.get("video_seconds", 0),
        "images": led.get("image_generations", 0),
        "tts_chars": led.get("tts_characters", 0),
        "regenerations": led.get("regenerations", 0),
        "budget_status": led.get("budget_status", "within_limit"),
    }


# ---------------------------------------------------------------------------
# DevSpendTracker — cumulative spend vs the $100 development ceiling
# ---------------------------------------------------------------------------
class DevSpendTracker:
    """Persists cumulative live spend across all runs to output/_dev_spend_ledger.json
    and guards the hard $100 development budget."""

    CEILING_USD = 100.0
    PATH = os.path.join("output", "_dev_spend_ledger.json")

    def _load(self) -> dict:
        if os.path.exists(self.PATH):
            with open(self.PATH) as f:
                return json.load(f)
        return {"ceiling_usd": self.CEILING_USD, "total_spent_usd": 0.0, "runs": []}

    def total_spent(self) -> float:
        return self._load().get("total_spent_usd", 0.0)

    def remaining(self) -> float:
        return round(self.CEILING_USD - self.total_spent(), 4)

    def would_exceed(self, projected_usd: float) -> bool:
        return (self.total_spent() + projected_usd) > self.CEILING_USD

    def record_run(self, session_id: str, usd: float, mode: str) -> float:
        data = self._load()
        if usd > 0:
            data["total_spent_usd"] = round(data.get("total_spent_usd", 0.0) + usd, 6)
            data["runs"].append({"session_id": session_id, "usd": round(usd, 6),
                                 "mode": mode, "ts": round(time.time(), 3)})
            os.makedirs(os.path.dirname(self.PATH), exist_ok=True)
            with open(self.PATH, "w") as f:
                json.dump(data, f, indent=2)
        return data["total_spent_usd"]
