import json
from ..agents.mock_agent import MockGeminiAgent
from ..agents.live_agents import LiveVideoCritic
from ..providers.base import MockVideoProvider, MockAudioProvider
from ..providers.live_providers import GoogleTTSProvider, VeoVideoProvider

class ProductionPipeline:
    def __init__(self, blackboard, mode: str):
        self.bb = blackboard
        self.mode = mode
        
        if self.mode == "LIVE_MEDIA":
            self.video_provider = VeoVideoProvider()
            self.audio_provider = GoogleTTSProvider()
            self.critic = LiveVideoCritic(self.bb)
        else:
            self.video_provider = MockVideoProvider()
            self.audio_provider = MockAudioProvider()
            self.critic = MockGeminiAgent("VideoCritic")

    def run(self) -> bool:
        script_data = self.bb.get("pre_production", {}).get("script", {})
        script = script_data.get("script_text", "") if isinstance(script_data, dict) else ""
        if not script:
            # Handle highly variable Gemini schema hallucinations for scenes/segments
            elements = []
            if isinstance(script_data, dict):
                elements = script_data.get("scenes")
                if not elements:
                    inner_script = script_data.get("script")
                    if isinstance(inner_script, dict):
                        elements = inner_script.get("segments") or inner_script.get("scenes")
                    elif isinstance(inner_script, list):
                        elements = inner_script
                if not elements:
                    elements = script_data.get("video_elements")
            elif isinstance(script_data, list):
                elements = script_data
                
            if not elements:
                elements = []
                
            if isinstance(elements, dict) and "segments" in elements:
                elements = elements["segments"]
                
            dialogues = []
            for scene in elements:
                if isinstance(scene, dict):
                    dlg = scene.get("dialogue") or scene.get("sienna_dialogue")
                    if not dlg and "audio" in scene and isinstance(scene["audio"], dict):
                        dlg = scene["audio"].get("dialogue") or scene["audio"].get("sienna_dialogue")
                        
                    if dlg:
                        dialogues.extend(dlg if isinstance(dlg, list) else [dlg])
            script = " ".join(dialogues)
            
        voice_id = self.bb.get("character", {}).get("voice_identity", {}).get("elevenlabs_voice_id", "")
        # Since we are using Google TTS instead of ElevenLabs, ensure it's a valid Google voice ID
        if not voice_id.startswith("en-"):
            voice_id = "en-AU-Neural2-A"
            
        image_anchor = self.bb.get("static_frame", {}).get("asset_uri", "")
        
        # Use visual plan prompts for Veo Video generation
        visual_plan_data = self.bb.get("visual_plan", {}).get("static_frame_prompt", {})
        if isinstance(visual_plan_data, dict):
            prompt_a = visual_plan_data.get("static_frame_prompt", "")
            prompt_b = visual_plan_data.get("b_roll_prompt", "")
        else:
            prompt_a = str(visual_plan_data)
            prompt_b = prompt_a

        import re
        import os
        import subprocess
        from .cost_ledger import CostLedger
        ledger = CostLedger(self.bb)
        
        # Pure Text-to-Video A-Roll / B-Roll Sequence
        generated_videos = []
        GENERATION_SEED = 427819
        
        if script and self.mode == "LIVE_MEDIA":
            # Handle script if it's a dict
            script_str = ""
            if isinstance(script, dict):
                if "script_text" in script:
                    script_str = script["script_text"]
                elif "scenes" in script:
                    lines = []
                    for scene in script["scenes"]:
                        audio = scene.get("audio", {})
                        if isinstance(audio, dict) and "script" in audio:
                            lines.append(audio["script"])
                        elif isinstance(audio, str):
                            lines.append(audio)
                    script_str = " ".join(lines)
                else:
                    script_str = str(script)
            else:
                script_str = str(script)
                
            # Split script in half for A-Roll and B-Roll
            words = script_str.split()
            mid = len(words) // 2
            chunk_a = " ".join(words[:mid])
            chunk_b = " ".join(words[mid:])
            
            shots = [
                {"type": "A-Roll", "prompt": prompt_a, "dialogue": f"(Sienna: \"{chunk_a}\")"},
                {"type": "B-Roll", "prompt": prompt_b, "dialogue": f"(Voiceover: \"{chunk_b}\")"}
            ]
            
            for i, shot in enumerate(shots):
                if not shot["prompt"]:
                    shot["prompt"] = "A highly detailed cinematic shot of Sienna."
                
                final_prompt = (
                    f"{shot['prompt']}\n\n"
                    f"Strictly no captions, no subtitles, clear on-screen visual field.\n"
                    f"Audio Constraints: The speaker has a clear, energetic 25-year-old female voice with a strict native Australian female accent. They speak at a steady, calm tempo. No background music.\n"
                    f"{shot['dialogue']}"
                )
                
                print(f"[Production] Generating {shot['type']}...")
                
                chunk_video_uri = ""
                max_retries = 3
                
                # Apply Seed Locking only to the A-Roll (talking head). 
                # Applying the same seed to a radically different composition (B-Roll action shot) 
                # causes the Veo latent space to warp and melt the subject.
                current_seed = GENERATION_SEED if shot['type'] == "A-Roll" else None
                
                for attempt in range(max_retries):
                    video_res = self.video_provider.generate_video(
                        prompt=final_prompt, 
                        reference_image=None,  # Pure Text-to-Video ensures pristine physics
                        output_dir=self.bb.session_dir,
                        seed=current_seed
                    )
                    ledger.add_video_generation()
                    
                    chunk_video_uri = video_res.get("uri", "") if isinstance(video_res, dict) else ""
                    if chunk_video_uri:
                        break
                    else:
                        print(f"[Production] Attempt {attempt+1}/{max_retries} failed. Retrying...")
                
                if not chunk_video_uri:
                    print(f"[Production] Failed to generate {shot['type']} after {max_retries} attempts.")
                    break
                generated_videos.append(chunk_video_uri)

        video_uri = ""
        if len(generated_videos) == 1:
            video_uri = generated_videos[0]
        elif len(generated_videos) > 1:
            print("[Production] Concatenating Frames-to-Video sequence...")
            concat_list = os.path.join(self.bb.session_dir, "concat.txt")
            with open(concat_list, "w") as f:
                for v in generated_videos:
                    # ffmpeg concat demuxer needs absolute paths.
                    f.write(f"file '{os.path.abspath(v)}'\n")
            
            final_concat = os.path.join(self.bb.session_dir, "final_concatenated.mp4")
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list, "-c", "copy", final_concat
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(final_concat):
                video_uri = final_concat
            else:
                video_uri = generated_videos[0] # Fallback
                
        audio_uri = "" # Handled natively by Veo 3.1
        synced_video_uri = video_uri

        print("[Production] Running Video Critic...")
        if self.mode == "LIVE_MEDIA":
            report = self.critic.generate(synced_video_uri)
        else:
            report = self.critic.generate("Critique video")
            
        print(f"[Production] Critic Report: {report}")
        
        state = {
            "model_route": "mock_direct_dialogue",
            "generated_video_uri": video_uri,
            "generated_audio_uri": audio_uri,
            "synced_video_uri": synced_video_uri,
            "video_critic_report": report
        }
        
        self.bb.update("production", state)
        self.bb.state["metadata"]["status"] = "production_complete"
        self.bb.save()
        return report.get("approved", False)
