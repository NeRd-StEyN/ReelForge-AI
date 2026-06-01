import os
import json
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
    fallback_raw = (os.getenv("OPENROUTER_FALLBACK_MODELS") or "google/gemini-2.0-flash-001").strip()

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
    max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", "2500"))
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
- Keep the same schema with fields: title, scenes[].id, scenes[].text, scenes[].visual_keyword
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
    return payload

def generate_script(topic, analytics_data=None):
    """Generates a highly viral video script based on the topic and past analytics."""
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

    prompt = f"""
    You are a viral Instagram Reels strategist specialized in bold, seductive, and provocative content about girls, dating, and attraction.
    Your audience is young men (18-30) who love bold content about what girls secretly want, seduction, body language, and intimate dating dynamics.
    The content must be bold, flirty, and slightly naughty — the kind that makes guys STOP scrolling immediately.
    {instructions}
    {language_rules}
    
    Create a highly engaging, bold, seductive reel script for this topic: "{topic}".
    The content style must be provocative, flirty storytelling about girls' secret desires, seduction psychology, and bold dating truths.

    Retention framework you must follow:
    - Start with a BOLD, slightly naughty hook that no guy can skip (e.g. "ladkiyan raat ko akele mein ye sochti hain...", "agar ladki ye karti hai toh wo tumhe bed mein chahti hai...", "ye 3 cheezein ladkiyon ko pagal karti hain...").
    - Build the script as a seductive reveal: Bold claim -> Teasing evidence -> Mind-blowing intimate truth.
    - Keep sexual tension and curiosity alive throughout — always hint at something spicier coming next.
    - Each scene must drop a bold, slightly taboo insight that keeps the viewer glued.
    - The final scene must deliver a satisfying, provocative payoff.

    Hard requirements:
    - First line must be a BOLD hook that instantly stops scroll in under 8 words.
    - The hook must be slightly naughty or seductive — trigger male fantasy and curiosity.
    - Use suggestive language that hints but doesn't cross into explicit territory (Instagram safe but bold).
    - Topics should revolve around: what girls secretly desire, seduction body language, things girls do when attracted, bedroom psychology, what turns girls on, intimate secrets girls never say out loud.
    - Build open loops so viewer watches till end ("lekin jo baat koi nahi batata wo ye hai...", "aur sabse wild cheez toh ye hai...").
    - End with a bold, provocative truth or seduction tip.
    - Script should read in about 30 to 35 seconds (SHORT reels get higher completion rate = more views).
    - Target total word count around 80 to 100 words.
    - Keep language bold, flirty, street-smart, and conversational — like a wingman sharing secrets.
    - Stay within Instagram guidelines — suggestive but not explicit.
    - Return exactly 3 scenes.
    - Each scene text must be one long flowing sentence (or two tightly connected clauses), not short choppy lines.
    - Keep each scene text around 25 to 35 words for fast punchy delivery.
    - Avoid line breaks inside scene text.
    - Use natural connectors so narration sounds like one continuous seductive story.
    - Every scene must have a distinct visual_keyword that returns HOT, attractive woman footage from stock libraries.
    - visual_keyword MUST include bold terms like: "sexy woman dancing", "hot girl", "attractive model", "seductive woman", "girl in bikini", "woman body fitness" — eye-catching female visuals.
    - visual_keyword must target realistic footage (cinematic, slow motion, real people, aesthetic lighting), avoid cartoon/anime.
    
    Format the output as strict JSON with the following structure:
    {{
        "title": "A catchy bold viral title",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken words for this scene",
                "visual_keyword": "Bold visual term featuring hot women (e.g. 'sexy woman dancing in neon club lights slow motion cinematic')"
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

def generate_topic_from_domain(domain, analytics_data=None, feedback_summary=""):
    """Generate the next reel topic inside one domain using recent performance feedback."""
    analytics_text = analytics_data if analytics_data else "No analytics yet"

    prompt = f"""
You are a short-form content strategist specialized in bold, provocative viral reels about girls, seduction, and attraction.
Your target audience is young men (18-30) on Instagram who love bold, slightly naughty content about women's secret desires, dating, and seduction.

Domain to stay inside: "{domain}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that stays inside the domain,
iterates on what performed best, and has VERY strong hook potential.
Topic must be bold, provocative, and seductive — about what girls secretly want, seduction tricks, intimate female psychology, or bold dating truths.
The idea should naturally allow: a naughty curiosity hook, teasing buildup, and a provocative reveal.

Great topic examples (for inspiration, don't copy exactly):
- Things girls secretly want in bed but never say
- Body language signs she wants you to kiss her
- Why bad boys attract every girl effortlessly
- What girls do when they are turned on
- Seduction tricks that make any girl obsessed
- Things girls notice about your body first
- Why girls are attracted to guys who ignore them
- What her eyes tell you about her desires
- Secret things girls find irresistibly sexy

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _openrouter_prompt(prompt)
    return content.splitlines()[0].strip()
