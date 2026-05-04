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
    You are a viral Instagram Reels strategist specialized in girl psychology, dating secrets, and relationship content.
    Your audience is primarily young men (18-30) who are curious about female behavior, attraction, and dating dynamics.
    {instructions}
    {language_rules}
    
    Create a highly engaging, curiosity-driven reel script for this topic: "{topic}".
    The content style must be psychology-backed storytelling about girls, dating, and attraction with relatable hooks and emotional payoffs.

    Retention framework you must follow:
    - Start with a bold curiosity hook that makes every guy stop scrolling (e.g. "ladkiyan ye cheez sabse pehle notice karti hain...", "agar ladki ye karti hai toh samajh jao...").
    - Build the script as a reveal: Setup (surprising claim) -> Evidence (relatable examples) -> Payoff (mind-blowing insight or actionable tip).
    - Keep at least one unanswered question or "wait for it" moment active until the final scene.
    - Each scene must drop a new insight or fact that keeps the viewer hooked.
    - The final scene must deliver a satisfying "aha" moment or practical dating advice.

    Hard requirements:
    - First line must be a strong hook that instantly stops scroll in under 8 words.
    - The hook must trigger male curiosity about girls or attraction ("ye galti 90 percent ladke karte hain", "ladkiyon ko ye secretly pasand hai").
    - Build open loops so viewer watches till end ("lekin sabse important baat ye hai...", "aur teesri cheez sunke hosh ud jayenge").
    - End with a surprising twist, relatable truth, or powerful dating tip.
    - Script should read in about 55 to 60 seconds.
    - Target total word count around 150 to 170 words.
    - Keep language punchy, relatable, and conversational.
    - Content must be respectful and non-objectifying — focus on psychology, behavior, and attraction science.
    - Return 3 to 4 scenes.
    - Each scene text must be one long flowing sentence (or two tightly connected clauses), not short choppy lines.
    - Keep each scene text around 35 to 50 words to reduce frequent voice pauses.
    - Avoid line breaks inside scene text.
    - Use natural connectors (and, while, because, then) so narration sounds like one continuous story.
    - Avoid generic filler; every scene must add a new insight or escalation.
    - Every scene must have a distinct visual_keyword that returns attractive, relevant footage of women/couples/dating scenarios from stock libraries.
    - visual_keyword MUST include terms like: "beautiful woman", "attractive girl", "couple", "girl smiling", "woman confidence", "dating scene" — something that shows appealing female presence.
    - visual_keyword must target realistic footage (cinematic, photoreal, real people, aesthetic lighting), avoid cartoon/anime/illustration words.
    
    Format the output as strict JSON with the following structure:
    {{
        "title": "A catchy viral title",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken words for this scene",
                "visual_keyword": "Highly specific realistic visual term featuring women/couples (e.g. 'beautiful confident woman walking in city street cinematic golden hour')"
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
You are a short-form content strategist specialized in viral reels about girl psychology, dating, and attraction.
Your target audience is young men (18-30) on Instagram who love content about understanding women, dating tips, and relationship psychology.

Domain to stay inside: "{domain}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that stays inside the domain,
iterates on what performed best, and has very strong hook potential.
Topic must be about girl psychology, female behavior, dating secrets, attraction science, or relationship dynamics.
The idea should naturally allow: a bold curiosity hook, relatable buildup, and a surprising insight or tip.

Great topic examples (for inspiration, don't copy exactly):
- Signs she secretly likes you but will never tell
- Things girls notice in the first 5 seconds of meeting you
- Why girls lose interest after texting for too long
- The one thing that makes every girl feel special
- Body language tricks girls use when they are attracted
- Why girls test you and how to pass every time
- What girls actually want vs what they say they want

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _openrouter_prompt(prompt)
    return content.splitlines()[0].strip()
