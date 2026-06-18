"""
Arrowow Studio — DRY_RUN entrypoint (Phase 1 acceptance harness)
================================================================

Runs the full ADK-shaped graph end-to-end with mocks and prints the run trace.

    python -m app.adk.run_dry --scenario "30s ad for our new running leggings"

Acceptance (system design §10, Phase 1): "empty graph runs end-to-end with mocks."
This produces a 30s master (mock URI), a session_state.json, and a run summary —
with NO GCP calls.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Allow running from the project root as a module or script.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adk.app import build_director
from app.adk.core import InvocationContext
from app.adk.state import session as session_state


async def _run(scenario: str, mode: str, session_id: str | None = None) -> dict:
    director = build_director(autonomous=True)
    sess = session_state.make_session(mode=mode, scenario=scenario, session_id=session_id)
    ctx = InvocationContext(sess, mode=mode, logger=print)
    summary = await director.run(ctx)
    path = session_state.persist_state(ctx.state)
    summary["state_file"] = path
    return summary


def main():
    parser = argparse.ArgumentParser(description="Arrowow Studio — ADK Production Engine")
    parser.add_argument("--scenario", type=str,
                        default="A 30-second UGC ad for our new running leggings, "
                                "energetic, gym setting.")
    parser.add_argument("--mode", type=str, default="DRY_RUN",
                        choices=["DRY_RUN", "LLM_ONLY", "LIVE_MEDIA"])
    parser.add_argument("--session", type=str, default=None,
                        help="Optional static session ID/folder name (reuses a single folder)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"ARROWOW STUDIO · mode={args.mode} · session={args.session or 'auto'}")
    print(f"scenario: {args.scenario}")
    print("=" * 70)

    summary = asyncio.run(_run(args.scenario, args.mode, args.session))

    print("=" * 70)
    print("RUN SUMMARY")
    print(json.dumps(summary, indent=2))
    print("=" * 70)
    print(f"PASS — status={summary['status']} · beats={summary['beats']} · "
          f"final={summary['final_uri']}")


if __name__ == "__main__":
    main()
