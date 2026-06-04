import os, json, time
from collections import namedtuple
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "google-credentials.json")
from google import genai
from google.oauth2 import service_account

with open("google-credentials.json", "r") as f:
    creds = json.load(f)
    project_id = creds.get("project_id")
scopes = ["https://www.googleapis.com/auth/cloud-platform"]
credentials = service_account.Credentials.from_service_account_file("google-credentials.json", scopes=scopes)
client = genai.Client(vertexai=True, project=project_id, location="us-central1", credentials=credentials)

op_id = "9f56ff26-c131-4d84-aee9-f4640035f3bf"
op_name = f"projects/{project_id}/locations/us-central1/publishers/google/models/veo-2.0-generate-001/operations/{op_id}"

DummyOp = namedtuple("DummyOp", ["name"])
operation = client.operations.get(operation=DummyOp(name=op_name))

print("operation.done:", operation.done)
if hasattr(operation, "error") and operation.error:
    print("operation.error:", operation.error)
if hasattr(operation, "response") and operation.response:
    print("operation.response dict:", operation.response)
else:
    print("operation.response is None or not present")
