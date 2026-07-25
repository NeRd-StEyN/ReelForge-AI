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

def _call_openrouter(prompt, model):
    """Call OpenRouter API with a given model. Returns response text."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://reelforge.ai",
        "X-Title": "ReelForge AI",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
    }
    
    resp = requests.post(_OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def _llm_prompt(prompt):
    """Call LLM via OpenRouter dynamic free routing."""
    models_to_try = [_OPENROUTER_PRIMARY_MODEL] + _OPENROUTER_FALLBACK_MODELS
    last_error = None

    for model in models_to_try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[OpenRouter] Using model: {model} (attempt {attempt + 1})")
                raw = _call_openrouter(prompt, model)
                return _normalize_content(raw)
            except Exception as exc:
                error_str = str(exc)
                last_error = exc
                if "429" in error_str or "rate" in error_str.lower():
                    wait_time = 15 * (attempt + 1)
                    print(f"[OpenRouter] Rate limit on {model}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                # Non-rate-limit error — skip to next model
                print(f"[OpenRouter] {model} failed: {exc}. Trying next model...")
                break

    raise RuntimeError(f"All OpenRouter models failed. Last error: {last_error}")



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
        "name": "warning_hook",
        "instruction": "Start with a direct warning that creates immediate suspense and fear. Example pattern: 'Agar tum akele ho toh ye video abhi mat dekhna...' or 'Ye khaufnak sach sunne ke baad tum darr jaoge...'",
    },
    {
        "name": "dark_mystery",
        "instruction": "Open with an unsolved mystery or creepy phenomenon. Example pattern: 'Duniya ki sabse rahasyamayi jagah jahan se koi wapas nahi aaya...' or 'Ye creepy mystery tumhe raat bhar sone nahi degi...'",
    },
    {
        "name": "unexplained_phenomena",
        "instruction": "Open with a mind-bending or terrifying true incident that science cannot explain. Example pattern: 'Science ke paas bhi is khaufnak ghatna ka koi jawab nahi hai...'",
    },
    {
        "name": "creepy_fact",
        "instruction": "Start with a disturbing fact about sleep paralysis, space, the ocean, or the human mind. Example pattern: 'Jab tum sote ho toh tumhare dimaag ke saath kya hota hai...'",
    },
    {
        "name": "curiosity_gap",
        "instruction": "Start with an incomplete statement that creates burning curiosity. Example pattern: 'Ye khaufnak rahasya duniya se chhupaya gaya tha, lekin...'",
    },
    {
        "name": "shock_stat",
        "instruction": "Open with a surprising or creepy statistic. Example pattern: '90% log nahi jaante ki sleep paralysis ke waqt...', make it feel eerie.",
    },
    {
        "name": "kabhii_nahi",
        "instruction": """
Open with a 'kabhi nahi...' statement in Devanagari Hindi.
The sentence MUST be a complete, punchy hook that generates extreme curiosity or chill.
DO NOT use '...' or truncate the sentence. It must be a full sentence on the first frame.
Examples of proven-viral openers:
  - 'ये खौफनाक राज़ आपको कोई नहीं बताएगा!'
  - 'इंसानी दिमाग का ये काला सच कभी मत भूलना!'
  - 'ये चीज़ लड़कियां कभी सीधे नहीं बतातीं!'
MANDATORY: The very first scene text must be a complete sentence that hooks the viewer instantly.""",
    },
    {
        "name": "test_format",
        "instruction": """
Frame the entire reel as a test or quiz the viewer can take.
Pattern: 'Psychology Test: Spot It Or Stay Stuck?' or '[Topic] Test: [Outcome if you fail]'
First sentence must name the test and its stakes.
Example: 'Ye dark psychology test fail kiya toh [consequence] rahoge forever!'""",
    },
]


def _pick_hook_framework(analytics_data=None, feedback_summary=""):
    """Choose a hook framework using an Epsilon-Greedy (80/20) policy.
    
    - 80% Exploitation: Pulls from proven high-converting hook styles (warning hook, dark mystery, creepy fact)
    - 20% Exploration: Forces wildcard framework rotation to discover new viral angles & prevent audience burnout
    """
    proven_viral = ["warning_hook", "dark_mystery", "unexplained_phenomena", "creepy_fact", "kabhii_nahi"]
    
    # 80% Exploitation of top viral framework patterns
    if random.random() < 0.80:
        preferred_name = random.choice(proven_viral)
        for framework in _HOOK_FRAMEWORKS:
            if framework["name"] == preferred_name:
                print(f"[HookEngine] Exploit policy: Using top viral framework '{framework['name']}'")
                return framework

    # 20% Exploration of wildcard frameworks to prevent echo chamber burnout
    chosen = random.choice(_HOOK_FRAMEWORKS)
    print(f"[HookEngine] Explore policy (20% wildcard): Using framework '{chosen['name']}'")
    return chosen


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

    ── 2-ACT ULTRA-HIGH RETENTION ARC (12–18 SECONDS STRICT) ──

    DURATION: This reel MUST be 12-18 seconds when spoken. NON-NEGOTIABLE.
    - Total word count: 40-55 words ONLY across the whole script.
    - Return EXACTLY 2 scenes for maximum completion rate (>100% loop probability).
    - Scene 1 (The Scroll Stopper — 6-9s): 20-25 words
        CRITICAL: The voiceover MUST start IMMEDIATELY with the hook statement. Do NOT read the title banner or header text aloud!
        Impossible-to-skip opening statement, pattern interrupt, or provocative truth.
    - Scene 2 (The Mind-Blow + Engagement Loop — 6-9s): 20-30 words
        Deliver the core psychological insight fast.
        End with a 1-sentence comment/share trigger.
        MANDATORY LOOP TRIGGER: The final 3 words must seamlessly loop back to the first word of Scene 1.

    RETENTION TACTICS:
    - Launch straight into the hook in word 1.
    - Keep language conversational, raw, street-smart — like a brother telling secrets.
    - Zero filler words. Every word must deliver high dopamine intrigue.

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
    {instructions}

    RULES:
    1. Generate exactly 6 to 8 short scenes. This is critical for fast-paced visual cuts.
    2. Each scene's `text` MUST be very short (1 or 2 sentences max) for high-energy pacing.
    3. For `visual_keyword`, YOU MUST provide LITERAL, highly-specific human actions (e.g., "close up couple holding hands", "person looking at phone in dark", "woman smiling over shoulder"). DO NOT use abstract words like "psychology", "mind", or "brain". We need real human B-roll.
    4. Each scene MUST have a `visual_mood` (mysterious, confident, dramatic, intense, dark, energetic, elegant, or horror).
    5. Final scene MUST include a CTA for comments (poll or question) and share trigger.
    6. Output strict JSON only.

    JSON STRUCTURE:
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

# TIER 3 — HORROR, THRILLER & MYSTERY (Primary Viral Focus)
_TOPIC_TIER3_EXPLORE = [
    "creepy psychological facts that will keep you awake at night",
    "unsolved mysteries that scientists still cannot explain",
    "the most haunted places where people disappeared without a trace",
    "dark psychology secrets about human fear and terror",
    "creepy things that happen in the deep ocean that sound fake but are real",
    "glitch in the matrix real life scary stories people experienced",
    "disturbing facts about dreams sleep paralysis and shadow figures",
    "real life unsolved vanishing cases that terrify researchers",
    "creepy psychological phenomena that explain why you feel watched",
    "terrifying historical incidents that were erased from history books",
    "the terrifying mystery of skinwalkers and eerie forest encounters",
    "disturbing deep web mysteries that remain unsolved today",
    "scariest psychological experiments ever conducted on humans",
    "creepy space facts that prove how terrifying the universe really is",
    "unexplained audio signals from space and the deep sea",
    "horrifying true paranormal stories documented by emergency services",
    "the eerie phenomenon of deja vu and dark memory loops",
    "creepy urban legends that turned out to be completely real",
    "disturbing brain facts: what happens when your mind plays tricks on you",
    "unsolved cryptid encounters caught on camera that defy science",
]

# PROVEN DEAD — NEVER USE AGAIN (based on analytics data)
# - "Her Smile Lies" (posted twice: 133 views + 541 views) — topic is exhausted
# - "Magnetic Presence / charisma" (127 views, 2 interactions)
# - "Secret Touch" (generic, no specific signal)
# - "Micro-Expression" (tutorial feel, doesn't trigger shares)
# - "Text Ignore" (138 views despite afternoon post)


# ── Anti-Consecutive Topic Rotation System ──────────────────────────────
_PILLAR_STATE_FILE = os.path.join("data", "last_topic_pillar.txt")

def _get_next_topic_pillar():
    """
    Guarantees strict alternating rotation between two core content pillars so that
    no two consecutive reels are ever of the same type:
    - Pillar 1: 'horror_mystery' (Horror, Thriller, Unsolved Mysteries, Creepy Facts)
    - Pillar 2: 'women_psychology' (Female/Women Psychology, Attraction Signals, Relationship Secrets)
    """
    last_pillar = ""
    try:
        if os.path.exists(_PILLAR_STATE_FILE):
            with open(_PILLAR_STATE_FILE, "r") as f:
                last_pillar = f.read().strip().lower()
    except (ValueError, OSError):
        pass

    if last_pillar == "horror_mystery":
        next_pillar = "women_psychology"
    else:
        next_pillar = "horror_mystery"

    try:
        os.makedirs("data", exist_ok=True)
        with open(_PILLAR_STATE_FILE, "w") as f:
            f.write(next_pillar)
    except OSError:
        pass

    print(f"[TopicEngine] Anti-consecutive rotation: Selected pillar '{next_pillar}' (previous was '{last_pillar or 'none'}')")
    return next_pillar


def generate_topic_from_domain(domain, analytics_data=None, feedback_summary="", used_topics=None):
    """Generate the next reel topic, alternating strictly between Horror/Thriller and Women Psychology."""
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

    pillar = _get_next_topic_pillar()

    if pillar == "horror_mystery":
        subcategory = random.choice(_TOPIC_TIER3_EXPLORE)
        pillar_instructions = """
Target Pillar: HORROR, THRILLER, UNSOLVED MYSTERIES & CREEPY FACTS
Task guidelines:
1. Focus strictly on scary psychological facts, unsolved mysteries, haunted locations, eerie phenomena, ocean/space horror, or glitch-in-the-matrix stories.
2. Must create instant fear, suspense, or chilling curiosity.
3. Examples (don't copy directly):
   - Duniya ki sabse bhutiya jagah jahan se koi wapas nahi aaya
   - 3 creepy facts jo tumhe aaj raat sone nahi denge
   - Sleep paralysis ka dark secret jo koi nahi batata
   - Science ke paas bhi is khaufnak mystery ka koi jawab nahi hai
"""
    else:
        women_topics_pool = _TOPIC_TIER1A_FRIENDZONE + _TOPIC_TIER1B_MIRROR + _TOPIC_TIER2_HIGH
        subcategory = random.choice(women_topics_pool)
        pillar_instructions = """
Target Pillar: FEMALE & WOMEN PSYCHOLOGY, ATTRACTION SECRETS & RELATIONSHIP SIGNALS
Task guidelines:
1. Focus on female/women psychology, subconscious body language signals, attraction secrets, mirror effect, or decoding mixed signals.
2. Must create intense curiosity about female behavior and relationship dynamics.
3. Examples (don't copy directly):
   - Ye cheez ladkiyan kabhi seedhe nahi batati
   - 3 body language signs jo batati hain ke wo interested hai
   - Mirror effect psychology — jab wo tumhari tarah act karti hai
   - Mixed signals ya friendzone — kaise pata karein
"""

    prompt = f"""
You are a short-form content strategist specialized in viral Instagram Reels. 
Your target audience is viewers on Indian Instagram who love engaging, high-curiosity short reels.

Primary domain: "{domain}"
Today's angle/subcategory focus: "{subcategory}"
{pillar_instructions}
Historical feedback summary: {feedback_summary or 'No data yet'}
{avoid_block}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that:
1. Strictly adheres to today's Target Pillar guidelines listed above
2. Has EXTREMELY STRONG hook potential
3. Is bold, engaging, and Instagram-safe
4. Is DIFFERENT from the recently used topics listed above

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _llm_prompt(prompt)
    lines = content.splitlines()
    if not lines:
        raise ValueError("LLM returned empty topic")
    return lines[0].strip()

