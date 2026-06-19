import os
import json
import random
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def _get_content_language():
    return (os.getenv("CONTENT_LANGUAGE") or "hindi").strip().lower()

def get_openrouter_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables. Please add it to your .env file.")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def _get_model_candidates():
    primary = (os.getenv("OPENROUTER_MODEL") or "google/gemini-2.5-flash").strip()
    fallback_raw = (os.getenv("OPENROUTER_FALLBACK_MODELS") or "openrouter/free").strip()

    candidates = [primary]
    if fallback_raw:
        candidates.extend([m.strip() for m in fallback_raw.split(",") if m.strip()])

    # Preserve order while removing duplicates.
    unique = []
    seen = set()
    for model in candidates:
        if model not in seen:
            unique.append(model)
            seen.add(model)
    return unique


def _normalize_content(content):
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        content = "\n".join(parts)

    text = str(content or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _openrouter_prompt(prompt):
    client = get_openrouter_client()
    last_error = None
    max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", "1000"))
    max_tokens = max(256, min(max_tokens, 16000))

    for model in _get_model_candidates():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
            )
            return _normalize_content(response.choices[0].message.content)
        except Exception as exc:
            last_error = exc
            print(f"OpenRouter model failed ({model}): {exc}")

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
    return _openrouter_prompt(prompt)


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
]


def generate_script(topic, analytics_data=None):
    """Generates a highly viral, SHORT video script optimized for completion rate."""
    language = _get_content_language()
    language_rules = """
    Language rules:
    - Narration text must be in Hindi using Devanagari script.
    - Avoid English words unless absolutely unavoidable proper nouns.
    - Keep pronunciation natural for Hindi TTS.
    - Title can be Hindi or Hinglish, but scene narration must stay Devanagari Hindi.
    """ if language in {"hindi", "hi", "hi-in"} else ""

    instructions = ""
    if analytics_data and analytics_data != "No previous reels found. Start fresh!" and "Error" not in analytics_data:
        instructions = f"""
    CRITICAL ANALYTICS FEEDBACK:
    Here is the performance data for my recent videos: 
    {analytics_data}
    
    Look at which topics or styles got the HIGHEST views and likes. 
    Use that knowledge to brainstorm a hook and topic that expands on what the audience already loves!
    """

    # Rotate hook framework randomly for variety
    hook_framework = random.choice(_HOOK_FRAMEWORKS)

    prompt = f"""
    You are an expert Instagram Reels strategist. Your goal: maximum completion rate and engagement.
    Your audience is young men (18-30) on Indian Instagram who love bold, intriguing content about psychology, attraction, relationships, and human behavior.
    {instructions}
    {language_rules}
    
    Create a PUNCHY, fast-paced reel script for this topic: "{topic}".
    
    HOOK FRAMEWORK (you MUST use this style):
    {hook_framework['instruction']}

    ──── CRITICAL RULES FOR MAXIMUM VIEWS ────
    
    DURATION: This reel MUST be 15-22 seconds when spoken. This is NON-NEGOTIABLE.
    - Total word count: 45-65 words ONLY
    - Return exactly 2 scenes
    - Scene 1 (Hook + Setup): 20-30 words — grab attention + tease the revelation
    - Scene 2 (Payoff + Twist): 20-35 words — deliver the insight + end with a rewatch trigger
    
    RETENTION TACTICS:
    - First 2 seconds must be IMPOSSIBLE to skip — bold claim, shocking fact, or mid-story entrance
    - Scene 1 must create an open loop that Scene 2 closes
    - Scene 2 must end with a detail that makes the viewer want to watch AGAIN (rewatch trigger)
    - Keep language conversational, raw, street-smart — like a friend sharing secrets, not a textbook
    - Build tension: Scene 1 is the tease, Scene 2 is the mindblowing reveal
    
    PATTERN INTERRUPT:
    - Scene 1 and Scene 2 must feel VISUALLY and TONALLY different
    - Scene 1: mysterious, teasing energy
    - Scene 2: confident, revealing energy
    
    CONTENT BOUNDARIES:
    - Be intriguing and bold but stay Instagram-safe — NO explicit content
    - Focus on psychology, body language, behavioral insights, confidence, and attraction dynamics
    - Avoid overly suggestive or sexual language — Instagram's content classifier will suppress reach
    - Think "Psychology Today meets street wisdom" not "clickbait"
    
    VISUAL KEYWORDS:
    - Each scene must have a visual_keyword for stock footage search
    - Keywords should describe the MOOD and SETTING, not just "hot girl"
    - Good examples: "confident woman walking city street cinematic", "close up eyes mysterious lighting", "couple coffee shop candid moment"
    - Include lighting/mood descriptors: neon, golden hour, moody dark, bright aesthetic, cinematic
    - Each scene MUST have a different visual_mood (one of: mysterious, confident, dramatic, warm, dark, energetic, elegant)
    - Avoid repetitive stock-looking keywords — make each scene feel visually distinct
    
    Format the output as strict JSON:
    {{
        "title": "A catchy viral title (max 8 words)",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken narration for this scene",
                "visual_keyword": "Descriptive visual search term with mood and lighting",
                "visual_mood": "mysterious"
            }},
            {{
                "id": 2,
                "text": "The spoken narration for this scene",
                "visual_keyword": "Different visual search term with contrasting mood",
                "visual_mood": "confident"
            }}
        ]
    }}
    Provide only the valid JSON, no markdown formatting blocks.
    """

    return _openrouter_prompt(prompt)


def generate_script_payload(topic, analytics_data=None, max_repairs=2):
    """Generate script and return a validated JSON payload with auto-repair retries."""
    raw = generate_script(topic, analytics_data)

    for attempt in range(max_repairs + 1):
        try:
            payload = _parse_script_payload(raw)
            return _postprocess_script_payload(payload)
        except Exception as exc:
            if attempt >= max_repairs:
                raise RuntimeError(
                    f"Failed to parse script JSON after {max_repairs + 1} attempts: {exc}"
                ) from exc
            print(f"Script JSON invalid, attempting repair ({attempt + 1}/{max_repairs})...")
            raw = _repair_script_json(raw, str(exc))


# ── Topic sub-category rotation for content variety ──────────────────
_TOPIC_SUBCATEGORIES = [
    "psychology of attraction and what makes someone irresistible",
    "body language secrets that reveal hidden feelings",
    "relationship red flags and green flags everyone should know",
    "confidence and charisma tips that change how people see you",
    "surprising psychological facts about human behavior and desire",
    "dating mistakes that silently kill attraction",
    "eye contact and micro-expressions that reveal true intentions",
    "things people find attractive but never talk about",
    "social psychology hacks for better connections",
    "emotional intelligence and what makes someone magnetic",
]


def generate_topic_from_domain(domain, analytics_data=None, feedback_summary=""):
    """Generate the next reel topic inside one domain using recent performance feedback."""
    analytics_text = analytics_data if analytics_data else "No analytics yet"

    # Rotate through sub-categories for content variety
    subcategory = random.choice(_TOPIC_SUBCATEGORIES)

    prompt = f"""
You are a short-form content strategist specialized in viral Instagram Reels about psychology, attraction, and human behavior.
Your target audience is young men (18-30) on Indian Instagram.

Primary domain: "{domain}"
Today's angle/subcategory to focus on: "{subcategory}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that:
1. Stays within the primary domain
2. Uses today's angle/subcategory as the specific focus
3. Iterates on what performed best (if analytics data is available)
4. Has VERY strong hook potential — must create instant curiosity
5. Focuses on psychology, body language, attraction science, or behavioral insights
6. Is bold and intriguing WITHOUT being sexually explicit (Instagram-safe)

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

    content = _openrouter_prompt(prompt)
    return content.splitlines()[0].strip()
