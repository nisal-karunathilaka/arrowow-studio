class ImageProvider:
    def generate_image(self, prompt: str, reference_image: str, output_dir: str = None) -> dict:
        raise NotImplementedError

class MockImageProvider(ImageProvider):
    def generate_image(self, prompt: str, reference_image: str, output_dir: str = None) -> dict:
        print("[MockImageProvider] Generating mock image...")
        return {
            "uri": "mock://image/sienna_static_frame_01.png",
            "status": "success"
        }

class VideoProvider:
    def generate_video(self, prompt: str, reference_image: str, output_dir: str = None) -> dict:
        raise NotImplementedError

class MockVideoProvider(VideoProvider):
    def generate_video(self, prompt: str, reference_image: str, output_dir: str = None) -> dict:
        print("[MockVideoProvider] Generating mock video...")
        return {
            "uri": "mock://video/sienna_final_video_01.mp4",
            "status": "success"
        }
        
class AudioProvider:
    def generate_audio(self, text: str, voice_id: str, output_dir: str = None) -> dict:
        raise NotImplementedError

class MockAudioProvider(AudioProvider):
    def generate_audio(self, text: str, voice_id: str, output_dir: str = None) -> dict:
        print(f"[MockAudioProvider] Generating audio with voice {voice_id}...")
        return {
            "uri": "mock://audio/sienna_voiceover_01.wav",
            "status": "success"
        }
