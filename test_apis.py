import os
import json
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "google-credentials.json")
from app.providers.live_providers import GoogleTTSProvider, ImagenProvider
# test TTS
tts = GoogleTTSProvider()
tts.generate_audio("Hello this is a test", "en-US-Journey-F", output_dir="output")
# test Imagen
imagen = ImagenProvider()
imagen.generate_image("A cute cat", "none", output_dir="output")
