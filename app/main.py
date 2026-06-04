import argparse
import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add app directory to path so we can run from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kernel.production_session import ProductionSession
from app.kernel.approval_gate import ApprovalGate
from app.agents.intake_agent import IntakeAgent
from app.agents.pre_production import PreProductionPipeline
from app.agents.visual_planning import VisualPlanningPipeline
from app.kernel.static_frame_stage import StaticFramePipeline
from app.kernel.production_stage import ProductionPipeline

def main():
    parser = argparse.ArgumentParser(description="Arrowow Local Production Kernel")
    parser.add_argument("--mode", type=str, default="DRY_RUN", choices=["DRY_RUN", "LLM_ONLY", "LIVE_MEDIA"])
    parser.add_argument("--brief", type=str, required=True)
    args = parser.parse_args()

    print(f"Starting Production Kernel in {args.mode} mode...")
    session = ProductionSession(mode=args.mode)
    print(f"Session ID: {session.session_id}")
    
    if not os.path.exists(args.brief):
        print(f"Brief file not found: {args.brief}")
        return
        
    with open(args.brief, 'r') as f:
        brief_data = json.load(f)
        
    # Phase A: Intake & Matcher
    intake = IntakeAgent(session.bb)
    if not intake.run(brief_data):
        print("Intake failed.")
        return
        
    choice = ApprovalGate.prompt("GATE 0 (Intake)", f"Character resolved: {session.bb.state['character'].get('character_id')}")
    if choice != 'Y': return

    # Phase B: Pre Production
    pre_prod = PreProductionPipeline(session.bb, args.mode)
    if not pre_prod.run():
        print("Pre-Production failed validation.")
        return
        
    # Try to get script_text, or reconstruct from scenes if missing
    script_data = session.bb.state['pre_production']['script']
    script_text = script_data.get('script_text')
    
    if not script_text:
        # It could be 'scenes', 'script', or 'video_elements'
        elements = script_data.get('scenes') or script_data.get('script') or script_data.get('video_elements') or []
        dialogues = []
        for scene in elements:
            if isinstance(scene, dict) and 'dialogue' in scene:
                dialogues.extend(scene['dialogue'] if isinstance(scene['dialogue'], list) else [scene['dialogue']])
        script_text = " ".join(dialogues)
        
    choice = ApprovalGate.prompt("GATE 1 (Story & Script)", f"Script Generated:\n{script_text}")
    if choice != 'Y': return
    
    # Phase C: Visual Planning
    vis_plan = VisualPlanningPipeline(session.bb, args.mode)
    if not vis_plan.run():
        print("Visual Planning failed.")
        return
        
    prompt_data = session.bb.state['visual_plan']['static_frame_prompt']
    prompt_text = prompt_data.get('static_frame_prompt') or prompt_data.get('prompt') or prompt_data.get('image_generation_prompt') or prompt_data.get('image_prompt') or prompt_data.get('visual_prompt') or ""
    choice = ApprovalGate.prompt("GATE 2A (Visual Plan)", f"Visual Prompt Generated:\n{prompt_text}")
    if choice != 'Y': return
    
    # Phase D: Static Frame Generation
    static_frame = StaticFramePipeline(session.bb, args.mode)
    if not static_frame.run():
        print("Static Frame failed validation.")
        return
        
    asset_uri = session.bb.state['static_frame'].get('asset_uri')
    choice = ApprovalGate.prompt("GATE 2B (Static Frame)", f"Static Frame Asset Generated at:\n{asset_uri}")
    if choice != 'Y': return
    
    # Phase E: Production (Video/Audio)
    prod = ProductionPipeline(session.bb, args.mode)
    if not prod.run():
        print("Final Production QA failed.")
        return
        
    session.bb.state["metadata"]["status"] = "complete"
    session.bb.save()
    print("\n" + "="*50)
    print("✅ ARROWOW PIPELINE COMPLETE")
    print(f"Artifacts saved in: {session.session_dir}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
