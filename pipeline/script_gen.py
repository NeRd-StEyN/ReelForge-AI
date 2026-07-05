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
    "meta-llama/llama-3.1-8b-instruct:free",
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
    """Call LLM via OpenRouter with primary model and automatic fallback."""
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
                    wait_time = 10 * (attempt + 1)
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
    """Choose a hook framework with a strong bias toward proven viral frameworks.
    
    Based on account analytics:
    - kabhii_nahi: 2x 1.4K-view reels → highest average performer
    - test_format: 2.4K view reel → top single performer
    - curiosity_gap: good secondary framework
    These three get 60% weight; others fill the remainder.
    """
    # Always prioritize the proven frameworks first (60% of the time)
    proven_viral = ["kabhii_nahi", "test_format", "curiosity_gap"]
    if random.random() < 0.60:
        preferred_name = random.choice(proven_viral)
        for framework in _HOOK_FRAMEWORKS:
            if framework["name"] == preferred_name:
                return framework

    if feedback_summary:
        if "saves" in feedback_summary.lower() or "comments" in feedback_summary.lower():
            preferred = ["kabhii_nahi", "curiosity_gap", "challenge", "story_open"]
        else:
            preferred = ["test_format", "shock_stat", "kabhii_nahi", "controversial_take"]

        for framework_name in preferred:
            for framework in _HOOK_FRAMEWORKS:
                if framework["name"] == framework_name:
                    return framework

    return random.choice(_HOOK_FRAMEWORKS)


def generate_script(topic, analytics_data=None, feedback_summary=""):
    """Generates a highly viral, SHORT video script optimized for completion rate."""
    language = _get_content_language()
    language_rules = """
    Language rules:
    - Narration text MUST be in pure Hindi using STRICTLY Devanagari script (e.g. "लड़कियां" NOT "ladkiyan").
    - DO NOT use Roman/Latin letters for the narration text. This is a hard requirement.
    - Keep pronunciation natural for Hindi TTS.
    - Title can be English or Hinglish, but scene text MUST be Devanagari.
    """ if language in {"hindi", "hi", "hi-in"} else ""

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
    You are an expert Instagram Reels strategist. Your goal: maximum completion rate and engagement.
    Your audience is young men (18-30) on Indian Instagram who love bold, intriguing content about psychology, attraction, relationships, and human behavior.
    {instructions}
    {language_rules}

    Create a PUNCHY, fast-paced reel script for this topic: "{topic}".

    HOOK FRAMEWORK (you MUST use this style):
    {hook_framework['instruction']}

    ──── 3-ACT EMOTIONAL ESCALATION ARC ────

    DURATION: This reel MUST be 25-35 seconds when spoken. NON-NEGOTIABLE.
    - Total word count: 70-100 words ONLY
    - Return EXACTLY 3 scenes
    - Scene 1 (Hook — emotional_beat: "curious"): 20-28 words
        Impossible-to-skip opening. Bold claim or shocking reveal.
        Emotion goal: make the viewer feel a sudden jolt of curiosity — they NEED to know more.
    - Scene 2 (Build — emotional_beat: "tense"): 22-32 words
        Deepen the intrigue. Reveal one specific, surprising insight.
        Emotion goal: build anxiety or suspense — make skipping feel like missing out on a secret.
    - Scene 3 (Payoff + Rewatch Trigger — emotional_beat: "shocked"): 20-28 words
        Drop the mind-blowing conclusion.
        MANDATORY REWATCH TRIGGER: The LAST LINE of Scene 3 MUST loop back to something said in
        Scene 1 — a callback, a twist, or a re-framing of Scene 1's opening claim.
        This creates an involuntary "wait, let me watch again" reaction.
        Emotion goal: deliver a satisfying shock + leave a dangling thread that rewards rewatching.

    RETENTION TACTICS:
    - Scene 1 must hook within 2 seconds — start mid-sentence, mid-story, or with a shocking stat
    - Scene 2 creates an open loop that makes skipping feel like missing out
    - Scene 3 closes the loop AND adds one extra twist that rewards rewatching
    - Keep language conversational, raw, street-smart — like a friend sharing secrets
    - Each scene should feel like a new revelation, not a continuation

    MANDATORY REWATCH TRIGGER (NON-NEGOTIABLE):
    The FINAL sentence of Scene 3 MUST contain a callback to EXACTLY one specific word or phrase used in Scene 1.
    This creates an involuntary 'wait, let me watch again' reaction that Instagram's algorithm
    registers as a rewatch — which is a top-tier distribution signal.
    Bad example: 'Toh ab tum jaante ho.' (no callback)
    Good example: Scene 1 said 'woh kabhi seedha nahi bolti' → Scene 3 ends with 'woh seedha kyun nahi bolti — ab tum samajh gaye.'
    The callback must feel like a satisfying click, not a forced repetition.

    IN-VIDEO LIKE BAIT (MANDATORY):
    Scene 3 MUST include one direct viewer-addressed line that prompts a like.
    This should feel natural, not forced. Examples:
    - 'Agar ye tumhare saath bhi hua hai, toh tum akele nahi ho.'
    - 'Ye baat sirf wo log samjhenge jo sach mein iske through gaye hain.'
    This line drives the emotional like-trigger without literally saying 'like karo'.

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
    - CRITICAL FOR SCENE 1: The first scene's visual MUST be high-contrast and instantly readable.
      Use bright, clear settings like: "woman face close up neon light portrait", "bold text glitch aesthetic", 
      "person confident city street golden hour", "dramatic studio portrait bright lighting".
      NEVER use dark, ambiguous indoor scenes (warehouses, dim tents, unlit rooms) for Scene 1.
      The viewer must immediately understand the visual context within 1 second — even with sound off.
    - Good examples: "confident woman walking city street cinematic", "close up eyes mysterious lighting", "couple coffee shop candid moment"
    - Include lighting/mood descriptors: neon, golden hour, moody dark, bright aesthetic, cinematic
    - Each scene MUST have a different visual_mood (one of: mysterious, confident, dramatic, warm, dark, energetic, elegant)
    - Avoid repetitive stock-looking keywords — make each scene feel visually distinct
    - Scene 1 visual_mood should be: mysterious OR energetic OR dramatic — never "dark" alone

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
# ── PROVEN VIRAL TOPIC SERIES (based on actual account performance) ──────────
# These topics are directly modeled from reels that got 1K+ views on this account.
# Each is part of a content funnel — each topic leads naturally to a Part 2.
_TOPIC_SUBCATEGORIES = [
    # TIER 1 — PROVEN VIRAL (replicate these series)
    "friendzone psychology — how to spot it, escape it, or use it",           # 2.4K views series
    "mirror effect psychology — when she copies your behavior it means THIS",  # 1.4K views series
    "eye contact secrets — what her first glance really reveals",              # 1.4K views series
    "situationship vs friendzone — how to decode where you really stand",      # Natural Part 2
    "texting psychology — what her reply speed actually means",
    "jealousy test — one move to check if she genuinely cares",
    # TIER 2 — HIGH POTENTIAL (aligned with niche)
    "psychological facts about attraction and human connection",
    "body language secrets that reveal hidden feelings safely",
    "how to build unshakeable confidence in social situations",
    "positive body language habits that command instant respect",
    "surprising psychological facts about human behavior and desire",
    "common communication mistakes and how to fix them",
    "how to read micro-expressions and understand people better",
    "psychology of charisma and what makes someone naturally magnetic",
    "subtle signs someone genuinely respects and values you",
    "the psychology of building strong, healthy relationships",
    "signs she's attracted but hiding it — body language tell",
    "what happens when you go silent — the power of withdrawal",
    "3 things that instantly kill attraction without you knowing",
    "the psychology of why being too available destroys attraction",
]


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
    subcategory = random.choice(_TOPIC_SUBCATEGORIES)

    prompt = f"""
You are a short-form content strategist specialized in viral Instagram Reels about psychology, attraction, and human behavior.
Your target audience is young men (18-30) on Indian Instagram.

Primary domain: "{domain}"
Today's angle/subcategory to focus on: "{subcategory}"
Historical feedback summary: {feedback_summary or 'No data yet'}
{avoid_block}
Task:
Propose exactly ONE topic idea for the next Instagram Reel that:
1. Stays within the primary domain
2. Uses today's angle/subcategory as the specific focus
3. Iterates on what performed best (if analytics data is available)
4. Has VERY strong hook potential — must create instant curiosity
5. Focuses on psychology, body language, attraction science, or behavioral insights
6. Is bold and intriguing WITHOUT being sexually explicit (Instagram-safe)
7. Is DIFFERENT from the recently used topics listed above

Great topic examples (for inspiration, don't copy exactly):
- Ek cheez jo ladkiyon ko turant attract karti hai
- Body language signs jo batati hain ke wo interested hai
- Psychology trick jo kisi ko bhi tumhari taraf kheench le
- 3 galtiyan jo ladke attraction mein karte hain
- Ankhen kaise reveal karti hain true feelings
- Red flags jo har ladke ko pehchanni chahiye
- Confidence ka wo secret jo koi nahi batata
- Kaise pata chale ke wo tumhare baare mein sochti hai

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _llm_prompt(prompt)
    lines = content.splitlines()
    if not lines:
        raise ValueError("LLM returned empty topic")
    return lines[0].strip()

