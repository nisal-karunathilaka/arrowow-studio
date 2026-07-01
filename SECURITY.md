# Security Policy

## Reporting a vulnerability

If you discover a security issue in Arrowow Studio, please report it privately to the
maintainer rather than opening a public issue. Do not include secrets, tokens, or private
keys in any report.

## How credentials are handled

Arrowow Studio calls Google Cloud (Vertex AI: Veo, Gemini, Imagen; Cloud TTS; Cloud Storage)
using a GCP **service account**. Credentials are **never committed** to this repository.

They are resolved at runtime, in this order (see `app/providers/live_providers.py` and
`app/adk/llm_backend.py`):

1. **Streamlit Community Cloud** — `st.secrets["gcp_service_account"]`, set via the app's
   **Settings → Secrets** (Advanced settings). These secrets are stored by Streamlit,
   injected server-side only, and are **not** part of this repo or exposed to app visitors.
2. **Local development** — a `google-credentials.json` service-account file in the working
   directory, **git-ignored** (never tracked).

### Setting the secret on Streamlit Cloud

In the app's **Settings → Secrets**, paste the service-account JSON as TOML. Use a
triple-quoted string for `private_key` so the PEM newlines are preserved:

```toml
[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = """-----BEGIN PRIVATE KEY-----
...real newlines...
-----END PRIVATE KEY-----
"""
client_email = "your-sa@your-project.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"

[app]
gcs_bucket = "arrowow-videos-YOUR_PROJECT_ID"  # optional override
```

A placeholder reference lives at `.streamlit/secrets.toml.template`.

## What the app exposes (and does not)

- **Never exposed to users:** the service-account key. It stays in server memory only.
- **Exposed by design:** generated media (images, videos, audio) are served to the UI as
  short-lived **GCS v4 signed URLs** (expire in ~2 hours). These grant temporary read access
  to a single object; they do not expose credentials.

## Git hygiene (enforced)

The following are git-ignored and must never be committed:

```
google-credentials.json
.streamlit/secrets.toml
```

If a secret is ever committed by accident: **rotate/revoke it immediately** in the GCP
Console (the essential mitigation — a leaked key must be assumed compromised even after
history is scrubbed), then purge it from history with `git filter-repo` and force-push.

## Least privilege

Grant the service account only the roles it needs (e.g. Vertex AI User, Storage Object
Admin on the app bucket). Avoid Owner/Editor. For production, prefer GCP Secret Manager or
Workload Identity over a downloaded key file.
