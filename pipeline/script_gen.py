import os
import json
import random
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ── OpenRouter model config (hardcoded) ──────────────────────────────
_OPENROUTER_PRIMARY_MODEL = "google/gemini-2.5-flash"
_OPENROUTER_FALLBACK_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.0-pro-exp-02-05:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def _get_content_language():
    return (os.getenv("CONTENT_LANGUAGE") or "hindi").strip().lower()

def _normalize_content(content):
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        content = "\\n".join(parts)

    text = str(content or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
def _call_gemini_api(prompt, model):
    """Call Google Gemini API. Returns response text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1200
        }
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError(f"Unexpected Gemini API response format: {data}")

def _llm_prompt(prompt):
    """Call LLM via Google Gemini API directly (100% free tier)."""
    models_to_try = ["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    last_error = None

    for model in models_to_try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[Gemini API] Using model: {model} (attempt {attempt + 1})")
                raw = _call_gemini_api(prompt, model)
                return _normalize_content(raw)
            except Exception as exc:
                error_str = str(exc)
                last_error = exc
                if "429" in error_str or "rate" in error_str.lower():
                    wait_time = 15 * (attempt + 1)
                    print(f"[Gemini API] Rate limit on {model}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                # Non-rate-limit error — skip to next model
                print(f"[Gemini API] {model} failed: {exc}. Trying next model...")
                break

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")



def _extract_json_block(text):
    content = str(text or "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start : end + 1]
    return content


def _parse_script_payload(raw_text):
    payload = json.loads(_extract_json_block(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Script payload is not a JSON object")
    if "scenes" not in payload or not isinstance(payload["scenes"], list):
        raise ValueError("Script payload missing list field: scenes")
    if len(payload["scenes"]) == 0:
        raise ValueError("Script payload contains 0 scenes")
    return payload


def _repair_script_json(raw_text, error_message):
    prompt = f"""
You must fix malformed JSON and return valid JSON only.

Rules:
- Keep the same schema with fields: title, scenes[].id, scenes[].text, scenes[].visual_keyword, scenes[].visual_mood
- Do not add markdown fences.
- Escape quotes correctly.
- Ensure valid commas and brackets.

Previous parser error:
{error_message}

Malformed content:
{raw_text}
"""
    return _llm_prompt(prompt)


def _normalize_scene_text(text):
    """Collapse line breaks/extra spaces so TTS reads each scene as one continuous thought."""
    return " ".join(str(text or "").replace("\n", " ").split())


def _postprocess_script_payload(payload):
    scenes = payload.get("scenes", [])
    for scene in scenes:
        if isinstance(scene, dict):
            scene["text"] = _normalize_scene_text(scene.get("text", ""))
            scene["visual_keyword"] = str(scene.get("visual_keyword", "")).strip()
            scene["visual_mood"] = str(scene.get("visual_mood", "neutral")).strip()
    return payload


# ── Hook framework rotation for maximum variety ──────────────────────
_HOOK_FRAMEWORKS = [
    {
        "name": "curiosity_gap",
        "instruction": "Start with an incomplete statement that creates burning curiosity. Example pattern: 'Ye cheez ladkiyan kabhi nahi bolti, lekin...' — leave the answer dangling so viewer MUST watch.",
    },
    {
        "name": "shock_stat",
        "instruction": "Open with a surprising statistic or psychological fact that sounds unbelievable. Example pattern: '90% ladkiyan ye secretly karti hain...' — make the number feel exclusive and secret.",
    },
    {
        "name": "challenge",
        "instruction": "Challenge the viewer's beliefs directly. Example pattern: 'Tum galat sochte ho attraction ke baare mein...' — create a 'prove me wrong' urge.",
    },
    {
        "name": "story_open",
        "instruction": "Start mid-story as if catching someone in the act. Example pattern: 'Jab ek ladki baar baar ye karti hai toh samajh jaao...' — make it feel like a real moment.",
    },
    {
        "name": "controversial_take",
        "instruction": "Lead with a bold, polarizing opinion. Example pattern: 'Acche ladke kabhi attract nahi karte, aur reason ye hai...' — force the viewer to pick a side.",
    },
    {
        "name": "warning_hook",
        "instruction": "Start with a direct warning that creates immediate suspense. Example pattern: 'Agar tum akele ho toh ye video mat dekhna...' or 'Ye sach sunne ke baad tum darr jaoge...'",
    },
    {
        "name": "dark_mystery",
        "instruction": "Open with an unsolved mystery or creepy phenomenon. Example pattern: 'Duniya ki sabse rahasyamayi jagah jahan se koi wapas nahi aaya...' or 'Ye creepy fact tumhe sone nahi dega...'",
    },
    # ── PROVEN VIRAL FRAMEWORK — HIGHEST PERFORMER (2.4K+ views) ──
    {
        "name": "kabhii_nahi",
        "instruction": """
This is the PROVEN highest-performing hook framework on this account (drove 2.4K views).
Open with an incomplete 'kabhi nahi...' statement in Devanagari Hindi.
The sentence MUST be cut off mid-thought so the screen text ends with '...' ellipsis.
This creates an involuntary open loop — the brain literally cannot scroll away without completing the sentence.
Pattern structure:
  Line 1 (on screen): 'लड़कियां कभी सीधे नहीं बतातीं...' (cut off — the '...' is the scroll stopper)
  Narration: Continue the thought — reveal WHAT they never say directly and WHY.
Examples of proven-viral openers:
  - 'ये चीज़ लड़कियां कभी नहीं...'
  - 'लड़कियां कभी सीधे नहीं बतातीं...'
  - 'वो signal जो ladkiyan kabhi...'
MANDATORY: The very first scene text must end with '...' to create the open loop on screen.""",
    },
    {
        "name": "test_format",
        "instruction": """
This is the PROVEN second-highest hook framework — 'Test' framing (drove the 2.4K views reel).
Frame the entire reel as a test or quiz the viewer can take.
Pattern: 'Friendzone Test: Spot It Or Stay Stuck?' or '[Topic] Test: [Outcome if you fail]'
This forces the viewer to COMPLETE the video to get their 'result'.
High completion rate = algorithm pushes it further.
First sentence must name the test and its stakes.
Example: 'Ye [topic] test fail kiya toh [consequence] rahoge forever!'""",
    },
]


def _pick_hook_framework(analytics_data=None, feedback_summary=""):
    """Choose a hook framework with a healthy balance to prevent audience fatigue.
    
    Instead of spamming the top 2 hooks 100% of the time, we give the top
    performers a slight bump, but ensure all frameworks rotate evenly.
    """
    proven_viral = ["kabhii_nahi", "test_format", "curiosity_gap"]
    
    # 30% of the time, force one of the proven viral hooks
    if random.random() < 0.30:
        preferred_name = random.choice(proven_viral)
        for framework in _HOOK_FRAMEWORKS:
            if framework["name"] == preferred_name:
                return framework

    # 70% of the time, completely random rotation for variety
    return random.choice(_HOOK_FRAMEWORKS)


def generate_script(topic, analytics_data=None, feedback_summary=""):
    """Generates a highly viral, SHORT video script optimized for completion rate."""
    language = _get_content_language()
    language_rules = """
    Language rules:
    - Narration text MUST be in pure Hindi using STRICTLY Devanagari script (e.g. "लड़कियां" NOT "ladkiyan").
    - DO NOT use Roman/Latin letters for the narration text. This is a hard requirement.
    - Keep pronunciation natural for Hindi TTS.
    - CRITICAL: The `title` MUST be in English or Roman Hinglish. NEVER use Devanagari script in the `title`.
    """ if language in {"hindi", "hi", "hi-in"} else ""

    # Check if this is a continuation part and retrieve the previous script to ensure continuity
    previous_script_context = ""
    try:
        from pipeline.feedback_loop import get_previous_part_script
        prev_script = get_previous_part_script(topic)
        if prev_script:
            scenes_text = "\n".join(
                f"  Scene {s.get('id', idx)}: {s.get('text', '')}"
                for idx, s in enumerate(prev_script.get("scenes", []), 1)
            )
            previous_script_context = f"""
    ══ PREVIOUS PART SCRIPT (CONTAINS CONTEXT FROM PART 1 / PART 2) ══
    This reel is a direct continuation of the previous part.
    Here is the exact script narration from the PREVIOUS part:
    {scenes_text}
    ═════════════════════════════════════════════════════════════════
    CRITICAL INSTRUCTIONS FOR THIS SEQUEL SCRIPT:
    1. Your new script MUST continue the story, signs, logic, or advice directly from the previous part.
    2. DO NOT repeat the same tips, signs, or facts. The audience wants to learn the next steps.
    3. Ensure the transition between the parts feels continuous and logical.
    """
            print(f"[Series] Sequenced continuation detected! Injected previous script context (length: {len(scenes_text)}).")
    except Exception as e:
        print(f"[Series] Warning check: could not fetch previous script context: {e}")

    # Build performance feedback block for the LLM
    instructions = ""
    if feedback_summary and feedback_summary.strip():
        instructions = f"""
    ══ REAL PERFORMANCE DATA FROM YOUR ACCOUNT ══
    {feedback_summary}
    ══════════════════════════════════════════════
    Use this data to write a BETTER script:
    - Model your hook style after the TOP performers above.
    - Avoid angles or tones used in the LOWEST performers.
    - The goal is to beat your current average view count.
    """
    elif isinstance(analytics_data, list) and analytics_data:
        # Fallback: raw list (no summarized history yet)
        raw_str = "; ".join(
            f"{p.get('topic_snippet', '')[:60]} ({p.get('views', 0)} views, {p.get('likes', 0)} likes)"
            for p in analytics_data[:5]
        )
        instructions = f"""
    RECENT POST DATA (use to improve hook angle):
    {raw_str}
    Write a hook that outperforms these.
    """

    # Rotate hook framework randomly for variety
    hook_framework = _pick_hook_framework(analytics_data=analytics_data, feedback_summary=feedback_summary)

    prompt = f"""
    You are "The Decoder", an expert Instagram Reels psychologist. Your goal: maximum completion rate and engagement.
    Your audience is young men (18-30) on Indian Instagram who want you to DECODE female psychology, mixed signals, and relationship tests.
    {instructions}
    {language_rules}
    {previous_script_context}

    Create a PUNCHY, fast-paced reel script for this topic: "{topic}".

    ── THE DECODER PERSONA & TITLE RULES (CRITICAL) ──
    - You must act as the expert who "hacks" or deciphers psychology.
    - Ban all vague, depressing, or purely emotional angles. Focus purely on actionable decoding, tests, and hard truths.
    - The `title` field (which is the on-screen hook) MUST follow this format: `[Trigger Word] + [Question/Promise]`
      Examples of perfect titles: "Mixed Signals: Testing or Friendzone?", "Confused Signals? Friendzone DECIPHERED!", "Friendzone Test: Spot it or Stay Stuck?"
    - The `title` field MUST NEVER use Devanagari script (Hindi characters). Use pure English or Roman Hinglish.
    - Heavily favor terms like "Test", "Deciphered", "Secret", or numbered lists in your approach.

    ── MAXIMIZING ENGAGEMENT WITHOUT REPETITION ──
    To break past the 3.5K view ceiling, we need COMMENTS (most important), SAVES, and SHARES.
    Current engagement is 2.43% — target 3-5%. Comments are the #1 ranking factor.
    DO NOT use a numbered checklist (e.g., "3 signs hai") for every single video. 
    Mix up the structure! Some videos should be a story, some a single deep psychological truth, and some a numbered list.
    1. COMMENTS (PRIORITY #1): End with a DIRECT QUESTION that requires a yes/no/opinion answer in comments
       Examples: 'Tell me in comments: kabhi aapko ye hua?' OR 'Guilty or Not Guilty? Comment now.'
       Make viewers feel like they MUST answer — create FOMO of missing the discussion.
    2. SAVES: When appropriate, use specific advice or a checklist that viewers want to refer back to.
    3. SHARES: Include a relatable moment or realization that makes them want to DM a friend ("Agar koi dost isme phansa hai...").

    HOOK FRAMEWORK (you MUST use this style):
    {hook_framework['instruction']}

    ──── 3-ACT EMOTIONAL ESCALATION ARC ────

    DURATION: This reel MUST be 25-35 seconds when spoken. NON-NEGOTIABLE.
    - Total word count: 70-100 words ONLY
    - Return EXACTLY 3 scenes
    - Scene 1 (Hook — emotional_beat: "curious"): 20-28 words
        Impossible-to-skip opening. Bold claim or shocking reveal.
        Emotion goal: make the viewer feel a sudden jolt of curiosity.
    - Scene 2 (Build — emotional_beat: "tense"): 22-35 words
        Deliver the core value. This can be a short list, a surprising psychological fact, or a deep truth.
        Emotion goal: create an 'aha' moment or realization.
    - Scene 3 (Payoff + Save CTA + Share Trigger — emotional_beat: "shocked"): 25-35 words
        Drop the mind-blowing conclusion.
        Include a natural CTA to save OR share, but mix it up so it doesn't sound robotic.
        Examples: 'Save this so you don't forget' OR 'Send this to a friend who needs to hear it'.
        MANDATORY REWATCH TRIGGER: The LAST LINE must loop back to something said in Scene 1.

    RETENTION TACTICS:
    - Scene 1 must hook within 2 seconds.
    - Scene 2 creates tension.
    - Scene 3 closes the loop AND adds one extra twist that rewards rewatching.
    - Keep language conversational, raw, street-smart — like a friend sharing secrets.

    MANDATORY COMMENT-DRIVING TRIGGER (NON-NEGOTIABLE):
    The FINAL sentence of Scene 3 MUST include a direct question or poll that forces viewers to comment.
    CRITICAL: This is what will push your engagement from 2.4% to 3-5%.
    Structure: [Controversial Statement] + [Direct Yes/No Question]
    Examples:
    - 'Tum sochte ho ye testing hai ya genuine interest? Comment karo: Testing / Genuine / Confused'
    - 'Guilty or innocent? Batao comments mein.'
    - 'Agar ye tum par hua, toh tum kya karenfe? Share your move in comments.'
    - 'Mujhe batao: Tumhara last relationship yahi reason se khatam hua ya kuch aur? Comment.'
    ALSO include one share line: 'Send this to [type of person] who needs to hear it.'
    Pattern: [Direct Question in comments] + [Share trigger] = maximum engagement.

    PATTERN INTERRUPT:
    - Each scene MUST feel visually and tonally distinct from the others
    - Scene 1: mysterious/teasing energy
    - Scene 2: building tension/revealing energy
    - Scene 3: confident/mindblowing energy

    CONTENT BOUNDARIES:
    - Be intriguing and bold but stay Instagram-safe — NO explicit content
    - Focus on psychology, body language, behavioral insights, confidence, and attraction dynamics
    - Avoid overly suggestive or sexual language — Instagram's content classifier will suppress reach
    - Think "Psychology Today meets street wisdom" not "clickbait"
    - CRITICAL: DO NOT use any emojis in the text. Our custom font does not support emojis and will display broken square symbols.

    VISUAL KEYWORDS:
    - Each scene must have a visual_keyword for stock footage search
    - Keywords should describe the MOOD and SETTING, not just "hot girl"
    - CRITICAL FOR SCENE 1: The first scene's visual MUST be HIGH-IMPACT and stop scrolls within 0.5 seconds.
      Rules:
      * Use BOLD color contrast (neon green/magenta on black, bright red, vivid yellow, electric blue)
      * Close-ups of faces or hands ALWAYS work better than wide shots
      * For psychology: intense eye contact, raised eyebrow, subtle smirk
      * For relationships: two people looking in opposite directions (subtle tension)
      * Horror/Mystery: extreme close-up + shadow + single light source
      * NEVER use blurry or low-contrast visuals in Scene 1 — it won't stop scrolls
      * Text overlay (title) MUST be readable in 0.3 seconds even on small phone screens
    - Best Scene 1 visuals: "extreme close-up face intense eyes neon lighting", "two people back to back dramatic shadow", "single eye macro shot mysterious"
    - Include mood + technical descriptors: "4K, high contrast, bold colors, cinematic, close-up"
    - Each scene MUST have a different visual_mood (one of: mysterious, confident, dramatic, intense, dark, energetic, elegant, horror)
    - Scene 1 visual_mood should be: intense OR mysterious OR dramatic — NEVER calm or neutral
    - Prioritize STOP-SCROLL visuals over artistic beauty

    Format the output as strict JSON:
    {{
        "title": "A catchy viral title (max 8 words)",
        "hook_framework": "curiosity_gap",
        "scenes": [
            {{
                "id": 1,
                "text": "Scene 1 narration (Hook — curious energy)",
                "visual_keyword": "Descriptive visual search term with mood and lighting",
                "visual_mood": "mysterious",
                "emotional_beat": "curious"
            }},
            {{
                "id": 2,
                "text": "Scene 2 narration (Build — tense energy)",
                "visual_keyword": "Different visual search term with contrasting mood",
                "visual_mood": "dramatic",
                "emotional_beat": "tense"
            }},
            {{
                "id": 3,
                "text": "Scene 3 narration (Payoff — shocked energy, rewatch callback to Scene 1)",
                "visual_keyword": "Third unique visual search term with final mood",
                "visual_mood": "confident",
                "emotional_beat": "shocked"
            }}
        ]
    }}
    Provide only the valid JSON, no markdown formatting blocks.
    """

    return _llm_prompt(prompt)


def generate_script_payload(topic, analytics_data=None, feedback_summary="", max_repairs=2):
    """Generate script and return a validated JSON payload with auto-repair retries."""
    if feedback_summary:
        print(f"[Feedback] Injecting performance history into script prompt.")
    raw = generate_script(topic, analytics_data=analytics_data, feedback_summary=feedback_summary)

    for attempt in range(max_repairs + 1):
        try:
            payload = _parse_script_payload(raw)
            payload = _postprocess_script_payload(payload)
            if "hook_framework" not in payload:
                payload["hook_framework"] = _pick_hook_framework(
                    analytics_data=analytics_data,
                    feedback_summary=feedback_summary,
                )["name"]
            return payload
        except Exception as exc:
            if attempt >= max_repairs:
                raise RuntimeError(
                    f"Failed to parse script JSON after {max_repairs + 1} attempts: {exc}"
                ) from exc
            print(f"Script JSON invalid, attempting repair ({attempt + 1}/{max_repairs})...")
            raw = _repair_script_json(raw, str(exc))


# ── Topic sub-category rotation for content variety ──────────────────
# Based on REAL analytics (July 2026):
# TIER 1A — Friendzone/Situationship: 2.5K-2.6K views, 21-24 shares, 84-93 interactions
# TIER 1B — Mirror Psychology: 1.5K views BUT 23 shares (1.53% share rate — HIGHEST of all reels)
# These two content types are the ONLY proven performers. Everything else gets 127-541 views.

_TOPIC_TIER1A_FRIENDZONE = [
    "friendzone psychology — how to spot it, escape it, or use it",
    "situationship vs friendzone — how to decode where you really stand",
    "different stages of a relationship and what each stage reveals",
    "friendship to love — signs she wants more than just being friends",
    "stuck in friendzone? psychology of why and how to break out",
    "situationship red flags — signs you're being kept as a backup",
    "how to know if she sees you as a friend or something more",
    "the hidden stage before a relationship that most guys miss",
    "why girls keep certain guys in the friendzone deliberately",
    "from talking stage to relationship — what signals matter most",
    "friendzone test — 3 signs that tell you exactly where you stand",
    "situationship psychology — why it feels like a relationship but isn't",
    "how friendships turn into love — the psychology behind it",
    "mixed signals or friendzone — how to tell the real difference",
    "the moment she decides you're just a friend — and how to reverse it",
    "signs she's keeping you as a backup — not as the one",
    "Part 2: Escape The Friendzone Using This One Shift",
    "Part 2: Situationship Exit — How to Make Her Choose",
]

_TOPIC_TIER1B_MIRROR = [
    # Mirror psychology: 1.53% share rate (highest) — people DM this to friends
    "mirror effect psychology — when she copies your behavior it means THIS",
    "she copies your words gestures energy — what her mirror behavior reveals",
    "mirror psychology test — does she subconsciously mirror you right now",
    "body mirroring — the one signal most guys completely miss",
    "when she starts copying YOU — what the psychology says about attraction",
    "why girls mirror the guy they like without even knowing it",
    "Part 2: Mirror Test — 3 Ways To Check If She's Mirroring You",
    "subconscious mirroring — her body is saying what her words won't",
]

# TIER 2 — GOOD (1.5K views, proven but not top-tier)
_TOPIC_TIER2_HIGH = [
    "eye contact secrets — what her first glance really reveals",
    "texting psychology — what her reply speed actually means",
    "jealousy test — one move to check if she genuinely cares",
    "signs she's attracted but hiding it — body language tell",
    "what happens when you go silent — the power of withdrawal",
    "3 things that instantly kill attraction without you knowing",
    "the psychology of why being too available destroys attraction",
    "her smile decoded — the difference between polite and genuine",
]

# TIER 3 — HORROR & MYSTERY (The new viral pivot)
_TOPIC_TIER3_EXPLORE = [
    "creepy psychological facts that will keep you awake at night",
    "unsolved mysteries that scientists still cannot explain",
    "the most haunted places where people disappeared without a trace",
    "dark psychology facts about the human mind",
    "creepy things that happen in the deep ocean or space",
    "glitch in the matrix real life scary stories",
    "the dark side of human behavior and psychology",
    "disturbing facts about dreams and sleep paralysis",
]

# PROVEN DEAD — NEVER USE AGAIN (based on analytics data)
# - "Her Smile Lies" (posted twice: 133 views + 541 views) — topic is exhausted
# - "Magnetic Presence / charisma" (127 views, 2 interactions)
# - "Secret Touch" (generic, no specific signal)
# - "Micro-Expression" (tutorial feel, doesn't trigger shares)
# - "Text Ignore" (138 views despite afternoon post)


def _pick_topic_subcategory():
    """
    Weighted topic picker designed for balance:
    - 25% Friendzone/Situationship (Tier 1A)
    - 25% Mirror Psychology (Tier 1B)
    - 25% Eye Contact/Body Language (Tier 2)
    - 25% Horror, Mystery & Dark Psychology (Tier 3)
    """
    roll = random.random()
    if roll < 0.25:
        return random.choice(_TOPIC_TIER1A_FRIENDZONE)
    elif roll < 0.50:
        return random.choice(_TOPIC_TIER1B_MIRROR)
    elif roll < 0.75:
        return random.choice(_TOPIC_TIER2_HIGH)
    else:
        return random.choice(_TOPIC_TIER3_EXPLORE)



def generate_topic_from_domain(domain, analytics_data=None, feedback_summary="", used_topics=None):
    """Generate the next reel topic, avoiding recently used ones."""
    # Build deduplication context for the LLM
    used_topics_set = used_topics or set()
    avoid_block = ""
    if used_topics_set:
        recent_list = ", ".join(f'"{t}"' for t in list(used_topics_set)[-15:])
        avoid_block = f"""
CRITICAL: DO NOT suggest any of these recently used topics (they were already posted):
{recent_list}
The new topic must be clearly different in angle and hook style from all of the above.
"""

    # Rotate through sub-categories for content variety
    subcategory = _pick_topic_subcategory()

    prompt = f"""
You are a short-form content strategist specialized in viral Instagram Reels. 
Your target audience is young men (18-30) on Indian Instagram who love dark psychology, attraction secrets, horror, and mysteries.

Primary domain: "{domain}"
Today's angle/subcategory to focus on: "{subcategory}"
Historical feedback summary: {feedback_summary or 'No data yet'}
{avoid_block}
Task:
Propose exactly ONE topic idea for the next Instagram Reel that:
1. Stays within the primary domain
2. Uses today's angle/subcategory as the specific focus
3. Iterates on what performed best (if analytics data is available)
4. Has VERY strong hook potential — must create instant curiosity or fear
5. Focuses on psychology, horror, mysteries, or dark facts
6. Is bold and intriguing WITHOUT being sexually explicit (Instagram-safe)
7. Is DIFFERENT from the recently used topics listed above

Great topic examples (for inspiration, don't copy exactly):
- Duniya ki sabse bhutiya jagah jahan se koi nahi lauta
- 3 creepy facts jo tumhe aaj raat sone nahi denge
- Ek cheez jo ladkiyon ko turant attract karti hai
- Sleep paralysis ka dark secret jo koi nahi batata
- Body language signs jo batati hain ke wo interested hai
- Psychology trick jo kisi ko bhi tumhari taraf kheench le
- Samundar ki gehrayi mein chhupe dark secrets
- Kaise pata chale ke wo tumhare baare mein sochti hai

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _llm_prompt(prompt)
    lines = content.splitlines()
    if not lines:
        raise ValueError("LLM returned empty topic")
    return lines[0].strip()

