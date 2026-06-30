import os
import json
import traceback
from google import genai
from google.oauth2 import service_account

# Load credentials and project ID from the local key file
cred_path = os.path.join(os.getcwd(), "google-credentials.json")
with open(cred_path, "r") as f:
    creds = json.load(f)
project_id = creds.get("project_id")
print(f"🔑 Project ID from credentials: {project_id}")

# Build a service account Credentials object (required for the client)
credentials = service_account.Credentials.from_service_account_file(
    cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

# Try Flash model in the global region (cheapest)
client = genai.Client(vertexai=True, project=project_id, location="global", credentials=credentials)
model_name = "gemini-3.5-flash"
print("✅ Vertex AI client instantiated (global region) with explicit credentials.")

prompt = "Hello!"
try:
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    print("🪄 Gemini response snippet (flash model):")
    try:
        text = response.text if hasattr(response, "text") else str(response)
        print(text[:200])
    except Exception:
        print(response)
except Exception as e:
    print("❌ Flash model request failed. Trying a pro model as fallback.")
    traceback.print_exc()
    # Fallback to a pro model
    model_name = "gemini-3.1-pro-preview"
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        print("🪄 Gemini response snippet (pro model):")
        text = response.text if hasattr(response, "text") else str(response)
        print(text[:200])
    except Exception as e2:
        print("❌ Pro model request also failed:")
        traceback.print_exc()


# End of verification
