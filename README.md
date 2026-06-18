# Arrowow Studio — UGC Video Production Engine

Arrowow Studio is an autonomous, multi-agent vertical-video production pipeline built using the Google Antigravity (AGY) ADK SDK and Google Vertex AI. It is designed to generate natural, high-performance UGC (User Generated Content) fitness ads featuring a consistent cast (e.g. "Sienna") on a budget.

---

## 🚀 Key Features

* **Multi-Agent Staging Graph**: Assembles scroll-stopping hooks, campaign scripts, wardrobes, and image/video prompts dynamically via structured Gemini 3.5 Flash and Gemini 3.1 Pro interfaces.
* **Auto-Healing Generator (Failed Renders Recovery)**: Dynamically checks for any initially failed or safety-blocked video renders, automatically shifting their seed and re-rendering them before compilation.
* **Closed-Loop Adversarial Refiner (GAN)**: An autonomous Generator $\leftrightarrow$ Discriminator loop that evaluates clip realism, lip-sync, and visual artifacts using a multimodal Gemini 3.1 Pro critic. If defects are found, it performs structured prompt mutations and seed jitters to self-heal.
* **Dynamic Post-Production Grading Loop**: Dynamically adjusts desaturation, contrast, and film grain noise in the final FFmpeg stage based on feedback from the QA critic to eliminate Veo's default glossy, hyperrealistic look.
* **Professional Movie Cuts (FFmpeg Crossfades)**: Applies dynamic video (`xfade`) and audio (`acrossfade`) transitions to blend consecutive 8-second beats seamlessly into a unified vertical movie.

---

## 🛠️ Project Setup

### 1. Requirements & Credentials
1. Ensure `ffmpeg` is installed on your local path (used for concatenating, crossfading, and color-grading beats).
2. Place your Vertex AI service account key file in the root directory and name it **`google-credentials.json`** (this is gitignored).

### 2. Configuration
Create a `.env` file in the root if you want to configure additional environment variables:
```bash
# Optional: force a specific GCP project ID (inferred from credentials by default)
GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
```

---

## 💻 Running the Application

Always run commands from the project root.

### 1. Diagnostic Verification (Mock Mode)
Run the diagnostic self-test suite to verify imports, schema structure, and mock loop logic without making live GCP calls:
```bash
python -m app.adk.selftest
```

### 2. End-to-End Production Loop
Run the full 5-beat storyboard generation, rendering, composition, and critic loop:

* **Mock Dry Run** (no cost, generates mock URIs):
  ```bash
  python app/main.py --mode DRY_RUN --session my_dry_session
  ```
* **Live Media Run** (calls Veo 3.1, Imagen, Cloud TTS, and Gemini QA Critic):
  ```bash
  python app/main.py --mode LIVE_MEDIA --session my_live_session
  ```

### 3. Single-Beat Closed-Loop Refiner (GAN)
Target and refine the visual parameters of a single beat (e.g. `hook`, `intro`, `action`, `proof`, `cta`) over multiple iterations:

* **Mock Dry Run**:
  ```bash
  python -m app.adk.refine_beat --beat intro --mode DRY_RUN --session refiner_test
  ```
* **Live Refinement Run** (Capped at max 3 iterations to control cost):
  ```bash
  python -m app.adk.refine_beat --beat intro --iters 3 --mode LIVE_MEDIA --session refiner_test
  ```

---

## 💰 Cost Governance

* **Dev Spend Ceiling**: The system maintains a hard **$100** limit across all runs. Any execution that would push overall spend beyond this cap is automatically halted by a budget guard.
* **Cost Accounting**: Every successful Vertex AI or Google Cloud call writes a cost entry into the local session cost ledger. All session logs and persisted states are written to:
  ```bash
  output/{session_name}/session_state.json
  ```
