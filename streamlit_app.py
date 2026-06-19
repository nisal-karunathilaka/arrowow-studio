"""
Arrowow Studio — Studio Console (Streamlit)
===========================================

A ChatGPT/Gemini-style console for the autonomous UGC video factory. Each "conversation"
is one video production: pick a brand + character + platform + aspect ratio, write a
brief, and the multi-agent pipeline runs in five human-in-the-loop steps. You review and
approve (or request changes to) every step before it advances, then play the master cut
and, if needed, refine the brief and regenerate — all in the same conversation.

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
  .aw-brief { background:rgba(148,163,184,.08); border-left:3px solid #6366f1; padding:.7rem .9rem;
              border-radius:8px; font-size:.92rem; }
  .aw-beat { background:rgba(148,163,184,.06); border:1px solid rgba(148,163,184,.18);
             border-radius:10px; padding:.6rem .8rem; margin-bottom:.45rem; }
  .aw-log { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.74rem;
            color:#64748b; white-space:pre-wrap; }
  div[data-testid="stSidebarHeader"] { padding-bottom:0; }
</style>
""", unsafe_allow_html=True)

# Segments that run automatically (fast + cheap) when they become current.
# 'render' is gated behind an explicit button because it is the expensive step.
AUTO_RUN = {"script", "visual_plan", "reference_frame", "qa"}

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
        "render_job_id": None,
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


def start_render(conv, feedback=None):
    """Kick the long render/compose segment off into a background thread."""
    seg = "render"
    job_id = f"{conv['id']}:render:{int(time.time())}"
    conv["render_job_id"] = job_id
    conv["status"][seg] = "running"
    conv["error"] = None
    sess, mode = conv["session"], conv["config"]["mode"]

    async def factory(log):
        if feedback:
            await pipeline.regenerate_segment(seg, sess, mode, feedback, log)
        else:
            await pipeline.run_segment(seg, sess, mode, log)

    jobs.start(job_id, factory)


def approve(conv, seg):
    conv["status"][seg] = "approved"
    if conv["stage_idx"] < len(pipeline.SEGMENT_KEYS) - 1:
        conv["stage_idx"] += 1


def regenerate_full(conv, new_brief: str):
    """Refine the brief and regenerate the whole video in the SAME conversation."""
    conv["config"]["user_brief"] = new_brief
    pipeline._run_intake(conv["session"], conv["config"])  # refresh brief in shared state
    conv["session"].state["hitl_feedback"] = {}
    conv["stage_idx"] = 0
    conv["status"] = {k: "pending" for k in pipeline.SEGMENT_KEYS}
    conv["logs"] = {k: [] for k in pipeline.SEGMENT_KEYS}
    conv["render_job_id"] = None
    conv["error"] = None
    conv["history"].append({"brief": new_brief})
    conv["title"] = (new_brief[:42] + "…") if len(new_brief) > 42 else new_brief


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def sidebar():
    with st.sidebar:
        st.markdown("### 🎬 Arrowow Studio")
        st.caption("Autonomous UGC video factory")
        if st.button("＋  New video", use_container_width=True, type="primary"):
            new_blank_conv()
            st.rerun()

        st.divider()
        st.markdown("**Mode** (for new videos)")
        mode_label = st.radio(
            "mode", ["🧪 Mock  ·  free, instant", "🛰️ Live  ·  real render (paid)"],
            index=0 if st.session_state.mode == "DRY_RUN" else 1,
            label_visibility="collapsed")
        st.session_state.mode = "DRY_RUN" if mode_label.startswith("🧪") else "LIVE_MEDIA"
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
            if st.button(label, key=f"sel_{c['id']}", use_container_width=True):
                st.session_state.active = c["id"]
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
    est = "free · instant" if mode == "DRY_RUN" else f"≈ ${pipeline.PROJECTED_RENDER_USD:.2f} live render"
    st.caption(f"Mode: **{'Mock' if mode=='DRY_RUN' else 'Live'}**  ·  {est}")

    if st.button("✨  Generate video", type="primary", disabled=not brief.strip()):
        config = {
            "brand_id": brand_opts[brand_label],
            "character_id": CHARACTERS[char_label],
            "platform": platform,
            "aspect_ratio": RESOLUTIONS[res_label],
            "user_brief": brief.strip(),
            "mode": mode,
        }
        create_conversation(config)
        st.rerun()


# ---------------------------------------------------------------------------
# Stepper
# ---------------------------------------------------------------------------
def stepper(conv):
    cols = st.columns(len(pipeline.SEGMENTS))
    for i, seg in enumerate(pipeline.SEGMENTS):
        status = conv["status"][seg["key"]]
        cls = {"approved": "aw-done", "review": "aw-active", "running": "aw-active",
               "pending": "aw-pending", "error": "aw-error"}[status]
        badge = {"approved": "✓ done", "review": "● review", "running": "● working",
                 "pending": "○ pending", "error": "⚠ error"}[status]
        with cols[i]:
            st.markdown(
                f"<div class='aw-step {cls}'><div class='ic'>{seg['icon']}</div>"
                f"<div class='lb'>{seg['label']}</div><div>{badge}</div></div>",
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
    st.markdown("**Beat-by-beat**")
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


def view_frame(conv, rp):
    if rp["exists"]:
        st.image(rp["uri"], caption="Canonical anchor frame (identity lock)", width=360)
    elif conv["config"]["mode"] == "DRY_RUN":
        st.info("🧪 Mock mode — no image file is generated. Switch to **Live** to render the real anchor frame.")
    else:
        st.warning(f"Frame not available (status: {rp.get('status')}).")


def view_render(conv, rp):
    # Per-beat status row
    bs = rp.get("beat_status", {})
    if bs:
        cols = st.columns(len(bs))
        for i, (bid, sstat) in enumerate(bs.items()):
            ok = sstat in ("success", "mock")
            cols[i].markdown(f"<div class='aw-step {'aw-done' if ok else 'aw-error'}'>"
                             f"<div class='lb'>{bid}</div><div>{'✓' if ok else '⚠'}</div></div>",
                             unsafe_allow_html=True)
    uri = rp.get("final_uri")
    if rp.get("exists"):
        st.video(uri)
        cap = " · 📝 captions burned-in" if rp.get("captions_burned") else ""
        st.caption(f"Master cut · {rp.get('duration_s','?')}s · {conv['config']['aspect_ratio']}{cap}")
    elif conv["config"]["mode"] == "DRY_RUN":
        st.info("🧪 Mock mode — the pipeline ran end-to-end but produced placeholder clips "
                "(no real video). Switch to **Live** mode to render a playable master.")
    elif rp.get("status") == "halted_budget":
        st.error("Render halted — it would exceed the $100 dev-spend ceiling.")
    else:
        st.warning(f"No master produced (status: {rp.get('status')}).")


def view_qa(conv, rp):
    cols = st.columns(7)
    for col, (k, label) in zip(cols, [("overall", "Overall"), ("realism", "Realism"),
                                      ("brief_adherence", "Brief"), ("product_visibility", "Product"),
                                      ("lip_sync", "Lip-sync"), ("audio", "Audio"),
                                      ("continuity", "Identity")]):
        v = rp.get(k)
        col.metric(label, f"{v}/10" if v is not None else "—")
    verdict = "✅ Approved" if rp.get("approved") else "⚠️ Needs work"
    st.markdown(f"**QA verdict:** {verdict}")
    if rp.get("summary"):
        st.caption(rp["summary"])
    for d in rp.get("defects", []):
        st.markdown(f"- `sev {d.get('severity')}` **{d.get('type')}** @ {d.get('segment')} — "
                    f"{d.get('description','')}")


VIEWS = {"script": view_script, "visual_plan": view_visual, "reference_frame": view_frame,
         "render": view_render, "qa": view_qa}


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
                (start_render(conv) if seg_key == "render" else run_sync(conv, seg_key))
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
    is_last = conv["stage_idx"] == len(pipeline.SEGMENT_KEYS) - 1
    next_label = "Finish ✓" if is_last else f"Approve → {pipeline.SEGMENTS[conv['stage_idx']+1]['label']}"
    c1, c2, _ = st.columns([1.3, 1.2, 2])

    if c1.button(f"✅ {next_label}", key=f"appr_{seg_key}_{conv['id']}", type="primary"):
        approve(conv, seg_key)
        st.rerun()

    with c2.popover("✏️ Request changes"):
        with st.form(f"mod_{seg_key}_{conv['id']}", clear_on_submit=True):
            fb = st.text_area("What should change?", height=90,
                              placeholder="e.g. make the hook punchier and lead with the pain point")
            submitted = st.form_submit_button("↻ Regenerate this step")
        if submitted and fb.strip():
            if seg_key == "render":
                start_render(conv, feedback=fb.strip())
            else:
                modify_sync(conv, seg_key, fb.strip())
            st.rerun()


# ---------------------------------------------------------------------------
# Render-in-progress poller
# ---------------------------------------------------------------------------
def render_progress(conv):
    job = jobs.get(conv["render_job_id"])
    with st.container(border=True):
        st.markdown("#### 🎥  Render & Compose")
        st.caption(pipeline.segment_meta("render")["doing"])
        logs = (job.logs if job else conv["logs"]["render"])[-14:]
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
        conv["logs"]["render"] = job.logs
        conv["status"]["render"] = "review"
        jobs.clear(job.id)
        st.rerun()
    elif job.status == "error":
        conv["logs"]["render"] = job.logs
        conv["status"]["render"] = "error"
        conv["error"] = job.error
        jobs.clear(job.id)
        st.rerun()


# ---------------------------------------------------------------------------
# Render-gate card (explicit button before the paid render)
# ---------------------------------------------------------------------------
def render_gate(conv):
    mode = conv["config"]["mode"]
    with st.container(border=True):
        st.markdown("#### 🎥  Render & Compose")
        st.write("All planning steps are approved. Render the 5 beats on Veo 3.1, synthesize the "
                 "voiceover, and composite the master cut.")
        if mode == "LIVE_MEDIA":
            tracker = pipeline.DevSpendTracker()
            remaining = tracker.remaining()
            would = tracker.would_exceed(pipeline.PROJECTED_RENDER_USD)
            st.caption(f"Estimated **${pipeline.PROJECTED_RENDER_USD:.2f}** · "
                       f"budget remaining **${remaining:.2f}**")
            if would:
                st.error(f"This render would exceed the ${tracker.CEILING_USD:.0f} dev-spend ceiling. "
                         "Switch to Mock mode or raise the ceiling.")
            if st.button("🎬 Render video (live)", type="primary", disabled=would,
                         key=f"rndr_{conv['id']}"):
                start_render(conv)
                st.rerun()
        else:
            st.caption("🧪 Mock mode · free, instant (placeholder clips).")
            if st.button("🎬 Run render (mock)", type="primary", key=f"rndr_{conv['id']}"):
                start_render(conv)
                st.rerun()


# ---------------------------------------------------------------------------
# Conversation view
# ---------------------------------------------------------------------------
def conversation(conv):
    cfg = conv["config"]
    st.markdown(f"## {conv['title']}")
    st.markdown(
        f"<span class='aw-chip'>{brands.get_brand(cfg['brand_id']).brand_name}</span>"
        f"<span class='aw-chip aw-chip-muted'>{cfg['platform']}</span>"
        f"<span class='aw-chip aw-chip-muted'>{cfg['aspect_ratio']}</span>"
        f"<span class='aw-chip aw-chip-muted'>{'Mock' if cfg['mode']=='DRY_RUN' else 'Live'} mode</span>",
        unsafe_allow_html=True)
    st.markdown(f"<div class='aw-brief'>{cfg['user_brief']}</div>", unsafe_allow_html=True)
    st.write("")
    stepper(conv)
    st.write("")

    cur = pipeline.SEGMENT_KEYS[conv["stage_idx"]]
    cur_status = conv["status"][cur]

    # Auto-run fast current segments before drawing the transcript.
    if cur_status == "pending" and cur in AUTO_RUN:
        with st.spinner(pipeline.segment_meta(cur)["doing"]):
            run_sync(conv, cur)
        cur_status = conv["status"][cur]

    # Draw transcript: every started segment up to and including the current one.
    for i in range(conv["stage_idx"] + 1):
        seg = pipeline.SEGMENT_KEYS[i]
        is_current = (i == conv["stage_idx"])

        if is_current and seg == "render":
            if conv["status"]["render"] == "pending":
                render_gate(conv)
            elif conv["status"]["render"] == "running":
                render_progress(conv)
            else:
                segment_card(conv, seg, is_current=True)
        else:
            segment_card(conv, seg, is_current=is_current)

    # Completion → refine & regenerate composer.
    if cur == "qa" and conv["status"]["qa"] in ("review", "approved"):
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
