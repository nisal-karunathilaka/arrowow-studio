"""
Arrowow Studio — Studio Console (Streamlit)
===========================================

A ChatGPT/Gemini-style console for the autonomous UGC video factory. Each "conversation"
is one video production: pick a brand + character + platform + aspect ratio, write a
brief, and the multi-agent pipeline runs in shot-by-shot human-in-the-loop steps.

You review and approve (or request changes to) every step — including each individual
shot — before the pipeline advances. After all shots are approved, the composite step
assembles the master cut and runs final QA.

Run:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid

import streamlit as st

from app.ui import pipeline, jobs
from app.adk.profiles import brands

# ---------------------------------------------------------------------------
# Page config + light theme polish
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Arrowow Studio", page_icon="🎬", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  .block-container { padding-top: 2.2rem; max-width: 1100px; }
  /* Stepper */
  .aw-step { text-align:center; padding:.5rem .2rem; border-radius:12px; font-size:.8rem; }
  .aw-step .ic { font-size:1.35rem; line-height:1.6rem; }
  .aw-step .lb { font-weight:600; }
  .aw-done   { background:rgba(34,197,94,.12);  color:#16a34a; }
  .aw-active { background:rgba(59,130,246,.14);  color:#2563eb; box-shadow:0 0 0 1px rgba(59,130,246,.35) inset; }
  .aw-pending{ background:rgba(148,163,184,.10); color:#94a3b8; }
  .aw-error  { background:rgba(239,68,68,.12);   color:#dc2626; }
  /* Chips */
  .aw-chip { display:inline-block; padding:.12rem .55rem; border-radius:999px; font-size:.72rem;
             background:rgba(99,102,241,.12); color:#6366f1; margin-right:.3rem; font-weight:600; }
  .aw-chip-muted { background:rgba(148,163,184,.15); color:#64748b; }
  .aw-chip-green { background:rgba(34,197,94,.15); color:#16a34a; }
  .aw-chip-amber { background:rgba(245,158,11,.15); color:#d97706; }
  .aw-brief { background:rgba(148,163,184,.08); border-left:3px solid #6366f1; padding:.7rem .9rem;
              border-radius:8px; font-size:.92rem; }
  .aw-beat { background:rgba(148,163,184,.06); border:1px solid rgba(148,163,184,.18);
             border-radius:10px; padding:.6rem .8rem; margin-bottom:.45rem; }
  .aw-log { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.74rem;
            color:#64748b; white-space:pre-wrap; }
  div[data-testid="stSidebarHeader"] { padding-bottom:0; }
  .aw-shot-header { display:flex; align-items:center; gap:.5rem; margin-bottom:.3rem; }
</style>
""", unsafe_allow_html=True)

# Segments that run automatically when they become current.
# Shot segments auto-run in DRY_RUN/LLM_ONLY; in LIVE_MEDIA they show a gate.
AUTO_RUN_PLANNING = {"script", "visual_plan"}
AUTO_RUN_FINAL = {"composite_qa"}

PLATFORMS = ["Instagram Reels", "TikTok", "YouTube Shorts", "Instagram Feed", "YouTube"]
RESOLUTIONS = {"9:16  ·  Vertical (Reels / TikTok / Shorts)": "9:16",
               "16:9  ·  Landscape (YouTube / web)": "16:9"}
CHARACTERS = {"Sienna — fitness & lifestyle creator (girl-next-door)": "sienna_fitness_01"}

EXAMPLE_BRIEF = (
    "30-second UGC ad introducing our new seamless training set. Goal: drive first-purchase "
    "from women 20–35 into fitness. Tone: high-energy, tough-love bestie. Show the gear moving "
    "with her through a workout, emphasise all-day comfort and that it actually performs. End "
    "on a confident call to action to shop the drop today."
)


# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------
def init_state():
    st.session_state.setdefault("convs", {})       # id -> conversation
    st.session_state.setdefault("active", None)     # active conversation id
    st.session_state.setdefault("mode", "DRY_RUN")  # global default for NEW conversations


def new_blank_conv() -> str:
    """Open the new-video composer (no conversation object until 'Generate' is pressed)."""
    st.session_state.active = None


def create_conversation(config: dict) -> str:
    cid = "vid_" + uuid.uuid4().hex[:8]
    config["session_id"] = cid
    session = pipeline.new_production_session(config)
    conv = {
        "id": cid,
        "title": (config["user_brief"][:42] + "…") if len(config["user_brief"]) > 42 else config["user_brief"],
        "created": time.time(),
        "config": config,
        "session": session,
        "stage_idx": 0,
        "status": {k: "pending" for k in pipeline.SEGMENT_KEYS},
        "logs": {k: [] for k in pipeline.SEGMENT_KEYS},
        "shot_job_ids": {},   # segment_key -> job_id for background shot renders
        "error": None,
        "history": [{"brief": config["user_brief"]}],
    }
    st.session_state.convs[cid] = conv
    st.session_state.active = cid
    return cid


# ---------------------------------------------------------------------------
# Run helpers
# ---------------------------------------------------------------------------
def _logger(conv, seg):
    logs = conv["logs"].setdefault(seg, [])
    return lambda m: logs.append(m)


def run_sync(conv, seg):
    """Run a fast segment inline (blocks this rerun under a spinner)."""
    conv["status"][seg] = "running"
    conv["error"] = None
    try:
        asyncio.run(pipeline.run_segment(seg, conv["session"], conv["config"]["mode"], _logger(conv, seg)))
        conv["status"][seg] = "review"
    except Exception as e:
        conv["status"][seg] = "error"
        conv["error"] = str(e)
        _logger(conv, seg)(f"[error] {e}")


def modify_sync(conv, seg, feedback):
    conv["status"][seg] = "running"
    conv["error"] = None
    try:
        asyncio.run(pipeline.regenerate_segment(seg, conv["session"], conv["config"]["mode"],
                                                feedback, _logger(conv, seg)))
        conv["status"][seg] = "review"
    except Exception as e:
        conv["status"][seg] = "error"
        conv["error"] = str(e)
        _logger(conv, seg)(f"[error] {e}")


def start_shot_bg(conv, seg_key, feedback=None):
    """Kick a shot or composite segment off into a background thread."""
    sess, mode = conv["session"], conv["config"]["mode"]

    # Credentials must be resolved on the MAIN thread — st.secrets is not reliably readable from
    # the background render worker (this was the deployed 'render failed' bug: creative agents run
    # inline and worked, but the threaded Veo/Imagen render could not read st.secrets). Warm + cache
    # BOTH credential paths here (media providers + LLM client) so the worker reuses them; if they
    # are missing/misconfigured, fail loudly in the UI instead of a silent 'render failed'.
    if mode == "LIVE_MEDIA":
        try:
            from app.providers import live_providers
            live_providers.warm_credentials()
            from app.adk import llm_backend
            llm_backend._get_client()  # warms the cached Gemini client used by per-shot VQA
        except Exception as e:
            conv["status"][seg_key] = "error"
            conv["error"] = f"GCP credentials not ready: {e}"
            return

    job_id = f"{conv['id']}:{seg_key}:{int(time.time())}"
    conv["shot_job_ids"][seg_key] = job_id
    conv["status"][seg_key] = "running"
    conv["error"] = None

    async def factory(log):
        if feedback:
            await pipeline.regenerate_segment(seg_key, sess, mode, feedback, log)
        else:
            await pipeline.run_segment(seg_key, sess, mode, log)

    jobs.start(job_id, factory)


def approve(conv, seg):
    conv["status"][seg] = "approved"
    if conv["stage_idx"] < len(pipeline.SEGMENT_KEYS) - 1:
        conv["stage_idx"] += 1


def regenerate_full(conv, new_brief: str):
    """Refine the brief and regenerate the whole video in the SAME conversation."""
    conv["config"]["user_brief"] = new_brief
    pipeline._run_intake(conv["session"], conv["config"])  # refresh brief in shared state
    conv["stage_idx"] = 0
    for k in conv["status"]:
        conv["status"][k] = "pending"
    for k in conv["logs"]:
        conv["logs"][k] = []
    conv["shot_job_ids"] = {}
    conv["error"] = None
    conv["history"].append({"brief": new_brief})


# ---------------------------------------------------------------------------
# Conversation Deletion and GCS Cleanup
# ---------------------------------------------------------------------------
def delete_conversation(cid):
    if cid in st.session_state.convs:
        conv = st.session_state.convs[cid]
        session_id = conv["session"].state.get("metadata", {}).get("session_id", cid)
        
        # Delete GCS assets synchronously
        try:
            from app.providers.live_providers import _get_credentials_and_project
            from google.cloud import storage
            credentials, project_id = _get_credentials_and_project()
            storage_client = storage.Client(credentials=credentials, project=project_id)
            bucket_name = f"arrowow-videos-{project_id}"
            bucket = storage_client.bucket(bucket_name)
            if bucket.exists():
                prefix = f"sessions/{session_id}/"
                blobs = list(bucket.list_blobs(prefix=prefix))
                if blobs:
                    bucket.delete_blobs(blobs)
                    print(f"[GCS Cleanup] Deleted {len(blobs)} blobs under prefix {prefix}")
        except Exception as e:
            print(f"[GCS Cleanup] Error: {e}")
            
        del st.session_state.convs[cid]
        if st.session_state.active == cid:
            st.session_state.active = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def sidebar():
    with st.sidebar:
        st.markdown("### 🎬 Arrowow Studio")
        if st.button("＋ New video", use_container_width=True):
            new_blank_conv()
            st.rerun()

        st.divider()
        modes = ["🧪 Mock (DRY_RUN)", "🧠 Live Creative (LLM_ONLY)", "🚀 Live Media (LIVE_MEDIA)"]
        default = {"DRY_RUN": 0, "LLM_ONLY": 1, "LIVE_MEDIA": 2}.get(st.session_state.mode, 0)
        mode_label = st.radio("Mode", modes, index=default)
        if mode_label.startswith("🧪"):
            st.session_state.mode = "DRY_RUN"
        elif mode_label.startswith("🧠"):
            st.session_state.mode = "LLM_ONLY"
        else:
            st.session_state.mode = "LIVE_MEDIA"
        tracker = pipeline.DevSpendTracker()
        st.caption(f"Dev budget remaining: **${tracker.remaining():.2f} / ${tracker.CEILING_USD:.0f}**")

        st.divider()
        st.markdown("**Your videos**")
        convs = sorted(st.session_state.convs.values(), key=lambda c: -c["created"])
        if not convs:
            st.caption("No videos yet — start one above.")
        for c in convs:
            done = sum(1 for s in c["status"].values() if s == "approved")
            label = f"{'🟢' if c['id']==st.session_state.active else '⚪️'} {c['title']}"
            
            c1, c2 = st.columns([5, 1.2])
            with c1:
                if st.button(label, key=f"sel_{c['id']}", use_container_width=True):
                    st.session_state.active = c["id"]
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"del_{c['id']}", use_container_width=True, help="Delete this video project and clean up GCS storage"):
                    delete_conversation(c["id"])
                    st.rerun()
            st.caption(f"　{done}/{len(pipeline.SEGMENT_KEYS)} steps · {c['config']['mode'].replace('_',' ').title()}")


# ---------------------------------------------------------------------------
# New-video composer
# ---------------------------------------------------------------------------
def composer():
    st.markdown("## Start a new video")
    st.caption("Configure the campaign, then the multi-agent pipeline drafts it step by step "
               "for your review.")

    c1, c2 = st.columns(2)
    with c1:
        brand_opts = {f"{b['name']}  ·  {b['product']}": b["id"] for b in brands.list_brands()}
        brand_label = st.selectbox("Brand profile", list(brand_opts.keys()))
        char_label = st.selectbox("Character", list(CHARACTERS.keys()))
    with c2:
        platform = st.selectbox("Target platform", PLATFORMS)
        res_label = st.selectbox("Aspect ratio / resolution", list(RESOLUTIONS.keys()))
        no_audio_overlay = st.checkbox("Natural cinematic style (no VO or music overlays)", value=True)

    st.markdown("**Creative brief**  ·  describe the video and the campaign goal")
    brief = st.text_area("brief", value="", height=150, label_visibility="collapsed",
                         placeholder=EXAMPLE_BRIEF)
    with st.expander("💡 Example brief — click to use"):
        st.write(EXAMPLE_BRIEF)
        if st.button("Use this example"):
            st.session_state["_prefill"] = EXAMPLE_BRIEF
            st.rerun()
    if st.session_state.get("_prefill") and not brief:
        brief = st.session_state.pop("_prefill")

    mode = st.session_state.mode
    if mode == "DRY_RUN":
        mode_name = "Mock"
        est = "free · instant"
    elif mode == "LLM_ONLY":
        mode_name = "Live Creative"
        est = "live text/plan · free"
    else:
        mode_name = "Live Media"
        est = f"≈ ${pipeline.PROJECTED_SHOT_USD * 5:.2f} live render (5 shots)"
    st.caption(f"Mode: **{mode_name}**  ·  {est}")

    if st.button("✨  Generate video", type="primary", disabled=not brief.strip()):
        config = {
            "brand_id": brand_opts[brand_label],
            "character_id": CHARACTERS[char_label],
            "platform": platform,
            "aspect_ratio": RESOLUTIONS[res_label],
            "user_brief": brief.strip(),
            "mode": mode,
            "no_audio_overlay": no_audio_overlay,
        }
        create_conversation(config)
        st.rerun()


# ---------------------------------------------------------------------------
# Stepper (2-row: Planning → Shots → Final)
# ---------------------------------------------------------------------------
def stepper(conv):
    # Row 1: Planning segments
    plan_segs = [s for s in pipeline.SEGMENTS if not s.get("beat_id") and s["key"] != "composite_qa"]
    shot_segs = [s for s in pipeline.SEGMENTS if s.get("beat_id")]
    final_segs = [s for s in pipeline.SEGMENTS if s["key"] == "composite_qa"]

    # Planning row
    cols = st.columns(len(plan_segs) + len(shot_segs) + len(final_segs))
    all_segs = plan_segs + shot_segs + final_segs
    for i, seg in enumerate(all_segs):
        status = conv["status"][seg["key"]]
        cls = {"approved": "aw-done", "review": "aw-active", "running": "aw-active",
               "pending": "aw-pending", "error": "aw-error"}[status]
        badge = {"approved": "✓", "review": "●", "running": "⏳",
                 "pending": "○", "error": "⚠"}[status]
        # Compact labels for shots
        if seg.get("beat_id"):
            label = seg["beat_id"].capitalize()[:4]
        else:
            label = seg["label"].split(":")[0][:12]
        with cols[i]:
            st.markdown(
                f"<div class='aw-step {cls}'><div class='ic'>{seg['icon']}</div>"
                f"<div class='lb'>{label}</div><div>{badge}</div></div>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Per-segment review renderers
# ---------------------------------------------------------------------------
def view_script(conv, rp):
    if rp.get("product"):
        st.markdown(f"**🎯 Hero product** · {rp['product']}")
        if rp.get("key_selling_points"):
            st.caption("Selling points: " + " · ".join(rp["key_selling_points"]))
    cc = st.columns(3)
    cc[0].markdown(f"**Hook**\n\n{rp['hook'] or '—'}")
    cc[1].markdown(f"**Angle**\n\n{rp['angle'] or '—'}")
    cc[2].markdown(f"**CTA**\n\n{rp['cta'] or '—'}")
    st.markdown("**Script**")
    st.markdown(f"<div class='aw-brief'>{rp['script_text'] or '—'}</div>", unsafe_allow_html=True)
    meta = []
    if rp.get("duration_s"):
        meta.append(f"~{rp['duration_s']}s")
    if rp.get("brand_safety_score") is not None:
        meta.append(f"brand-safety {rp['brand_safety_score']}")
    if meta:
        st.caption("  ·  ".join(meta))


def view_visual(conv, rp):
    cc = st.columns(2)
    cc[0].markdown(f"**Wardrobe** · {rp['wardrobe'] or '—'}")
    cc[0].markdown(f"**Location** · {rp['location'] or '—'}")
    cc[1].markdown(f"**Hair** · {rp.get('hair_style') or '—'}")
    cc[1].markdown(f"**Makeup** · {rp.get('makeup') or '—'}")
    if rp.get("product_styling"):
        st.caption(f"Product styling: {rp['product_styling']}")
    st.markdown("**Beat-by-beat storyboard**")
    beats = rp.get("beats") or [{"beat_id": s["beat"], "camera": s["camera"],
                                 "dialogue_or_vo": "", "prompt": s["action"]}
                                for s in rp.get("scenes", [])]
    for b in beats:
        ost = f"<span class='aw-chip'>📝 {b.get('on_screen_text')}</span>" if b.get("on_screen_text") else ""
        pa = f"<br><b>Product:</b> {b.get('product_action')}" if b.get("product_action") else ""
        st.markdown(
            f"<div class='aw-beat'><span class='aw-chip'>{b.get('beat_id','')}</span>"
            f"<span class='aw-chip aw-chip-muted'>cam {b.get('camera','')}</span>"
            f"<span class='aw-chip aw-chip-muted'>{b.get('sync_mode','voiceover')}</span>{ost}<br>"
            f"<b>VO:</b> {b.get('dialogue_or_vo','') or '—'}{pa}<br>"
            f"<span class='aw-log'>{b.get('prompt','')[:260]}</span></div>",
            unsafe_allow_html=True)


def view_shot(conv, rp):
    """Render a single shot review card with ref frame, video, VQA scores, chain status."""
    beat_id = rp.get("beat_id", "")
    mode = conv["config"]["mode"]

    # -- Header: beat info + chain status --
    chain = rp.get("chain_status", "unknown")
    if chain == "chained":
        chain_badge = "<span class='aw-chip aw-chip-green'>🔗 Chained from prev</span>"
    elif chain == "anchored":
        chain_badge = "<span class='aw-chip aw-chip-amber'>🖼️ Imagen anchor</span>"
    else:
        chain_badge = "<span class='aw-chip aw-chip-muted'>? unknown</span>"

    st.markdown(
        f"<div class='aw-shot-header'>"
        f"<span class='aw-chip'>{beat_id.upper()}</span>"
        f"<span class='aw-chip aw-chip-muted'>cam {rp.get('camera','')}</span>"
        f"<span class='aw-chip aw-chip-muted'>{rp.get('sync_mode','')}</span>"
        f"{chain_badge}</div>",
        unsafe_allow_html=True)

    # Beat description
    if rp.get("dialogue_or_vo"):
        st.caption(f"**VO:** {rp['dialogue_or_vo']}")
    if rp.get("product_action"):
        st.caption(f"**Product:** {rp['product_action']}")

    # -- Reference frame + Video side by side --
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Reference Frame**")
        if rp.get("ref_frame_exists"):
            try:
                st.image(rp["ref_frame_uri"], caption=f"{beat_id} reference", use_container_width=True)
            except Exception:
                st.warning("Could not load reference frame image.")
        elif mode in ("DRY_RUN", "LLM_ONLY"):
            st.info("🧪 Mock mode — no image generated.")
        else:
            st.warning("Reference frame not available.")
            if rp.get("ref_frame_error"):
                st.caption(f"⚠ {rp['ref_frame_error']}")

    with c2:
        st.markdown("**Rendered Video**")
        video_status = rp.get("video_status", "")
        if rp.get("video_exists") and video_status in ("success", "mock"):
            st.video(rp["video_uri"])
        elif video_status == "mock":
            st.info(f"🧪 Mock clip: `{os.path.basename(rp.get('video_uri', ''))}`")
        elif video_status == "halted_budget":
            st.error("⚠ Halted — budget ceiling reached.")
        else:
            st.warning(f"Video not available (status: {video_status or 'pending'}).")
            if rp.get("video_error"):
                st.caption(f"⚠ {rp['video_error']}")

    # -- VQA Scores --
    if rp.get("vqa_overall") is not None:
        st.markdown("**VQA Scores**")
        mc = st.columns(4)
        mc[0].metric("Overall", f"{rp['vqa_overall']}/10")
        mc[1].metric("Ending State", f"{rp.get('vqa_ending_state', '—')}/10")
        mc[2].metric("Continuity", f"{rp.get('vqa_continuity', '—')}/10")
        mc[3].metric("Realism", f"{rp.get('vqa_realism', '—')}/10")

        if rp.get("vqa_defects"):
            with st.expander(f"⚠ {len(rp['vqa_defects'])} defect(s)"):
                for d in rp["vqa_defects"]:
                    st.markdown(f"- `sev {d.get('severity')}` **{d.get('type')}** — {d.get('description','')}")


def view_composite(conv, rp):
    """Render the final composite + QA review card."""
    # Master video
    uri = rp.get("final_uri")
    if rp.get("exists"):
        st.video(uri)
        cap = " · 📝 captions" if rp.get("captions_burned") else ""
        st.caption(f"Master cut · {rp.get('duration_s','?')}s · {conv['config']['aspect_ratio']}{cap}")
    elif conv["config"]["mode"] in ("DRY_RUN", "LLM_ONLY"):
        st.info("🧪 Mock / Creative mode — placeholder master. Switch to **Live Media** for real video.")
    elif rp.get("status") == "halted_budget":
        st.error("Render halted — budget ceiling reached.")
    else:
        st.warning(f"No master produced (status: {rp.get('status')}).")

    # Beat status row
    bs = rp.get("beat_status", {})
    if bs:
        cols = st.columns(len(bs))
        for i, (bid, sstat) in enumerate(bs.items()):
            ok = sstat in ("success", "mock")
            cols[i].markdown(f"<div class='aw-step {'aw-done' if ok else 'aw-error'}'>"
                             f"<div class='lb'>{bid}</div><div>{'✓' if ok else '⚠'}</div></div>",
                             unsafe_allow_html=True)

    # QA scores
    st.markdown("**Final QA Review**")
    cols = st.columns(8)
    for col, (k, label) in zip(cols, [("qa_overall", "Overall"), ("qa_realism", "Realism"),
                                      ("qa_brief_adherence", "Brief"), ("qa_product_visibility", "Product"),
                                      ("qa_lip_sync", "Lip-sync"), ("qa_audio", "Audio"),
                                      ("qa_continuity", "Identity"), ("qa_ending_state", "Ending")]):
        v = rp.get(k)
        col.metric(label, f"{v}/10" if v is not None else "—")

    verdict = "✅ Approved" if rp.get("qa_approved") else "⚠️ Needs work"
    st.markdown(f"**QA verdict:** {verdict}")
    if rp.get("qa_summary"):
        st.caption(rp["qa_summary"])
    for d in rp.get("qa_defects", []):
        st.markdown(f"- `sev {d.get('severity')}` **{d.get('type')}** @ {d.get('segment')} — "
                    f"{d.get('description','')}")


VIEWS = {
    "script": view_script,
    "visual_plan": view_visual,
    "composite_qa": view_composite,
}
# Add shot views
for _bid in pipeline.BEAT_IDS:
    VIEWS[f"shot_{_bid}"] = view_shot


# ---------------------------------------------------------------------------
# Segment card (transcript entry)
# ---------------------------------------------------------------------------
def segment_card(conv, seg_key, is_current):
    meta = pipeline.segment_meta(seg_key)
    status = conv["status"][seg_key]
    title = f"{meta['icon']}  {meta['label']}"

    # Non-current, approved → compact expander
    if not is_current and status == "approved":
        with st.expander(f"{title}  ·  ✓ approved", expanded=False):
            VIEWS[seg_key](conv, pipeline.review_payload(seg_key, conv["session"].state))
        return

    with st.container(border=True):
        st.markdown(f"#### {title}")

        if status == "error":
            st.error(f"This step failed: {conv.get('error')}")
            cc = st.columns(2)
            if cc[0].button("↻ Retry", key=f"retry_{seg_key}_{conv['id']}"):
                if seg_key.startswith("shot_") or seg_key == "composite_qa":
                    start_shot_bg(conv, seg_key)
                else:
                    run_sync(conv, seg_key)
                st.rerun()
            return

        VIEWS[seg_key](conv, pipeline.review_payload(seg_key, conv["session"].state))

        if status == "review" and is_current:
            hitl_actions(conv, seg_key)
        elif status == "approved":
            st.success("Approved")


def hitl_actions(conv, seg_key):
    """Approve / request-changes controls for the current segment under review."""
    st.divider()

    # Block approval if a shot render has failed
    disabled = False
    if seg_key.startswith("shot_"):
        bid = seg_key.replace("shot_", "")
        clip = conv["session"].state.get("beats", {}).get(bid, {})
        if clip.get("status") not in ("success", "mock"):
            disabled = True

    is_last = conv["stage_idx"] == len(pipeline.SEGMENT_KEYS) - 1
    next_label = "Finish ✓" if is_last else f"Approve → {pipeline.SEGMENTS[conv['stage_idx']+1]['label']}"
    c1, c2, _ = st.columns([1.3, 1.2, 2])

    if disabled:
        st.warning("⚠️ This shot failed to render successfully. You cannot approve it. Please click 'Retry' or 'Request changes' to get a successful render.")

    if c1.button(f"✅ {next_label}", key=f"appr_{seg_key}_{conv['id']}", type="primary", disabled=disabled):
        approve(conv, seg_key)
        st.rerun()

    with c2.popover("✏️ Request changes"):
        with st.form(f"mod_{seg_key}_{conv['id']}", clear_on_submit=True):
            fb = st.text_area("What should change?", height=90,
                              placeholder="e.g. make the lighting warmer, re-anchor the reference frame")
            submitted = st.form_submit_button("↻ Regenerate this step")
        if submitted and fb.strip():
            if seg_key.startswith("shot_") or seg_key == "composite_qa":
                start_shot_bg(conv, seg_key, feedback=fb.strip())
            else:
                modify_sync(conv, seg_key, fb.strip())
            st.rerun()


# ---------------------------------------------------------------------------
# Shot gate (LIVE_MEDIA — confirm before spending on each shot)
# ---------------------------------------------------------------------------
def shot_gate(conv, seg_key):
    mode = conv["config"]["mode"]
    meta = pipeline.segment_meta(seg_key)
    beat_id = meta.get("beat_id", "")

    with st.container(border=True):
        st.markdown(f"#### {meta['icon']}  {meta['label']}")
        st.write(f"Ready to render **{beat_id.capitalize()}**. This will generate a reference frame "
                 f"and render the video with Veo 3.1.")

        if mode == "LIVE_MEDIA":
            tracker = pipeline.DevSpendTracker()
            remaining = tracker.remaining()
            would = tracker.would_exceed(pipeline.PROJECTED_SHOT_USD)
            st.caption(f"Estimated **${pipeline.PROJECTED_SHOT_USD:.2f}** · "
                       f"budget remaining **${remaining:.2f}**")
            if would:
                st.error(f"This shot would exceed the ${tracker.CEILING_USD:.0f} dev-spend ceiling.")
            if st.button(f"🎬 Render {beat_id.capitalize()} (live)", type="primary", disabled=would,
                         key=f"shotgate_{seg_key}_{conv['id']}"):
                start_shot_bg(conv, seg_key)
                st.rerun()
        else:
            st.caption(f"{'🧪 Mock' if mode == 'DRY_RUN' else '🧠 Live Creative'} mode · free")
            if st.button(f"🎬 Render {beat_id.capitalize()}", type="primary",
                         key=f"shotgate_{seg_key}_{conv['id']}"):
                start_shot_bg(conv, seg_key)
                st.rerun()


# ---------------------------------------------------------------------------
# Shot/composite progress poller
# ---------------------------------------------------------------------------
def shot_progress(conv, seg_key):
    job_id = conv["shot_job_ids"].get(seg_key)
    job = jobs.get(job_id) if job_id else None
    meta = pipeline.segment_meta(seg_key)

    with st.container(border=True):
        st.markdown(f"#### {meta['icon']}  {meta['label']}")
        st.caption(meta["doing"])
        logs = (job.logs if job else conv["logs"].get(seg_key, []))[-10:]
        st.markdown(f"<div class='aw-log'>{'<br>'.join(logs) or 'starting…'}</div>",
                    unsafe_allow_html=True)
        if job:
            st.caption(f"⏱ {job.elapsed:.0f}s elapsed")

    if job is None:
        return
    if job.status == "running":
        time.sleep(1.3)
        st.rerun()
    elif job.status == "done":
        conv["logs"][seg_key] = job.logs
        conv["status"][seg_key] = "review"
        jobs.clear(job.id)
        st.rerun()
    elif job.status == "error":
        conv["logs"][seg_key] = job.logs
        conv["status"][seg_key] = "error"
        conv["error"] = job.error
        jobs.clear(job.id)
        st.rerun()


# ---------------------------------------------------------------------------
# Conversation view (main flow)
# ---------------------------------------------------------------------------
def conversation(conv):
    cfg = conv["config"]
    st.markdown(f"## {conv['title']}")
    mode_chip = 'Mock' if cfg['mode']=='DRY_RUN' else ('Live Creative' if cfg['mode']=='LLM_ONLY' else 'Live Media')
    st.markdown(
        f"<span class='aw-chip'>{brands.get_brand(cfg['brand_id']).brand_name}</span>"
        f"<span class='aw-chip aw-chip-muted'>{cfg['platform']}</span>"
        f"<span class='aw-chip aw-chip-muted'>{cfg['aspect_ratio']}</span>"
        f"<span class='aw-chip aw-chip-muted'>{mode_chip} mode</span>",
        unsafe_allow_html=True)
    st.markdown(f"<div class='aw-brief'>{cfg['user_brief']}</div>", unsafe_allow_html=True)
    st.write("")
    stepper(conv)
    st.write("")

    cur = pipeline.SEGMENT_KEYS[conv["stage_idx"]]
    cur_status = conv["status"][cur]
    mode = cfg["mode"]

    # Auto-run logic
    if cur_status == "pending":
        if cur in AUTO_RUN_PLANNING:
            with st.spinner(pipeline.segment_meta(cur)["doing"]):
                run_sync(conv, cur)
            cur_status = conv["status"][cur]
        elif cur in AUTO_RUN_FINAL:
            # Composite QA — run in background (may take time for QA loop)
            start_shot_bg(conv, cur)
            cur_status = conv["status"][cur]
        elif cur.startswith("shot_"):
            if mode in ("DRY_RUN", "LLM_ONLY"):
                # Fast mock — run inline
                with st.spinner(pipeline.segment_meta(cur)["doing"]):
                    run_sync(conv, cur)
                cur_status = conv["status"][cur]
            # LIVE_MEDIA: don't auto-run, show gate below

    # Draw transcript: every started segment up to and including the current one.
    for i in range(conv["stage_idx"] + 1):
        seg = pipeline.SEGMENT_KEYS[i]
        is_current = (i == conv["stage_idx"])

        if is_current and seg.startswith("shot_"):
            if conv["status"][seg] == "pending":
                shot_gate(conv, seg)
            elif conv["status"][seg] == "running":
                shot_progress(conv, seg)
            else:
                segment_card(conv, seg, is_current=True)
        elif is_current and seg == "composite_qa":
            if conv["status"][seg] == "running":
                shot_progress(conv, seg)
            else:
                segment_card(conv, seg, is_current=True)
        else:
            segment_card(conv, seg, is_current=is_current)

    # Completion → refine & regenerate composer.
    if cur == "composite_qa" and conv["status"]["composite_qa"] in ("review", "approved"):
        finished_composer(conv)


def finished_composer(conv):
    st.write("")
    with st.container(border=True):
        st.markdown("#### 🔁  Refine & regenerate")
        st.caption("Not quite right? Tweak the brief and regenerate the whole video in this "
                   "conversation.")
        new_brief = st.text_area("refine", value=conv["config"]["user_brief"], height=110,
                                  label_visibility="collapsed", key=f"refine_{conv['id']}")
        if st.button("✨ Regenerate full video", key=f"regen_{conv['id']}"):
            regenerate_full(conv, new_brief.strip() or conv["config"]["user_brief"])
            st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    init_state()
    sidebar()
    active = st.session_state.active
    if active and active in st.session_state.convs:
        conversation(st.session_state.convs[active])
    else:
        composer()


main()
