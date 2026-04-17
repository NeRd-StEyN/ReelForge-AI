import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

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

def generate_script(topic, analytics_data=None):
    """Generates a highly viral video script based on the topic and past analytics."""

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
    You are a viral Instagram Reels strategist specialized in horror mystery content.
    {instructions}
    
    Create a highly engaging, suspenseful, fast-paced reel script for this topic: "{topic}".
    The content style must be horror or unsettling mystery, with curiosity and tension.

    Hard requirements:
    - First line must be a strong hook that instantly stops scroll in under 8 words.
    - Build open loops and tension every few lines so viewer wants to watch till end.
    - End with a payoff reveal or twist.
    - Script should read in about 40 to 55 seconds.
    - Keep language punchy and easy to understand.
    - Avoid explicit gore.
    - Return 6 to 8 scenes.
    - Each scene text should be short enough for readable subtitles.
    
    Format the output as strict JSON with the following structure:
    {{
        "title": "A catchy viral title",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken words for this scene",
                "visual_keyword": "Highly specific visual term to search stock footage for (e.g. 'mysterious dark galaxy space explosion')"
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
            return _parse_script_payload(raw)
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
You are a short-form content strategist specialized in horror reels.

Domain to stay inside: "{domain}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that stays inside the domain,
iterates on what performed best, and has very strong hook potential.
Topic must support a horror or unsettling mystery storytelling angle.

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _openrouter_prompt(prompt)
    return content.splitlines()[0].strip()
