import os
import json
from google import genai
from google.genai import types

def test_image():
    cred_path = os.path.join(os.getcwd(), "google-credentials.json")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    with open(cred_path, "r") as f:
        creds = json.load(f)
        project_id = creds.get("project_id")
        
    client = genai.Client(vertexai=True, project=project_id, location="global")
    
    print("Testing gemini-3.1-flash-image generate_images method...")
    try:
        # Try the helper method first
        result = client.models.generate_images(
            model='gemini-3.1-flash-image',
            prompt='A futuristic glowing blue apple on a metallic table.',
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1"
            )
        )
        print("Success with generate_images!")
        for i, generated_image in enumerate(result.generated_images):
            # image is usually an Image object with image.image_bytes
            with open(f"test_image_{i}.png", "wb") as f:
                f.write(generated_image.image.image_bytes)
            print(f"Saved test_image_{i}.png")
        return
    except Exception as e:
        print(f"generate_images helper failed: {e}")
        
    print("\nTesting gemini-3.1-flash-image generate_content method...")
    try:
        # Fallback to generate_content
        response = client.models.generate_content(
            model='gemini-3.1-flash-image',
            contents='Generate an image of a futuristic glowing blue apple on a metallic table.'
        )
        print("Success with generate_content!")
        # check parts
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                with open("test_image_inline.png", "wb") as f:
                    f.write(part.inline_data.data)
                print("Saved test_image_inline.png")
    except Exception as e:
        print(f"generate_content failed: {e}")

if __name__ == "__main__":
    test_image()
