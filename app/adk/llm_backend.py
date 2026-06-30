"""
Arrowow Studio — Structured LLM Backend (Vertex AI via google.genai)
====================================================================

The single live entrypoint for the creative agents. Uses the standard **google.genai**
Vertex client with native structured output (`response_schema` + `response_mime_type=
application/json`). Structured-output only — there is NO brittle regex/JSON-cleaning
fallback; clean JSON is guaranteed by the response mime type, and the agent validates
it against its Pydantic schema (system design §8 of the ideal docs).

Why google.genai (not the Antigravity SDK the old code used):
  - portable & standard for the Cloud Run deploy target (no heavy agent harness),
  - importable from base Python (the project venv's antigravity import is very slow),
  - already the SDK used by the VideoCritic and the media providers.

`async` on purpose: the ADK graph runs in one event loop, so each agent awaits this
(`client.aio.*`). `structured_generate` is module-level so tests can stub it.
"""
from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MODEL = "gemini-3.5-flash"   # cheap creative tier (system design §1)
MAX_ATTEMPTS = 3
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_CLIENT = None  # cached genai.Client for the process


def _resolve_project_and_creds():
    """Resolve (project_id, credentials). Prefers env (Cloud Run / Secret Manager),
    falls back to the local credentials file for dev.

      1. Streamlit secrets 'gcp_service_account' (optional, dict)
      2. GOOGLE_CLOUD_PROJECT for the project id (optional)
      3. GOOGLE_APPLICATION_CREDENTIALS or ./google-credentials.json for the key
    """
    # 1. Try to load from Streamlit secrets first (serverless)
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            from google.oauth2 import service_account
            info = dict(st.secrets["gcp_service_account"])
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES)
            project = info.get("project_id")
            return project, credentials
    except Exception:
        pass

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or \
        os.path.join(os.getcwd(), "google-credentials.json")

    credentials = None
    if os.path.exists(cred_path):
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=SCOPES)
        if not project:
            with open(cred_path) as f:
                project = json.load(f).get("project_id")

    if not project:
        raise FileNotFoundError(
            "No GCP project found. Set GOOGLE_CLOUD_PROJECT, or point "
            "GOOGLE_APPLICATION_CREDENTIALS at a service-account file, or place "
            "google-credentials.json in the working dir. (Prod: use Secret Manager.)"
        )
    return project, credentials


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        from google import genai
        project, credentials = _resolve_project_and_creds()
        _CLIENT = genai.Client(vertexai=True, project=project,
                               location="global", credentials=credentials)
    return _CLIENT


def _track_tokens(state: dict | None, usage) -> None:
    if not state or not usage:
        return
    ledger = state.setdefault("cost_ledger", {})
    ledger["estimated_input_tokens"] = (
        ledger.get("estimated_input_tokens", 0) + (getattr(usage, "prompt_token_count", 0) or 0)
    )
    ledger["estimated_output_tokens"] = (
        ledger.get("estimated_output_tokens", 0) + (getattr(usage, "candidates_token_count", 0) or 0)
    )


async def structured_generate(
    system_instruction: str,
    user_prompt: str,
    output_schema: Any,
    state: dict | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Call Vertex Gemini and return a dict validated against `output_schema`.

    Structured-output ONLY. Raises ValueError if the model fails to return a usable
    structured object after MAX_ATTEMPTS — by design, no free-text JSON salvage.
    """
    from google.genai import types

    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=output_schema,
        temperature=0.6,
    )

    last_err: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            resp = await client.aio.models.generate_content(
                model=model, contents=user_prompt, config=config)
            _track_tokens(state, getattr(resp, "usage_metadata", None))

            parsed = getattr(resp, "parsed", None)
            if parsed is not None:
                return parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed)
            # response_mime_type guarantees clean JSON text (not markdown) — parse directly.
            if getattr(resp, "text", None):
                return json.loads(resp.text)
        except Exception as e:  # network / SDK / transient — retry
            last_err = e

    raise ValueError(
        f"Structured output failed for {getattr(output_schema, '__name__', output_schema)} "
        f"after {MAX_ATTEMPTS} attempts. Last error: {last_err}"
    )
