import os
from google import genai

def test_gemini_sdk():
    project_id = "gen-lang-client-0620387606"
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "google-credentials.json")
    
    client = genai.Client(vertexai=True, project=project_id, location="us-central1")
    
    print("Testing gemini-3.5-flash...")
    try:
        # Sometimes the SDK requires publishers/google/models/ prefix for preview models
        model_name = "publishers/google/models/gemini-3.5-flash"
        response = client.models.generate_content(
            model=model_name,
            contents="Hello! Are you Gemini 3.5 Flash?"
        )
        print(f"Success! Response: {response.text}")
    except Exception as e:
        print(f"Error with full path: {e}")

if __name__ == "__main__":
    test_gemini_sdk()
