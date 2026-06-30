import os
from google import genai
from google.genai import types

def test_veo_sdk():
    cred_path = os.path.join(os.getcwd(), "google-credentials.json")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    
    import json
    with open(cred_path, "r") as f:
        creds = json.load(f)
        project_id = creds.get("project_id")
    
    # Initialize the client with Vertex AI
    client = genai.Client(vertexai=True, project=project_id, location="us-central1")
    
    prompt = "A beautiful cinematic shot of a coffee cup with steam rising. The person behind the camera says 'Wow, what a great cup of coffee' with native Australian female voice and perfect lip sync."
    
    print(f"Sending request to Veo 3.1 via SDK...")
    try:
        # We also need to pass the generateAudio parameter if Veo 3.1 supports it via SDK config
        config = types.GenerateVideosConfig(
            aspect_ratio="16:9",
            person_generation="ALLOW_ADULT",
            # We can try to pass generateAudio if the SDK supports kwargs
            # generate_audio=True # We'll skip this for the first SDK test just to see if the model string works
        )
        
        operation = client.models.generate_videos(
            model="veo-3.1-generate-001",
            prompt=prompt,
            config=config
        )
        
        print(f"Veo operation started successfully: {operation.name}")
        print("We don't need to wait for it to finish, just starting it means the SDK supports the model!")
        
    except Exception as e:
        print(f"SDK Error: {e}")

if __name__ == "__main__":
    test_veo_sdk()
