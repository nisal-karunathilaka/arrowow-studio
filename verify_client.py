import os
import json
from google import genai

# Load credentials from the local service account key
cred_path = os.path.join(os.getcwd(), "google-credentials.json")
with open(cred_path, "r") as f:
    creds = json.load(f)
project_id = creds.get("project_id")

# Create a Vertex AI client (no model call)
client = genai.Client(vertexai=True, project=project_id, location="us-central1")
print("✅ Client instantiated successfully for project:", project_id)
