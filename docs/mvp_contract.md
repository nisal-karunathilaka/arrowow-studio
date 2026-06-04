# MVP Contract: Arrowow Studio Local Production Kernel

## 1. Goal
Build a local, low-cost, HITL-controlled video production pipeline that generates a single character-driven UGC video from one brief.

## 2. Scope
* **Execution:** Local Python CLI
* **Character:** 1 Character (`sienna_fitness_01`)
* **Storage:** Local JSON files
* **Approval Gates:** 4 Terminal-based HITL checkpoints

## 3. Out of Scope for MVP
* Web Frontend / UI
* Cloud Deployment (Cloud Run / Workflows)
* Firestore integration
* Multi-character generation
* Videos longer than 8 seconds

## 4. Execution Modes
* `DRY_RUN`: Testing agent flows and state validation without paid API calls. Output is mock JSON.
* `LLM_ONLY`: Uses Gemini for text planning only.
* `LIVE_MEDIA`: Calls live media APIs (Imagen, Veo, ElevenLabs, HeyGen) only after approvals.

## 5. Success Criteria
The MVP is successful if it can generate one approved short UGC video package with:
1. Valid character resolution and state locking.
2. Approved UGC Script (Gate 1).
3. Approved Visual Plan (Gate 2A).
4. Approved Static Frame (Gate 2B).
5. One video generation attempt (max 1 retry), 8 seconds at 720p.
6. Complete final QA report and Cost Ledger validation.
7. Output populated in local `/output/session_id/` directory.
