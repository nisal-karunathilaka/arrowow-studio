import os
import json
from google import genai
from google.oauth2 import service_account

cred_path = os.path.join(os.getcwd(), "google-credentials.json")
with open(cred_path, "r") as f:
    creds = json.load(f)
project_id = creds.get("project_id")
# Create credentials object
credentials = service_account.Credentials.from_service_account_file(
    cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

# Helper to list models in a region
regions = ["global", "us-central1", "europe-west1", "asia-east1"]
for region in regions:
    try:
        client = genai.Client(vertexai=True, project=project_id, location=region, credentials=credentials)
        print(f"\nListing models in region: {region}")
        for model in client.models.list():
            print(f"- {model.name}")
    except Exception as e:
        print(f"Failed to list models in {region}: {e}")
