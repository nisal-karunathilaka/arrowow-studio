# Current Status & Technical Debt Analysis
**Arrowow Studio Local Production Kernel**
*Last Audited: June 18, 2026*

---

## 1. Executive Summary
The Arrowow Studio project is currently a local, CLI-driven, Human-in-the-Loop (HITL) video production pipeline designed to generate single-character UGC (User Generated Content) videos. While the codebase establishes a robust foundational architecture utilizing the `google-antigravity` SDK and Vertex AI, it faces significant limitations regarding video continuity, lip-sync fidelity, and autonomous execution. 

The system currently relies on manual terminal approvals (Gates 0-2) and struggles with the inherent constraints of current video generation models (specifically, the 8-second temporal limit of Veo 3.1 and latent space drift over consecutive renders).

---

## 2. System Architecture Deep Dive

The pipeline operates as a state machine managed by a central Kernel.

### A. Core Kernel & State Management
* **The Blackboard (`app/kernel/blackboard.py`)**: A thread-safe, local JSON state container. It persists the output of each pipeline stage (`brief`, `character`, `pre_production`, `visual_plan`, `static_frame`, `production`).
* **Strict Validation (`app/kernel/state_validator.py`)**: Ensures the Blackboard conforms to a rigid JSON schema (`schemas/session_state.schema.json`) before advancing stages.
* **The Cost Ledger (`app/kernel/cost_ledger.py`)**: A critical safeguard that audits Vertex AI billing. It tracks input/output tokens, image counts, and video counts. If generations exceed the hardcoded limits (2 videos, 5 images, 100k tokens), it flags the budget status to prevent runaway API costs.

### B. Multi-Agent Staging (The `app/agents` Module)
The system employs distinct agent roles to construct the prompt payload:
1. **Intake & Matcher**: Deterministically locks the input brief to a pre-defined persona profile (e.g., `sienna_fitness_01`).
2. **Pre-Production Pipeline**: 
   * *Creative Strategist*: Determines hook and angle.
   * *Scriptwriter*: Drafts the verbal dialogue.
   * *Text Critic*: A self-healing loop that rejects scripts containing banned terminology (e.g., "squat", "sheer") to bypass aggressive Vertex AI safety filters.
3. **Visual Planner**: Generates storyboards, determines wardrobe, and authors specific `static_frame_prompt` and `b_roll_prompt` outputs.

### C. Media Providers (`app/providers/live_providers.py`)
* **Audio**: Utilizes Google Cloud Text-to-Speech (`en-AU-Neural2-A`).
* **Image**: Uses Gemini 3.1 Flash Image (`gemini-3.1-flash-image`) to generate reference anchors.
* **Video**: Leverages Vertex AI Veo 3.1 (`veo-3.1-generate-001`) via asynchronous Google Cloud Storage (GCS) staging.

---

## 3. Evaluation of Generation Strategies
The repository currently contains three distinct strategies for generating video, distributed across different branches and uncommitted states. None of the current strategies fully resolve the long-form video challenge.

### Strategy A: 8-Second Image-to-Video Chaining (Base `master` Branch)
* **Mechanism**: The script is divided into ~15-word chunks. The first chunk is generated from a static image anchor. `ffmpeg` extracts the final frame of that chunk, which is then passed as the reference image anchor for the subsequent chunk.
* **Critical Failure Points**:
  * **Latent Space Drift**: After 2-3 iterations, the generator loses track of the original facial geometry. The character's face "melts," clothing textures morph, and background consistency fails.
  * **Visual Seams**: Stitching consecutive talking-head shots creates highly noticeable, jarring jump cuts because micro-movements do not align seamlessly frame-to-frame.

### Strategy B: A-Roll / B-Roll Sequential Split (Current Workspace / Unstaged)
* **Mechanism**: A mixed-architecture approach. Scene 1 (A-Roll) is a continuous talking head. Scene 2 (B-Roll) is an action shot (e.g., jogging) driven purely by voiceover.
* **Strengths**: Protects lip-sync. Because the character is not speaking to the camera in Scene 2, lip-sync mismatches are avoided. Seed locking (`GENERATION_SEED = 427819`) is applied *only* to the A-Roll to ensure facial consistency.
* **Critical Failure Points**:
  * **Hard Limitations**: It requires `ffmpeg` to concatenate the files, resulting in an abrupt, unstylized transition. Furthermore, the total duration is strictly capped at the sum of the two generations (usually ~15 seconds total).

### Strategy C: 15-Second Native Text-to-Video (`feature/15s-native-seed-locking`)
* **Mechanism**: Discards reference images entirely. Relies on Veo 3.1's native text-to-video capabilities to generate a single, continuous 15-second A-Roll shot using highly specific descriptive prompting and a locked seed.
* **Critical Failure Points**:
  * **Low Retention**: A 15-second static shot without visual variation performs poorly on short-form platforms (TikTok/Reels).
  * **Hallucination Risk**: Generating audio and matching lip movements for a full 15 seconds stretches the temporal coherence of current video models, often resulting in "uncanny valley" facial twitching near the end of the render.

---

## 4. Technical Debt & Critical Limitations

### 1. LLM Output Hallucination
The `live_agents.py` module frequently encounters JSON parsing failures when the LLM escapes quotes incorrectly or wraps output in unexpected markdown. While a robust `clean_and_parse_json` fallback exists, the reliance on raw text parsing over strict structured outputs (like OpenAI's structured outputs API or Gemini's function calling) is brittle.

### 2. Lip-Sync Fidelity
The pipeline currently relies entirely on Veo 3.1's native ability to infer lip movements from text prompts. It does not synchronize pre-generated, high-fidelity audio tracks (like ElevenLabs) frame-by-frame with the video output. This results in acceptable but non-production-grade sync.

### 3. Transition Quality
Video compilation relies on simple `ffmpeg` concat commands. The pipeline lacks spatial reasoning to execute Match Cuts, Whip Pans, or L-Cuts. The resulting cuts feel mechanical and amateurish.

### 4. Absence of Autonomous Feedback Loops
If the `VideoCritic` flags a completed video for severe uncanny valley effects or lip-sync failure, the pipeline simply halts or records an error. There is no automated routing to retry the generation with modified seeds, altered prompts, or alternative camera angles. The HITL (Human In The Loop) gates create bottlenecks preventing fully asynchronous, overnight video generation.
