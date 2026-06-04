import os
import json
import time
import requests
import google.auth
import google.auth.transport.requests

def get_access_token():
    cred_path = os.path.join(os.getcwd(), "google-credentials.json")
    from google.oauth2 import service_account
    credentials = service_account.Credentials.from_service_account_file(
        cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token, credentials.project_id

def test_veo_3_1():
    token, default_project = get_access_token()
    project_id = "gen-lang-client-0620387606"  # User's specific project
    
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/veo-3.1-generate-001:predictLongRunning"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    payload = {
        "instances": [
            {
                "prompt": "A beautiful cinematic shot of a coffee cup with steam rising. The person behind the camera says 'Wow, what a great cup of coffee' with native Australian female voice and perfect lip sync."
            }
        ],
        "parameters": {
            "sampleCount": 1,
            "generateAudio": True # Enable audio generation as per docs
        }
    }
    
    print(f"Sending request to Veo 3.1 API...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return
        
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    operation_name = data.get("name")
    if not operation_name:
        print("No operation name found.")
        return
        
    poll_url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/veo-3.1-generate-001:fetchPredictOperation"
    
    print(f"\nPolling operation {operation_name}...")
    
    poll_payload = {
        "operationName": operation_name
    }
    
    while True:
        poll_response = requests.post(poll_url, headers=headers, json=poll_payload)
        poll_data = poll_response.json()
        
        if poll_data.get("done"):
            print(f"\nGeneration complete!")
            print(json.dumps(poll_data, indent=2))
            break
            
        print(".", end="", flush=True)
        time.sleep(10)

if __name__ == "__main__":
    test_veo_3_1()
