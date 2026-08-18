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


# ── Hook framework rotation for maximum variety (Female Psychology & Attraction Focus) ──
_HOOK_FRAMEWORKS = [
    {
        "name": "eye_contact_trap",
        "instruction": "Open with an intense eye contact or glance signal. Example pattern: 'Jab wo tumse eye contact karke nazrein churati hai, toh iska asli matlab samjho...' or 'Her eye contact trap: Shatter it with THIS secret!'",
    },
    {
        "name": "mixed_signals_decoder",
        "instruction": "Open with a mixed signal dilemma. Example pattern: 'Her mixed signals: Testing ya friendzoning? The truth hurts...' or 'Agar wo ek din warm aur dusre din cold react kare, toh wo ye test kar rahi hai...'",
    },
    {
        "name": "mirror_effect_secret",
        "instruction": "Open with body language mirroring. Example pattern: 'Jab wo tumhari tarah baatein ya gesture copy karne lage, toh dimaag mein ye chal raha hota hai...' or 'Subconscious mirroring: 3 signs jo wo chhupa nahi sakti!'",
    },
    {
        "name": "female_psychology_truth",
        "instruction": "Start with a direct female psychology rule. Example pattern: 'Ye ek cheez ladkiyan tumhein kabhi seedhe nahi batayengi...' or 'Psychology says: jab ladki tumhare baare mein sochti hai...'",
    },
    {
        "name": "curiosity_gap",
        "instruction": "Start with an incomplete provocative statement that creates burning curiosity. Example pattern: 'Agar wo tumhara text ignore kar ke online reh rahi hai, toh wo tumhein is test mein phansa rahi hai...'",
    },
    {
        "name": "kabhii_nahi",
        "instruction": """
Open with a 'kabhi nahi...' statement in Devanagari Hindi.
The sentence MUST be a complete, punchy hook about female attraction or relationship signals.
DO NOT use '...' or truncate the sentence. It must be a full sentence on the first frame.
Examples of proven-viral openers:
  - 'ये चीज़ लड़कियां कभी सीधे नहीं बतातीं!'
  - 'उसकी ये हरकत कभी इग्नोर मत करना!'
  - 'ये 3 इशारे लड़कियां सिर्फ खास इंसान को देती हैं!'
MANDATORY: The very first scene text must be a complete sentence that hooks the viewer instantly.""",
    },
    {
        "name": "test_format",
        "instruction": """
Frame the entire reel as a test or quiz the viewer can take.
Pattern: 'Friendzone Test: Spot It Or Stay Stuck?' or 'Attraction Test: Is She Testing You?'
First sentence must name the test and its stakes.
Example: 'Ye female psychology test fail kiya toh friendzone mein rahoge forever!'""",
    },
]


def _pick_hook_framework(analytics_data=None, feedback_summary=""):
    """Choose a hook framework using an Epsilon-Greedy (80/20) policy for female psychology."""
    proven_viral = ["eye_contact_trap", "mixed_signals_decoder", "mirror_effect_secret", "female_psychology_truth", "kabhii_nahi"]
    
    # 80% Exploitation of top viral framework patterns
    if random.random() < 0.80:
        preferred_name = random.choice(proven_viral)
        for framework in _HOOK_FRAMEWORKS:
            if framework["name"] == preferred_name:
                print(f"[HookEngine] Exploit policy: Using top viral framework '{framework['name']}'")
                return framework

    # 20% Exploration of wildcard frameworks
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

    ── HIGH-RETENTION DECODER ARC (22–30 SECONDS OPTIMAL) ──

    DURATION: This reel MUST be 22-30 seconds when spoken.
    - Total word count: 60-80 words across the whole script.
    - Return EXACTLY 3 or 4 scenes to build narrative depth, tension, and high watch time.
    - Scene 1 (The Hook — 5-7s): 15-20 words
        CRITICAL: The voiceover MUST start IMMEDIATELY with the hook statement. Do NOT read the title banner aloud!
        Impossible-to-skip opening statement about female psychology or attraction signal.
    - Scene 2 (The Deep Signal — 7-9s): 20-25 words
        Explain the psychological reason behind her behavior / body language.
    - Scene 3 (The Decoder Move — 7-9s): 20-25 words
        Provide the exact counter-move or decoding tip for the viewer.
    - Scene 4 (Comment & Share Loop — 4-6s): 10-15 words
        End with a direct comment question or opinion poll + share trigger.
        MANDATORY LOOP TRIGGER: The final 3 words should seamlessly connect back to the hook idea.

    RETENTION TACTICS:
    - Launch straight into the hook in word 1.
    - Keep language conversational, raw, street-smart — like a brother telling secrets.
    - Zero filler words. Every word must deliver high dopamine intrigue.

    MANDATORY COMMENT-DRIVING TRIGGER (NON-NEGOTIABLE):
    The FINAL sentence MUST include a direct question or poll that forces viewers to comment.
    Structure: [Controversial Statement] + [Direct Yes/No Question]
    Examples:
    - 'Tum sochte ho ye testing hai ya genuine interest? Comment karo: Testing / Genuine'
    - 'Guilty or innocent? Batao comments mein.'
    - 'Agar ye tum par hua, toh tum kya karoge? Share your move in comments.'
    ALSO include one share line: 'Send this to a friend who needs to hear it.'

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

# ── Topic sub-category pools for maximum retention & viral reach ──────
# Based on REAL analytics (July 2026):
# TIER 1A — Friendzone/Situationship/Mixed Signals: 2.5K-6.3K views (HIGHEST VIEWS)
# TIER 1B — Mirror Psychology & Eye Contact Secrets: 1.5K-3.5K views (HIGHEST SHARE RATE)

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
    "mirror effect psychology — when she copies your behavior it means THIS",
    "she copies your words gestures energy — what her mirror behavior reveals",
    "mirror psychology test — does she subconsciously mirror you right now",
    "body mirroring — the one signal most guys completely miss",
    "when she starts copying YOU — what the psychology says about attraction",
    "why girls mirror the guy they like without even knowing it",
    "Part 2: Mirror Test — 3 Ways To Check If She's Mirroring You",
    "subconscious mirroring — her body is saying what her words won't",
]

_TOPIC_TIER2_HIGH = [
    "eye contact secrets — what her first glance really reveals",
    "eye contact trap — why girls look away when you catch them watching",
    "texting psychology — what her reply speed actually means",
    "jealousy test — one move to check if she genuinely cares",
    "signs she's attracted but hiding it — body language tell",
    "what happens when you go silent — the power of withdrawal",
    "3 things that instantly kill attraction without you knowing",
    "the psychology of why being too available destroys attraction",
    "her smile decoded — the difference between polite and genuine",
]


def generate_topic_from_domain(domain, analytics_data=None, feedback_summary="", used_topics=None):
    """Generate the next reel topic focused 100% on Female Psychology & Attraction Signals."""
    used_topics_set = used_topics or set()
    avoid_block = ""
    if used_topics_set:
        recent_list = ", ".join(f'"{t}"' for t in list(used_topics_set)[-15:])
        avoid_block = f"""
CRITICAL: DO NOT suggest any of these recently used topics (they were already posted):
{recent_list}
The new topic must be clearly different in angle and hook style from all of the above.
"""

    women_topics_pool = _TOPIC_TIER1A_FRIENDZONE + _TOPIC_TIER1B_MIRROR + _TOPIC_TIER2_HIGH
    subcategory = random.choice(women_topics_pool)

    pillar_instructions = """
Target Niche: FEMALE & WOMEN PSYCHOLOGY, ATTRACTION SECRETS, EYE CONTACT & RELATIONSHIP SIGNALS
Task guidelines:
1. Focus strictly on female/women psychology, subconscious body language signals, attraction secrets, mirror effect, eye contact traps, or decoding mixed signals.
2. Must create intense curiosity about female behavior and relationship dynamics.
3. Proven Top-Performing Angles (model after these):
   - Her Mixed Signals: Testing or Friendzoning?
   - Eye Contact Trap: The REAL Unlock!
   - Mirror Effect Psychology — Jab wo tumhari tarah act karti hai
   - Ye 3 signs jo batati hain ke wo interested hai
"""

    prompt = f"""
You are a short-form content strategist specialized in viral Instagram Reels. 
Your target audience is young men (18-30) on Indian Instagram who want female psychology, attraction secrets, and relationship signals deciphered.

Primary domain: "{domain}"
Today's angle/subcategory focus: "{subcategory}"
{pillar_instructions}
Historical feedback summary: {feedback_summary or 'No data yet'}
{avoid_block}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that:
1. Strictly adheres to today's Target Niche guidelines listed above
2. Has EXTREMELY STRONG hook potential for views and shares
3. Is bold, engaging, street-smart, and Instagram-safe
4. Is DIFFERENT from the recently used topics listed above

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _llm_prompt(prompt)
    lines = content.splitlines()
    if not lines:
        raise ValueError("LLM returned empty topic")
    return lines[0].strip()

