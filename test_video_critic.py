import os
import json
from google import genai
from google.genai import types
from google.oauth2 import service_account

cred_path = os.path.join(os.getcwd(), "google-credentials.json")
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

video_path = "output/4bac5287-60ef-400f-9ee2-10592718da60/veo_final_synced.mp4"
if not os.path.exists(video_path):
    print("Video file not found.")
    exit(1)

print(f"Uploading {video_path}...")
# Note: For vertex, genai client handles file uploads to Vertex API (Files API is supported on Vertex in the new SDK?)
# Actually, File API might be Gemini Developer API only. Let's try it.
try:
    uploaded_file = client.files.upload(file=video_path)
    print(f"Uploaded file: {uploaded_file.name}")
except Exception as e:
    print(f"File upload failed: {e}")
    # Fallback to base64 if it's small enough, or GCS
    print("Using inline data...")
    with open(video_path, "rb") as vf:
        video_bytes = vf.read()
    uploaded_file = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")

print("Calling Gemini 1.5 Pro to analyze video...")
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            uploaded_file,
            "Analyze this video for production-grade natural quality. Specifically, pay close attention to the human face, movements, and if the lip sync perfectly matches the audio. Is there any uncanny valley effect? Rate it out of 10."
        ]
    )
    print(response.text)
except Exception as e:
    print(f"Analysis failed: {e}")
