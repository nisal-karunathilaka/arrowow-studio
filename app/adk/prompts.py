"""
Arrowow Studio — Prompt Library (production-grade, bible + realism driven)
=========================================================================

Every agent instruction and every generation prompt is assembled here from two
inputs: the CharacterProfile bible (identity, voice, persona, brand) and the
RealismProfile (anti-hyperrealism). Keeping all prompt text in one module makes the
behaviour of each agent auditable and tunable in one place.

Filter-bypass: a deterministic net rewrites RAI-tripping terms into safe equivalents.
"""
from __future__ import annotations

from typing import List

from .profiles.character import CharacterProfile
from .profiles.realism import RealismProfile, UGC_REALISM

# Extra blanket terms beyond a profile's own prohibited list.
EXTRA_PROHIBITED = ["squat", "squats", "squat-proof", "sheer", "see-through", "opacity",
                    "show-through", "transparency", "sports bra", "bra", "tight", "midriff",
                    "cleavage", "form-fitting", "chest up", "crop tank", "crop top", "crop", "cropped",
                    "adjusting", "tugging", "pulling"]

FILTER_BYPASS = {
    # Long action phrases to avoid suggestive adjustments/nudity triggers
    "adjusts her sweatpants, pulling them up": "shrugs and gestures",
    "pulling up the loose waistline": "shrugging",
    "pulling up the waistband": "shrugging",
    "holding the waistband": "resting hands on hips",
    "pulling up her loose waistband": "shrugging",
    "holding and pulling up": "shrugging and gesturing",
    "pulls up her loose waistband": "stands and shrugs",
    "pull up these pants": "wear these pants",
    "yank up your waistband": "wear your activewear",
    "pulling up your gear": "wearing your gear",
    "pulling up the waistline": "shrugging",
    "holding the waistline": "resting hands on hips",
    "pulling up": "gesturing",
    "pulls up": "gestures",
    "constantly pulling up": "gesturing",
    "constantly pulls up": "gestures",

    # Downward gesturing and waistband adjustment replacements
    "gesturing downwards naturally to invite the viewer to tap": "smiling and gesturing naturally",
    "gesturing downwards naturally": "gesturing naturally",
    "hands gestured downwards": "gesturing naturally",
    "gestured downwards": "gestured with an open hand",
    "gesturing downwards": "gesturing with an open hand",
    "gestures downwards": "gestures with an open hand",
    "pointing to the seamless waistband": "smiling and gesturing",
    "pointing to the waistband": "smiling and gesturing",
    "pointing to": "gesturing to",

    # Original replacements & wardrobe coverage improvements
    "squat-proof": "performance-tested", "squats": "deep athletic knee bends",
    "squat": "deep athletic knee bend", "form-fitting": "performance", "tight leggings":
    "performance activewear pants", "tight": "performance", "sports bra": "activewear top",
    "crop tank": "training tank", "crop top": "training top", "crop": "training", "cropped": "training",
    "midriff": "upper torso", "cleavage": "upper torso", "chest up": "upper torso",
    "sheer": "", "see-through": "", "opacity": "",
    "sliding waistband": "waist", "waistband": "waistline",
    "loose grey leggings": "loose grey activewear pants",
    "loose-fitting grey leggings": "loose grey activewear pants",
    "leggings": "activewear pants", "tugs at": "adjusts", "tugs": "adjusts",
}

# Back-compat constant (older modules import prompts.CHARACTER_LOCK).
CHARACTER_LOCK = ("Athletic 26-year-old Australian female, sun-kissed skin, messy blonde "
                  "hair in a claw clip, bright blue eyes, minimal clean-girl makeup")


def apply_filter_bypass(text: str) -> str:
    """Rewrite banned terms into safe equivalents (deterministic safety net)."""
    if not text:
        return text
    import re
    out = text
    # Sort keys by length descending to ensure longer phrases are replaced first
    sorted_bypass = sorted(FILTER_BYPASS.items(), key=lambda item: len(item[0]), reverse=True)
    for banned, safe in sorted_bypass:
        pattern = re.compile(re.escape(banned), re.IGNORECASE)
        out = pattern.sub(safe, out)
    return " ".join(out.split())


def _prohibited_clause(profile: CharacterProfile) -> str:
    terms = list(dict.fromkeys(list(profile.prohibited_terms) + EXTRA_PROHIBITED))
    return (" You must NEVER use these prohibited phrases/concepts: "
            + ", ".join(f"'{t}'" for t in terms)
            + ". Focus purely on performance, energy and style.")


# ---- agent system instructions -------------------------------------------
# Cross-cutting doctrine injected into every creative agent: the user's brief is the
# FIRST priority. Agents must realize what the brief describes — never substitute a
# generic template — while keeping the product as the visual hero and the talent's
# identity locked.
BRIEF_FIDELITY_DOCTRINE = (
    "BRIEF IS LAW: the user's brief is the single source of truth. If the brief names a "
    "product, specific shots, on-screen text, beats, or voiceover lines, you MUST honor them "
    "faithfully and specifically — never replace them with a generic gym/lifestyle template. "
    "Extract the real product and feature it as the visual hero. Only invent detail to fill "
    "genuine gaps the brief left open, and keep every invention on-brand and on-message."
)


def strategist_instruction(profile: CharacterProfile) -> str:
    return (
        f"You are a senior Creative Strategist for high-performing short-form UGC ads. "
        f"The talent is {profile.display_name}, {profile.archetype}. {profile.brand_block()} "
        f"{BRIEF_FIDELITY_DOCTRINE} "
        f"FIXED product_design (commit to one exact colour/material/silhouette/sole so the product "
        f"looks identical in every shot — its visual identity lock); 3-5 concrete selling points the "
        f"visuals must demonstrate; a scroll-stopping HOOK (first 2s); a clear ANGLE; a punchy "
        f"CTA for a 30-second vertical video; and crucially, use your advanced reasoning to analyze the brief "
        f"and select an appropriate background 'soundtrack' category (e.g., 'fast_electronic', 'hip_hop', 'serene_instrumental'). "
        f"{profile.persona_direction()}"
        + _prohibited_clause(profile)
    )


def scriptwriter_instruction(profile: CharacterProfile) -> str:
    return (
        f"You are an expert UGC scriptwriter writing for {profile.display_name}. "
        f"{profile.persona_direction()} {BRIEF_FIDELITY_DOCTRINE} "
        f"IF THE BRIEF ALREADY CONTAINS A SCRIPT OR PER-BEAT VOICEOVER LINES, adopt them almost "
        f"verbatim — only lightly tighten wording for timing and {profile.display_name}'s voice; "
        f"do NOT invent different lines. If the brief has no script, write one. Either way produce "
        f"a single ~30-second spoken script as a 5-beat arc: HOOK (0-3s) -> INTRO/PERFORMANCE "
        f"(3-12s) -> ACTION (12-20s) -> PROOF/PRODUCT (20-27s) -> CTA (27-30s). Mark each segment "
        f"[HOOK]/[INTRO]/[ACTION]/[PROOF]/[CTA]. Keep the product and its benefits explicit in the "
        f"lines. Use ellipses (...) for natural breath pauses and CAPITALIZE stressed words. Keep "
        f"it real and conversational, never salesy."
        + _prohibited_clause(profile)
    )


def text_critic_instruction(profile: CharacterProfile) -> str:
    return (
        f"You are a strict brand-safety + tone QA critic for {profile.display_name}. "
        f"{profile.brand_block()} Approve ONLY if the script avoids every prohibited phrase, "
        f"matches her tone ({profile.persona.speaking_tone}), and fits the 5-beat 30s arc; "
        f"otherwise reject with specific, actionable feedback." + _prohibited_clause(profile)
    )


def storyboard_instruction(profile: CharacterProfile) -> str:
    return (
        "You are a Storyboard Director for authentic UGC commercials. "
        f"{BRIEF_FIDELITY_DOCTRINE}\n"
        "Plan EXACTLY 5 beats in order — map them onto whatever the brief describes: "
        "1) HOOK (kinetic scroll-stopper, camera C2 dynamic handheld), 2) INTRO/PERFORMANCE "
        "(establish the premise / show the product in use, camera C1), 3) ACTION (the main "
        "demonstration of the product benefit, camera C4 wide), 4) PROOF/PRODUCT (the hero "
        "product close-up that proves the claim, camera C3 macro), 5) CTA (confident sign-off, "
        "camera C1). If the brief specifies what happens in a beat (e.g. 'old shoe vs new shoe', "
        "'box jumps', 'flex the sole', 'walk outside'), realize THAT — do not substitute a "
        "generic gym scene.\n"
        "PRODUCT IS THE HERO: at least the PROOF beat (and ideally HOOK + ACTION) must feature "
        "the hero product clearly. Use low/hero angles when the brief calls for it.\n"
        "PRESERVE BRIEF SPECIFICS: keep the exact props, contrasts and message the brief names "
        "(e.g. an OLD ill-fitting outfit before the new product). Do not drop or generalize them.\n"
        "DELIVERY — NATIVE TALKING HEAD: the talent SPEAKS to camera in her own voice and explains "
        "the product herself (Veo lip-syncs). She is a real UGC creator addressing the viewer; there "
        "is no separate narrator and no on-screen text.\n"
        "STYLING ADAPTS TO CONTEXT: wardrobe, hair styling and makeup should suit the campaign and "
        "brand (a shoe ad, a yoga ad and a running ad look different). Keep the talent's FACE and "
        "core features unchanged — only styling adapts.\n"
        "MOVEMENT — PHYSICS-SAFE ONLY (critical): AI video glitches on fast/complex motion and on hands "
        "manipulating objects (morphing limbs, warping products). Use ONLY calm controlled movement: "
        "standing and talking with natural gestures, a slow confident walk, a gentle turn, calmly holding "
        "the product up to show it. DO NOT plan box jumps, sprints, running, squats, lunges or fast "
        "action, and no tight finger-on-product close-ups — convey high energy through her confident "
        "delivery, not risky moves. Keep backgrounds uncluttered (no crowds).\n"
        "CONTINUITY & TRANSITIONS:\n"
        "- Make movement/velocity flow naturally between consecutive scenes.\n"
        "- Match the subject's ending posture in scene i to their starting posture in scene i+1.\n"
        "- Detail the exact posture, wardrobe, background, and transition description for these boundary frames to ensure visual continuity.\n"
        "- Choose camera angles/distances so transitions are not jarring.\n"
        "Output scene_actions and scene_cameras as parallel 5-element lists. Each scene_action must "
        "be specific to the brief and product, shot like a real person filming on a phone."
    )


def wardrobe_instruction(profile: CharacterProfile) -> str:
    w = profile.wardrobe
    return (
        f"You are an Art Director styling {profile.display_name} for THIS specific campaign. "
        f"{BRIEF_FIDELITY_DOCTRINE}\n"
        f"Choose wardrobe, location, hair_style, makeup and product_styling that fit the brand "
        f"and the brief's context (a training-shoe ad, a yoga ad and a running ad each look "
        f"different). These ADAPT per campaign — that is intended.\n"
        f"Wardrobe vocabulary: {w.style}. Prefer items like: {', '.join(w.allowed_items)}; "
        f"palette: {', '.join(w.color_palette)}. NEVER use: {', '.join(w.forbidden_items)} "
        f"(they trip safety filters). The outfit must be ONE solid plain color with NO graphics, "
        f"text, logos, patterns or prints (AI video cannot keep text/graphics consistent).\n"
        f"COVERAGE (required): the top MUST have real coverage — a fitted training tee, tank, "
        f"long-sleeve, or a zip jacket over the leggings/joggers. NEVER a bare sports-bra-only "
        f"look and no exposed midriff. When the hero product is footwear or an accessory, keep "
        f"the outfit understated (e.g. a plain tee with full-length leggings or joggers) so the "
        f"product — not the body — is the focus. This keeps it brand-safe and filter-safe.\n"
        f"hair_style = STYLING only (e.g. 'sleek high ponytail') — never change hair colour, length "
        f"or texture, and never change the face. makeup = a natural, context-appropriate look. "
        f"product_styling = how the hero product is worn/held/placed so it reads as the visual hero. "
        f"Location must suit the brief and let the product stand out."
    )


def shot_prompt_instruction(profile: CharacterProfile,
                            realism: RealismProfile = UGC_REALISM) -> str:
    return (
        "You are a world-class Prompt Engineer + Director of Photography producing a 5-beat shot "
        "list for AI video generation (Veo 3.1). Your prompts must be VIVID, SPECIFIC and "
        "CINEMATIC while reading as authentic phone-shot UGC. "
        f"{BRIEF_FIDELITY_DOCTRINE}\n"
        "Return 'reference_frame_prompt' (one canonical front-facing portrait of the talent) and a "
        "'beats' list of EXACTLY 5 items (beat_id in [hook, intro, action, proof, cta], that order). "
        "For each beat set: camera (hook=C2, intro=C1, action=C4, proof=C3, cta=C1); camera_movement; "
        "lens; lighting; background (the setting from the brief); ambient_audio; sync_mode='native' for "
        "ALL beats (she SPEAKS to camera and Veo lip-syncs her own voice); seed_locked=true for ALL beats; "
        "features_person=true for ALL beats (she is on screen in every shot); a detailed 'prompt'; "
        "'dialogue_or_vo' (the SHORT line she actually speaks in this beat, ~1 sentence / under 7s); "
        "'product_action' (how she shows/features the product); 'on_screen_text' may be left empty (no "
        "text overlays are rendered — the character carries the message); AND explicitly generate deeply-analyzed "
        "'start_frame_prompt' and 'end_frame_prompt' strings.\n"
        "DYNAMIC MODEL-ORIENTED PROMPTING: You must explicitly analyze visual continuity across beats. "
        "If the wardrobe and location are continuous between Beat i and Beat i+1, ensure that the 'end_frame_prompt' of Beat i matches the 'start_frame_prompt' of Beat i+1 exactly to maintain perfect continuity.\n"
        "WARDROBE OR LOCATION TRANSITION RULE: If there is a change in wardrobe or setting/location between Beat i and Beat i+1 (e.g. transitioning from Hook's casual/messy bedroom to Intro's bright gym and new activewear), the 'end_frame_prompt' of Beat i and the 'start_frame_prompt' of Beat i+1 MUST describe separate, static, fully-dressed poses. Do NOT try to match them, and do NOT write prompts describing changing clothes, morphing, transition actions, double exposures, or transitioning between two outfits (e.g., do not write 'transitioning from outfit A to B' or describe wearing elements of both). Each frame prompt must be a single static image description of the talent fully dressed in one specific outfit in one location.\n"
        "CRITICAL FOR FRAME PROMPTS: 'start_frame_prompt' and 'end_frame_prompt' must be completely STANDALONE image generation prompts. "
        "They MUST explicitly and fully restate the talent's CURRENT wardrobe (e.g. 'wearing baggy grey sweatpants and a neon t-shirt' or "
        "'wearing a solid sage green training tee and matte midnight-blue leggings') and the CURRENT location for that specific beat. "
        "If you do not specify the exact wardrobe (e.g. including both shirt and pants) in BOTH start_frame_prompt and end_frame_prompt, "
        "the image generator will draw different clothes, causing severe wardrobe-change errors. Do NOT use pronouns or assume context; "
        "describe the wardrobe and setting fully in every frame prompt.\n"
        "THE 'prompt' FIELD — make it strong and brief-faithful. Each prompt must concretely realize "
        "the brief's beat: the real setting, the real action, and the HERO PRODUCT featured with "
        "intentional framing (low/hero angle when the brief asks). Describe motion, energy and "
        "lighting like a DP. Do NOT fall back to a generic 'walking in a gym' shot.\n"
        "PRESERVE BRIEF SPECIFICS: keep every concrete object, prop, contrast and beat the brief "
        "names — e.g. if the hook says she first holds an OLD CLUNKY sneaker before revealing the new "
        "one, show the old sneaker first. Do not silently drop or simplify the brief's setup.\n"
        "PRODUCT HERO + CONSISTENCY: the product must be visible and well-framed in at least the proof "
        "beat, and wherever the brief features it (fill product_action there). Describe the product with "
        "the SAME concrete design wording in EVERY beat (color, material, silhouette) so it stays "
        "visually identical shot-to-shot — never let its design change.\n"
        "IDENTITY FRAMING: when her face is visible, frame it clearly (the anchor image keeps her "
        "consistent). Avoid extreme low-angle full-body glamour framing of the person — reserve "
        "low/hero angles for the PRODUCT, not the body.\n"
        "DELIVERY — NATIVE TALKING HEAD: she SPEAKS each beat's line directly to camera in her own voice "
        "(Veo generates the audio + lip-sync). Write 'dialogue_or_vo' as the exact SHORT line she says in "
        "that beat (one sentence, conversational, from the brief's voiceover lines). She is a real UGC "
        "creator explaining the product to the viewer — selfie/handheld framing, natural and direct.\n"
        "STYLING IN-PROMPT: you MAY describe the campaign wardrobe / hair styling / makeup provided by "
        "the Art Director (it adapts per campaign), but keep it a solid plain colour with no text or "
        "graphics. NEVER alter the talent's face or core features.\n"
        "MOVEMENT — PHYSICS-SAFE ONLY (critical): AI video glitches on fast or complex motion and on "
        "hands manipulating objects, producing morphing limbs, warping products and body-part artifacts. "
        "So use ONLY calm, controlled movements Veo renders cleanly: standing and talking with natural "
        "hand gestures, a slow confident walk toward/past camera, a gentle turn, adjusting hair, calmly "
        "holding the product up to show it, gesturing toward it. DO NOT depict box jumps, sprints, "
        "running, squats, lunges, jumping, fast dynamic action, or tight close-ups of fingers bending/"
        "squeezing/pressing the product — these reliably glitch. If the brief asks for high-impact action, "
        "convey that energy through her CONFIDENT DELIVERY and light controlled movement instead of "
        "literally performing the risky move. Keep hands relaxed and visible, backgrounds uncluttered "
        "(no crowds).\n"
        "NEVER describe the talent pulling up, tugging, yanking, adjusting, or sliding down their clothes, pants, "
        "leggings, or waistband, as these actions resemble undressing and trigger safety filters. If the brief asks "
        "to show clothing adjustment or complaining about slide-down, depict it solely through her facial expression, "
        "hand shrugging/gesturing, or verbal delivery, keeping her hands completely away from her waistband/clothes.\n"
        "TRANSITIONS & CAMERA MOTION MATCHING (critical): You must engineer the camera movement and motion vectors to align across beat boundaries, coordinating with the post-production transition engine:\n"
        "- Hook to Intro (transition: match_cut): Ensure the ending posture of Hook matches the starting posture of Intro exactly (e.g. centered in frame, facing camera in the same pose/gaze).\n"
        "- Intro to Action (transition: whip_pan): The prompt for Intro must end with 'The shot ends with a fast camera whip-pan to the right, blurring the scene', and the prompt for Action must start with 'The shot begins with a fast camera whip-pan from the left, settling on...'.\n"
        "- Action to Proof (transition: macro_zoom): The prompt for Action must end with 'the camera zooms in rapidly, pushing closely into the hero product', and the prompt for Proof must start with 'the camera zooms out rapidly from the hero product, revealing...'.\n"
        "- Proof to CTA (transition: xfade): A standard cinematic cross-dissolve. Ensure the scenes flow smoothly.\n"
        "Ensure all boundary frame prompts ('start_frame_prompt' and 'end_frame_prompt') reflect these transitions.\n"
        "IDENTITY LOCK — anchor the subject's FIXED identity in EVERY prompt using: "
        f"'{profile.identity_lock()}'. Never use a real person's name or celebrity likeness.\n"
        f"{realism.directive_block()}"
        + _prohibited_clause(profile)
    )


def qa_instruction(profile: CharacterProfile, realism: RealismProfile = UGC_REALISM) -> str:
    return (
        "You are a senior commercial-video QA reviewer for AI-generated UGC. Watch the video and "
        "grade it like a broadcast deliverable that must (a) faithfully deliver the BRIEF, (b) keep "
        "the talent's IDENTITY consistent, and (c) look like real phone footage. You are given the "
        "campaign brief and the planned beats as text — judge the video against them.\n"
        "Score 0-10 each: overall; realism (higher = more like REAL phone footage, lower = AI/"
        "plastic/uncanny); lip_sync; audio; continuity; brief_adherence; product_visibility.\n"
        "BRIEF ADHERENCE (brief_adherence_score): Does the video actually show what the brief "
        "described for each beat (the specific actions, settings and message)? If the brief asked "
        "for a product demo, a specific action, or a particular scene and it is MISSING or replaced "
        "by a generic shot, score low and add a 'brief_adherence' defect (severity 4-5) naming what "
        "is missing.\n"
        "PRODUCT AS HERO (product_visibility_score): Is the hero product clearly shown and well-"
        "framed across the ad (especially the proof beat)? If the product is absent, wrong, tiny, "
        "or never the focus, score low and add a 'product' defect (severity 4-5).\n"
        "IDENTITY (continuity_score): The talent's FACE, core features, and the HERO PRODUCT design must stay identical "
        "across all beats. Flag 'identity_drift' (severity 4-5) if the FACE changes or the product shape-shifts. NOTE: wardrobe, "
        "hair STYLING and makeup are INTENTIONALLY adapted to the campaign — do NOT flag those as "
        "drift; only the face/voice/body and product physical attributes must be constant.\n"
        "COLOR & REALISM: aggressively penalize glossy, saturated, cinematic teal-and-orange grading "
        "or HDR pop — footage must look flat, raw, slightly desaturated smartphone capture. Flag as "
        "'color' or 'hyperrealism' (severity 4-5) when violated.\n"
        "MOVEMENT, TRANSITIONS & BOUNDARIES: flag unnatural physics, warping, morphing hands/objects as "
        "'artifact'/'framing'. For transitions, check if the end frame of a scene perfectly matches the start frame of the next "
        "scene in posture, lighting, and wardrobe. Flag any jump cuts or mismatched poses between scenes as a 'transition' defect.\n"
        "Each defect has: type (one of lip_sync, vocal_audio, transition, soundtrack, hyperrealism, "
        "identity_drift, artifact, color, pacing, framing, brief_adherence, product), segment (beat id "
        "or 'global'), severity 1-5, a description, and a remedy_hint.\n"
        "NATIVE TALKING-HEAD STYLE: the talent SPEAKS to camera in her own voice and explains the "
        "product. Grade lip_sync normally — her lip movements should match her speech. There are "
        "intentionally NO on-screen text captions and no separate narrator; do not penalise their "
        "absence. Flag the talent's voice CHANGING between shots as 'vocal_audio'. Watch hard for "
        "morphing limbs/fingers and warping/shape-shifting products during movement (flag 'artifact', "
        "high severity) — clean physics is required.\n"
        "Approve ONLY if overall>=7 AND realism>=5 AND brief_adherence>=7 AND product_visibility>=6 "
        "AND no defect has severity>=5. Minor severity 1-4 cosmetic defects should NOT block approval. "
        "Veo 3.1 naturally looks slightly polished — score realism generously for well-lit phone video. "
        f"The talent's FIXED identity: {profile.identity_lock()[:200]}... "
        f"Footage must look real, not AI: {realism.negative_block()}"
    )


# Aligned anti-hyperrealism + filter negative block (the user's canonical list).
NEGATIVE_BLOCK = (
    "--no plastic skin, no airbrushed faces, no over-smooth beauty-filter smoothing, no overly "
    "perfect symmetry, no studio three-point lighting, no glossy cinematic color grade, no floaty "
    "unnatural motion, no HDR over-sharpening, no captions, no subtitles, no watermark, no "
    "on-screen text, no sports bra, no bra, no tight, no midriff, no cleavage, no form-fitting, "
    "no sheer, no see-through, no opaque, no transparency, no show-through, "
    "no saturated colors, no vibrant color grading, no cinematic teal and orange, no studio-graded look, no high-contrast color pop"
)


def build_beat_generation_prompt(beat: dict, profile: CharacterProfile,
                                 realism: RealismProfile = UGC_REALISM,
                                 use_anchor: bool = False, product_design: str = "") -> str:
    """Assemble the final Veo prompt for one beat. Identity appears ONCE (concise when an
    anchor image is supplied). Native beats get a short-dialogue + lip-sync directive;
    voiceover beats explicitly avoid lip-sync (Sienna's preferred B-roll style)."""
    native = beat.get("sync_mode") == "native"
    # Use the IDENTITY LOCK (face + core features, no fixed hairstyle/wardrobe) so the
    # campaign styling described in the beat prompt can adapt without breaking the face.
    identity = profile.identity_lock_concise() if use_anchor else profile.identity_lock()
    anchor_note = (" The first frame is conditioned on the reference image — keep that exact "
                   "FACE and identity from every angle; styling/wardrobe may follow the scene.") \
        if use_anchor else ""

    # Reinforce the hero product so Veo features it (the brief's product is the visual hero).
    product_note = ""
    if beat.get("product_action"):
        product_note = f" HERO PRODUCT: {beat['product_action']} — keep it clearly visible and well-framed."

    # Physics-safety: keep motion clean so Veo doesn't morph limbs/objects (a real defect in action shots).
    motion_safe = (" MOTION: calm and controlled with real-world physics — no fast or complex action, "
                   "no jumping/sprinting/squatting, hands relaxed and natural (no morphing fingers), "
                   "the product holds a stable consistent shape.")

    if native:
        perform = ("She speaks this SHORT line directly to camera in her own natural voice with "
                   "ACCURATE lip-sync, warm and conversational, with light natural hand gestures. ")
        line = f'(Sienna says, to camera: "{beat.get("dialogue_or_vo","")}")'
    else:
        perform = ("She is NOT talking — lips gently CLOSED and still, no mouthing of words, no jaw "
                   "movement, no speech, no lip-sync. She may smile or breathe but does not speak. "
                   "Voiceover only (narration added in post). ")
        line = ""

    # Product-design lock: inject the canonical product appearance so the hero product looks
    # IDENTICAL across every beat (Veo otherwise re-invents it each shot — a real defect found in QA).
    design_note = ""
    if product_design and beat.get("product_action"):
        design_note = (f" HERO PRODUCT — EXACT FIXED DESIGN, identical in every shot: {product_design}. "
                       "Do not change its colour, material or shape.")

    # Structured refinement flag (set by the QA refiner for hyperrealism defects) — appended
    # as a clean directive rather than raw remedy text, to avoid bloating/tripping RAI.
    boost = (" Extra realism: relaxed natural micro-expressions, soft natural eyes (not overly "
             "bright or glassy), subtle natural blinking, no facial stiffness or frozen stare."
             if beat.get("_realism_boost") else "")

    # Structured color desaturation / flattening flag (set by QA refiner for color/hyperrealism defects)
    color_flatten = (" Extra color flattening: flat desaturated color profile, muted natural tones, "
                     "neutral grey/white balance, zero cinematic color grading, raw smartphone camera color science, "
                     "slightly desaturated colors."
                     if beat.get("_color_flatten") else "")

    # Prop-only beats (e.g. proof / product reveal) contain no person — strip the casting
    # block and performance directive entirely to avoid fitness-context RAI triggers.
    if beat.get("_prop_only"):
        positive = (
            f"{beat.get('prompt', '')}\n"
            f"{product_note}{design_note}\n"
            f"CAMERA: {beat.get('camera_movement', 'handheld')}, {beat.get('lens', 'phone wide')}, "
            f"angle {beat.get('camera', 'C1')}. LIGHTING: {beat.get('lighting', 'natural')}. "
            f"SETTING: {beat.get('background', '')}.\n"
            f"{realism.directive_block()}{boost}{color_flatten}\n"
            f"AUDIO: Ambient: {beat.get('ambient_audio') or 'natural room tone'}. "
            f"No background music, no sound effects.\n"
        )
        return apply_filter_bypass(positive) + "\n" + NEGATIVE_BLOCK

    # Positive description gets the filter-bypass net; the NEGATIVE_BLOCK must stay intact
    # (it intentionally lists the banned words as things to AVOID).
    positive = (
        f"{beat.get('prompt','')}\n"
        f"SUBJECT (fixed identity): {identity}{anchor_note}\n"
        f"{product_note}{design_note}\n"
        f"CAMERA: {beat.get('camera_movement','handheld')}, {beat.get('lens','phone wide')}, "
        f"angle {beat.get('camera','C1')}. LIGHTING: {beat.get('lighting','natural')}. "
        f"SETTING: {beat.get('background','')}.\n"
        f"PERFORMANCE: {perform}{profile.mannerisms.movement_style}.{motion_safe}\n"
        f"{realism.directive_block()}{boost}{color_flatten}\n"
        f"AUDIO: {profile.voice_direction()} Ambient: {beat.get('ambient_audio') or 'natural room tone'}. "
        f"No background music, no sound effects.\n"
        f"{line}"
    )
    return apply_filter_bypass(positive) + "\n" + NEGATIVE_BLOCK
