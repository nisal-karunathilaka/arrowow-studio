import os
import json
import uuid
from google.cloud import texttospeech
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

# Setup Google Cloud Authentication
cred_path = os.path.join(os.getcwd(), "google-credentials.json")
if os.path.exists(cred_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    
    # Initialize Vertex AI automatically with the project ID from the JSON
    with open(cred_path, "r") as f:
        creds = json.load(f)
        project_id = creds.get("project_id")
        if project_id:
            vertexai.init(project=project_id, location="us-central1")

class ImagenProvider:
    def generate_image(self, prompt: str, reference_image: str, output_dir: str = None) -> dict:
        print(f"[ImagenProvider] Generating image with Gemini 3.1 Flash Image...")
        try:
            from google import genai
            import json
            
            cred_path = os.path.join(os.getcwd(), "google-credentials.json")
            with open(cred_path, "r") as f:
                creds = json.load(f)
                project_id = creds.get("project_id")
                
            client = genai.Client(vertexai=True, project=project_id, location="global")
            
            response = client.models.generate_content(
                model="gemini-3.1-flash-image",
                contents=prompt
            )
            
            target_dir = output_dir or os.path.join(os.getcwd(), "output")
            os.makedirs(target_dir, exist_ok=True)
            output_path = os.path.join(target_dir, f"sienna_frame_{uuid.uuid4().hex[:6]}.png")
            
            # Extract image bytes from inline data
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    with open(output_path, "wb") as f:
                        f.write(part.inline_data.data)
                    break
                    
            return {"uri": output_path, "status": "success"}
        except Exception as e:
            print(f"[ImagenProvider] Error: {e}")
            return {"uri": "error.png", "status": "failed"}

class GoogleTTSProvider:
    def generate_audio(self, text: str, voice_id: str = "en-US-Journey-F", output_dir: str = None) -> dict:
        print(f"[GoogleTTSProvider] Generating audio with voice {voice_id}...")
        try:
            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Parse language code from voice_id (e.g. en-AU-Neural2-A -> en-AU)
            lang_code = "-".join(voice_id.split("-")[:2]) if "-" in voice_id else "en-US"
            voice = texttospeech.VoiceSelectionParams(
                language_code=lang_code,
                name=voice_id
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            
            target_dir = output_dir or os.path.join(os.getcwd(), "output")
            os.makedirs(target_dir, exist_ok=True)
            output_path = os.path.join(target_dir, f"voiceover_{uuid.uuid4().hex[:6]}.mp3")
            
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
                
            return {"uri": output_path, "status": "success"}
        except Exception as e:
            print(f"[GoogleTTSProvider] Error: {e}")
            return {"uri": "error.mp3", "status": "failed"}

class VeoVideoProvider:
    def generate_video(self, prompt: str, reference_image: str = None, output_dir: str = None, seed: int = None) -> dict:
        print("[VeoVideoProvider] Generating video using Veo 3.1...")
        try:
            from google import genai
            from google.genai import types
            from google.oauth2 import service_account
            from google.cloud import storage
            import time
            
            cred_path = os.path.join(os.getcwd(), "google-credentials.json")
            if not os.path.exists(cred_path):
                raise FileNotFoundError("google-credentials.json not found in root directory")
                
            with open(cred_path, "r") as f:
                creds = json.load(f)
                project_id = creds.get("project_id")
                
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            credentials = service_account.Credentials.from_service_account_file(
                cred_path, scopes=scopes
            )
            
            client = genai.Client(
                vertexai=True,
                project=project_id,
                location="us-central1",
                credentials=credentials
            )
            
            bucket_name = f"arrowow-videos-{project_id}"
            output_gcs_uri = f"gs://{bucket_name}/renders/"
            
            # Upload reference image to GCS if available (Image-to-Video consistency)
            input_gcs_uri = None
            if reference_image and os.path.exists(reference_image):
                print(f"[VeoVideoProvider] Uploading reference image {reference_image} to GCS...")
                storage_client = storage.Client(credentials=credentials, project=project_id)
                bucket = storage_client.bucket(bucket_name)
                blob_name = f"inputs/{os.path.basename(reference_image)}"
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(reference_image)
                input_gcs_uri = f"gs://{bucket_name}/{blob_name}"
                print(f"[VeoVideoProvider] Reference image uploaded: {input_gcs_uri}")
                
            print("[VeoVideoProvider] Requesting video from Veo...")
            
            config_params = {
                "output_gcs_uri": output_gcs_uri,
                "aspect_ratio": "16:9",
                "person_generation": "ALLOW_ADULT",
                "generate_audio": True,
                # Veo 3.1 caps at 8 seconds for BOTH Text-to-Video [4,6,8] and Image-to-Video [8]
                "duration_seconds": 8,
            }
            
            # Seed locking for character consistency
            if seed is not None:
                config_params["seed"] = seed

            if input_gcs_uri:
                config_params["reference_images"] = [
                    types.VideoGenerationReferenceImage(
                        image=types.Image(gcs_uri=input_gcs_uri, mime_type="image/png"),
                        reference_type="ASSET"
                    )
                ]
                
            # For Veo 3.1, if we are passing audio instructions in the prompt, we don't strictly need to pass an API parameter if the prompt is enough, but some versions of the SDK require generate_audio=True to enable the audio tracks. The google-genai package kwargs might support it. We'll pass it if the API supports it.
            # But the user's REST payload showed "generateAudio": True inside parameters.
            # We will just pass the prompt for now, as standard Veo 3.1 genai SDK implies audio generates from prompt.
                
            operation = client.models.generate_videos(
                model="veo-3.1-generate-001",
                prompt=prompt,
                config=types.GenerateVideosConfig(**config_params)
            )
            
            print(f"[VeoVideoProvider] Veo operation started: {operation.name}")
            print("Waiting for video rendering (takes 1-3 minutes)...")
            
            while not operation.done:
                print(".", end="", flush=True)
                time.sleep(10)
                operation = client.operations.get(operation)
                
            print("")
            if operation.error:
                raise Exception(f"Veo Server Error: {operation.error}")
                
            if not operation.response or not operation.response.generated_videos:
                raise Exception(f"Veo rejected the prompt or returned an empty response. Likely a safety filter trigger. Response: {operation.response}")
                
            generated_video = operation.response.generated_videos[0]
            gcs_path = generated_video.video.uri
            print(f"[VeoVideoProvider] Render successful! GCS URI: {gcs_path}")
            
            # Download the final video locally
            target_dir = output_dir or os.path.join(os.getcwd(), "output")
            os.makedirs(target_dir, exist_ok=True)
            output_path = os.path.join(target_dir, f"veo_final_{uuid.uuid4().hex[:6]}.mp4")
            
            print(f"[VeoVideoProvider] Downloading video to local path: {output_path}")
            storage_client = storage.Client(credentials=credentials, project=project_id)
            relative_path = gcs_path.replace(f"gs://{bucket_name}/", "")
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(relative_path)
            blob.download_to_filename(output_path)
            
            return {"uri": output_path, "status": "success"}
            
        except Exception as e:
            print(f"[VeoVideoProvider] Live video generation failed: {e}")
            return {"uri": "error.mp4", "status": "failed"}

