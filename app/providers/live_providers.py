"""
live_providers.py — Arrowow Studio production media providers.

All providers load credentials from st.secrets["gcp_service_account"] first
(Streamlit Community Cloud), then fall back to the local google-credentials.json
file (local dev). No credentials are ever hardcoded.

Outputs (images, videos, audio) are uploaded to GCS and returned as signed URLs
so they are accessible from the Streamlit UI without a persistent local disk.
"""
from __future__ import annotations

import io
import json
import os
import time
import uuid
import datetime
import tempfile

# ---------------------------------------------------------------------------
# Credential helpers — shared by all providers
# ---------------------------------------------------------------------------

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Process-global credential cache. IMPORTANT: st.secrets is only reliably readable on the
# Streamlit MAIN thread, but renders run in a background thread (jobs.py). So we cache the
# resolved (project_id, creds) here — warm it once on the main thread (see warm_credentials /
# start_shot_bg) and every background worker reuses this cache without touching st.secrets.
_CREDS_CACHE = None


def _read_secret_info():
    """Return the service-account info dict from st.secrets, or None. Repairs the very common
    Streamlit-Cloud gotcha where the PEM private_key is stored with escaped '\\n' sequences."""
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            pk = info.get("private_key", "")
            # If the key came in with literal backslash-n instead of real newlines, fix it —
            # otherwise from_service_account_info raises "Could not deserialize key data".
            if pk and "\\n" in pk and "-----BEGIN" in pk:
                info["private_key"] = pk.replace("\\n", "\n")
            return info
    except Exception as e:
        print(f"[creds] st.secrets not accessible ({e.__class__.__name__}: {e})")
    return None


def _load_credentials():
    """Return (project_id, google.oauth2.service_account.Credentials).

    Priority: cached → st.secrets['gcp_service_account'] (Streamlit Cloud) → google-credentials.json.
    Raises a clear, actionable error if none resolve (instead of silently failing every render).
    """
    global _CREDS_CACHE
    if _CREDS_CACHE is not None:
        return _CREDS_CACHE

    from google.oauth2 import service_account

    info = _read_secret_info()
    source = "st.secrets"
    if info is None:
        cred_path = os.path.join(os.getcwd(), "google-credentials.json")
        if os.path.exists(cred_path):
            with open(cred_path) as f:
                info = json.load(f)
            source = "google-credentials.json"

    if info is None:
        raise FileNotFoundError(
            "No GCP credentials found. On Streamlit Cloud, set st.secrets['gcp_service_account'] "
            "to the full service-account JSON; locally, place google-credentials.json in the working dir."
        )

    try:
        creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    except Exception as e:
        raise RuntimeError(
            f"GCP credentials from {source} could not be parsed ({e}). If on Streamlit Cloud, "
            "ensure the private_key is pasted with real newlines (use a TOML triple-quoted string)."
        ) from e

    _CREDS_CACHE = (info.get("project_id"), creds)
    return _CREDS_CACHE


def warm_credentials() -> str:
    """Resolve + cache credentials on the CURRENT (main) thread so background render workers can
    reuse them. Returns a short status string; raises with a clear message if creds are missing."""
    project_id, _ = _load_credentials()
    return f"credentials ready (project {project_id})"


def _bucket_name(project_id: str) -> str:
    """Derive the GCS bucket name from the project ID."""
    # Allow override via st.secrets or env var for flexibility
    try:
        import streamlit as st
        b = st.secrets.get("app", {}).get("gcs_bucket")
        if b:
            return b
    except Exception:
        pass
    env = os.environ.get("GCS_BUCKET")
    if env:
        return env
    return f"arrowow-videos-{project_id}"


def _signed_url(bucket, blob_name: str, expiry_hours: int = 2) -> str:
    """Return a v4 signed URL for a blob, valid for *expiry_hours*."""
    from google.cloud import storage  # noqa: F401
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(hours=expiry_hours),
        method="GET",
    )


def _ensure_bucket(storage_client, bucket_name: str, project_id: str):
    """Return the bucket, creating it in us-central1 if it doesn't exist."""
    from google.cloud.exceptions import NotFound, Conflict
    bucket = storage_client.bucket(bucket_name)
    try:
        storage_client.get_bucket(bucket_name)
    except NotFound:
        try:
            new_bucket = storage_client.create_bucket(
                bucket_name, location="us-central1", project=project_id)
            print(f"[GCS] Created bucket gs://{bucket_name}")
            return new_bucket
        except Conflict:
            pass  # Another process created it
    return bucket


def _download_gcs_url_to_temp(url: str, suffix: str = ".png") -> str:
    """Download an https:// GCS signed URL to a NamedTemporaryFile and return its path."""
    import urllib.request
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    urllib.request.urlretrieve(url, tmp.name)
    return tmp.name


# ---------------------------------------------------------------------------
# upload_file_to_gcs — used by mock mode in media_tools.py
# ---------------------------------------------------------------------------

def upload_file_to_gcs(local_path: str, blob_name: str) -> str:
    """Upload *local_path* to GCS and return a signed URL.

    Used by DRY_RUN / LLM_ONLY mock mode to make demo assets accessible from
    the Streamlit UI without relying on local disk.
    """
    from google.cloud import storage
    project_id, creds = _load_credentials()
    storage_client = storage.Client(credentials=creds, project=project_id)
    bkt = _ensure_bucket(storage_client, _bucket_name(project_id), project_id)
    blob = bkt.blob(blob_name)
    blob.upload_from_filename(local_path)
    return _signed_url(bkt, blob_name)


# ---------------------------------------------------------------------------
# ImagenProvider — Gemini image generation
# ---------------------------------------------------------------------------

class ImagenProvider:
    def generate_image(self, prompt: str, reference_image: str = None,
                       output_dir: str = None) -> dict:
        print("[ImagenProvider] Generating image with Gemini Flash Image…")
        try:
            from google import genai
            from google.cloud import storage

            project_id, creds = _load_credentials()
            client = genai.Client(vertexai=True, project=project_id,
                                  location="global", credentials=creds)

            contents = [prompt]

            # reference_image may be a local path or a signed GCS https:// URL
            if reference_image and not reference_image.endswith("error.png"):
                local_path = None
                if reference_image.startswith("http://") or reference_image.startswith("https://"):
                    try:
                        local_path = _download_gcs_url_to_temp(reference_image, suffix=".png")
                    except Exception as dl_err:
                        print(f"[ImagenProvider] Could not download reference image: {dl_err}")
                elif os.path.exists(reference_image):
                    local_path = reference_image

                if local_path:
                    from PIL import Image as PILImage
                    img = PILImage.open(local_path)
                    contents.insert(0, img)

            # Rate-limit pacing (4 RPM quota)
            time.sleep(15)

            response = None
            for attempt in range(4):
                try:
                    response = client.models.generate_content(
                        model="gemini-3.1-flash-image",
                        contents=contents,
                    )
                    break
                except Exception as ex:
                    if "429" in str(ex) or "RESOURCE_EXHAUSTED" in str(ex):
                        backoff = 20 * (attempt + 1)
                        print(f"[ImagenProvider] 429 — retry in {backoff}s…")
                        time.sleep(backoff)
                        if attempt == 3:
                            raise
                    else:
                        raise

            # Extract inline image bytes and upload to GCS → return signed URL
            storage_client = storage.Client(credentials=creds, project=project_id)
            bkt = _ensure_bucket(storage_client, _bucket_name(project_id), project_id)
            blob_name = f"images/sienna_frame_{uuid.uuid4().hex[:6]}.png"

            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    blob = bkt.blob(blob_name)
                    blob.upload_from_string(part.inline_data.data,
                                            content_type="image/png")
                    url = _signed_url(bkt, blob_name)
                    return {"uri": url, "status": "success"}

            raise ValueError("No inline image data in Gemini response")

        except Exception as e:
            print(f"[ImagenProvider] Error: {e}")
            return {"uri": "error.png", "status": "failed", "error": str(e)[:300]}


# ---------------------------------------------------------------------------
# GoogleTTSProvider — Cloud Text-to-Speech
# ---------------------------------------------------------------------------

class GoogleTTSProvider:
    def generate_audio(self, text: str, voice_id: str = "en-US-Journey-F",
                       output_dir: str = None) -> dict:
        print(f"[GoogleTTSProvider] Synthesizing audio with voice {voice_id}…")
        try:
            from google.cloud import texttospeech, storage

            project_id, creds = _load_credentials()
            tts_client = texttospeech.TextToSpeechClient(credentials=creds)

            lang_code = "-".join(voice_id.split("-")[:2]) if "-" in voice_id else "en-US"
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=lang_code, name=voice_id)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3)

            response = tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config)

            # Upload MP3 to GCS → return signed URL
            storage_client = storage.Client(credentials=creds, project=project_id)
            bkt = _ensure_bucket(storage_client, _bucket_name(project_id), project_id)
            blob_name = f"audio/voiceover_{uuid.uuid4().hex[:6]}.mp3"
            blob = bkt.blob(blob_name)
            blob.upload_from_string(response.audio_content, content_type="audio/mpeg")
            url = _signed_url(bkt, blob_name)
            return {"uri": url, "status": "success"}

        except Exception as e:
            print(f"[GoogleTTSProvider] Error: {e}")
            return {"uri": "error.mp3", "status": "failed", "error": str(e)[:300]}


# ---------------------------------------------------------------------------
# VeoVideoProvider — Veo 3.1 video generation
# ---------------------------------------------------------------------------

class VeoVideoProvider:
    def generate_video(self, prompt: str, reference_image: str = None,
                       last_frame: str = None, output_dir: str = None,
                       seed: int = None, generate_audio: bool = True,
                       aspect_ratio: str = "16:9") -> dict:
        print("[VeoVideoProvider] Requesting video from Veo 3.1…")
        try:
            from google import genai
            from google.genai import types
            from google.cloud import storage

            project_id, creds = _load_credentials()
            client = genai.Client(vertexai=True, project=project_id,
                                  location="us-central1", credentials=creds)

            storage_client = storage.Client(credentials=creds, project=project_id)
            bucket_name = _bucket_name(project_id)
            bkt = _ensure_bucket(storage_client, bucket_name, project_id)
            output_gcs_uri = f"gs://{bucket_name}/renders/"

            def _upload_image_for_veo(img_src: str, prefix: str) -> str | None:
                """Upload a local path or signed URL to GCS input/ and return gs:// URI."""
                if not img_src or img_src.endswith("error.png"):
                    return None
                local = None
                if img_src.startswith("http://") or img_src.startswith("https://"):
                    try:
                        local = _download_gcs_url_to_temp(img_src, suffix=".png")
                    except Exception as dl_err:
                        print(f"[VeoVideoProvider] Could not download {prefix}: {dl_err}")
                        return None
                elif os.path.exists(img_src):
                    local = img_src
                else:
                    return None

                blob_name = f"inputs/{prefix}_{os.path.basename(local)}"
                blob = bkt.blob(blob_name)
                blob.upload_from_filename(local)
                return f"gs://{bucket_name}/{blob_name}"

            input_gcs_uri = _upload_image_for_veo(reference_image, "ref")
            last_gcs_uri = _upload_image_for_veo(last_frame, "last")

            config_params = {
                "output_gcs_uri": output_gcs_uri,
                "aspect_ratio": aspect_ratio if aspect_ratio in ("16:9", "9:16") else "16:9",
                "person_generation": "ALLOW_ADULT",
                "generate_audio": generate_audio,
                "duration_seconds": 8,
            }
            if seed is not None:
                config_params["seed"] = seed
            if last_gcs_uri:
                config_params["last_frame"] = types.Image(
                    gcs_uri=last_gcs_uri, mime_type="image/png")

            input_image_obj = None
            if input_gcs_uri:
                input_image_obj = types.Image(
                    gcs_uri=input_gcs_uri, mime_type="image/png")

            def _run(img_obj, include_last: bool) -> str:
                """Generate + poll one Veo op; return the gs:// video URI or raise."""
                cfg = dict(config_params)
                if not include_last:
                    cfg.pop("last_frame", None)
                op = client.models.generate_videos(
                    model="veo-3.1-generate-001", prompt=prompt, image=img_obj,
                    config=types.GenerateVideosConfig(**cfg))
                print(f"[VeoVideoProvider] Operation started: {op.name}")
                while not op.done:
                    print(".", end="", flush=True)
                    time.sleep(10)
                    op = client.operations.get(op)
                print("")
                if op.error:
                    raise Exception(f"Veo error: {op.error}")
                if not op.response or not op.response.generated_videos:
                    raise Exception("Veo returned an empty response — likely a safety filter block.")
                return op.response.generated_videos[0].video.uri

            # Veo's RAI filter intermittently blocks a render that uses an input image — either an
            # explicit input-image error (code 3, support 15236754) OR an "empty response" safety
            # block that the reference/tail frame can trigger. In BOTH cases, when an input image was
            # used, fall back to TEXT-TO-VIDEO (no input image) so the shot still renders — identity
            # is carried by the prompt. Blocked renders are not billed, so the retry is free to try.
            used_fallback = False
            try:
                gcs_path = _run(input_image_obj, include_last=bool(last_gcs_uri))
            except Exception as first_err:
                s = str(first_err).lower()
                safety_block = ("input image violates" in s or ("'code': 3" in s and "image" in s)
                                or "empty response" in s or "safety filter" in s or "usage guidelines" in s)
                if input_image_obj is not None and safety_block:
                    print("[VeoVideoProvider] Image-conditioned render RAI-blocked — retrying as "
                          "text-to-video (no input image)…")
                    gcs_path = _run(None, include_last=False)
                    used_fallback = True
                else:
                    raise

            # The rendered video is already in GCS. Generate a signed URL directly —
            # no local download needed (Streamlit Cloud has no persistent disk).
            relative_path = gcs_path.replace(f"gs://{bucket_name}/", "")
            url = _signed_url(bkt, relative_path, expiry_hours=2)

            print(f"[VeoVideoProvider] Success → {gcs_path}" + (" (text-to-video fallback)" if used_fallback else ""))
            return {"uri": url, "status": "success", "fallback_t2v": used_fallback}

        except Exception as e:
            print(f"[VeoVideoProvider] Failed: {e}")
            return {"uri": "error.mp4", "status": "failed", "error": str(e)[:300]}
