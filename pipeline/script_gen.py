import os
import json
import random
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Model configuration ──────────────────────────────────
# 1. Google Gemini via Google AI Studio (100% Free: 1500 req/day, native JSON & Hindi)
_GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]

# 2. OpenRouter fallback models
_OPENROUTER_PRIMARY_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash")
_fallback_env = os.getenv("OPENROUTER_FALLBACK_MODELS", "google/gemini-2.0-flash-exp:free,google/gemini-1.5-flash,openrouter/free")
_OPENROUTER_FALLBACK_MODELS = [m.strip() for m in _fallback_env.split(",") if m.strip()]
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def _get_content_language():
    return (os.getenv("CONTENT_LANGUAGE") or "hindi").strip().lower()

# Phrases that signal Gemini or other models are leaking chain-of-thought reasoning.
_THINKING_PREAMBLE_PATTERNS = [
    "here's a thinking process",
    "here is a thinking process",
    "here's my thinking",
    "here is my thinking",
    "let me think through",
    "let me analyze",
    "let me break this down",
    "thinking process:",
    "my thought process",
    "step-by-step thinking",
    "**analyze the request",
    "1.  **analyze",
    "1. **analyze",
]


def _strip_thinking_preamble(text: str) -> str:
    """Remove chain-of-thought preamble from plain text responses."""
    lower = text.lower()
    is_thinking = any(lower.startswith(p) or lower[:120].find(p) != -1
                      for p in _THINKING_PREAMBLE_PATTERNS)
    if not is_thinking:
        return text

    print("[LLM] Detected thinking preamble in response — stripping chain-of-thought...")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    for para in reversed(paragraphs):
        lines = para.splitlines()
        first_line = lines[0].strip() if lines else ""
        if first_line.startswith(("#", "**", "*", "-", "1.", "2.", "3.")):
            continue
        lower_para = para.lower()
        if any(skip in lower_para for skip in (
            "here's the", "here is the", "final answer", "the comment is",
            "output:", "result:", "answer:"
        )):
            after = para.split(":", 1)[-1].strip()
            if after:
                return after
            continue
        if len(para) > 5:
            return para

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else text


def _extract_json_block(text):
    content = str(text or "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start : end + 1]
    return content


def _normalize_content(content, json_mode=False):
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
    text = text.strip()

    # For JSON mode, extract the JSON object directly — NEVER strip paragraphs with preamble stripper
    if json_mode:
        return _extract_json_block(text)

    # Strip thinking preamble only on plain-text prompts (captions, topics, etc.)
    return _strip_thinking_preamble(text)


def _call_gemini_direct(prompt, model="gemini-2.0-flash", json_mode=False):
    """Call Google Gemini API directly (100% Free via Google AI Studio).
    
    Provides best-in-class Hindi Devanagari generation and guaranteed JSON output.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    generation_config = {
        "temperature": 0.7,
        "maxOutputTokens": 3000,
    }
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini returned empty candidates: {data}")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError(f"Gemini response missing text parts: {data}")

    return parts[0].get("text", "")


def _call_openrouter(prompt, model, json_mode=False):
    """Call OpenRouter API with a given model. Returns response text."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
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
        "max_tokens": 2500,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(_OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _llm_prompt(prompt, json_mode=False):
    """Call LLM with Google Gemini (Free via AI Studio) as primary, falling back to OpenRouter."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    # ── 1. Priority 1: Google Gemini (100% Free, Native Hindi & JSON) ──
    if gemini_key:
        for model in _GEMINI_MODELS:
            try:
                print(f"[LLM] Using Google Gemini ({model})...")
                raw = _call_gemini_direct(prompt, model=model, json_mode=json_mode)
                return _normalize_content(raw, json_mode=json_mode)
            except Exception as exc:
                print(f"[LLM] Gemini {model} error: {exc}. Trying fallback...")
                time.sleep(1)

    # ── 2. Priority 2: OpenRouter ──
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        models_to_try = [_OPENROUTER_PRIMARY_MODEL] + _OPENROUTER_FALLBACK_MODELS
        last_error = None
        for model in models_to_try:
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    print(f"[OpenRouter] Using model: {model} (attempt {attempt + 1})")
                    raw = _call_openrouter(prompt, model, json_mode=json_mode)
                    return _normalize_content(raw, json_mode=json_mode)
                except Exception as exc:
                    last_error = exc
                    error_str = str(exc)
                    if "429" in error_str or "rate" in error_str.lower():
                        time.sleep(5 * (attempt + 1))
                        continue
                    print(f"[OpenRouter] {model} failed: {exc}. Trying next model...")
                    break
        raise RuntimeError(f"All LLM models failed. Last error: {last_error}")

    raise RuntimeError("Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is configured.")


# Dummy placeholder phrases that signify a model gave a broken template
_DUMMY_SAMPLE_PATTERNS = [
    "sample title", "sample text", "sample video", "sample narration",
    "placeholder", "insert title here", "insert text here"
]


def _validate_script_payload(payload):
    """Strict anti-dummy guardrails to prevent 5-second reels and placeholder text."""
    if not isinstance(payload, dict):
        raise ValueError("Script payload is not a JSON object")

    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("Script payload missing required field: title")

    for bad in _DUMMY_SAMPLE_PATTERNS:
        if bad in title.lower():
            raise ValueError(f"Script payload rejected: title contains dummy placeholder '{title}'")

    scenes = payload.get("scenes", [])
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise ValueError("Script payload missing list field: scenes")

    # Guardrail: Must have at least 3 scenes (prevent 1-scene 5-second videos)
    if len(scenes) < 3:
        raise ValueError(f"Script payload rejected: only {len(scenes)} scenes generated. Reels need at least 3-4 scenes for 20-30s duration.")

    total_words = 0
    has_hindi = False

    for idx, s in enumerate(scenes):
        if not isinstance(s, dict):
            raise ValueError(f"Scene {idx+1} is not a valid object")
        stext = str(s.get("text", "")).strip()
        if not stext:
            raise ValueError(f"Scene {idx+1} has empty text")

        for bad in _DUMMY_SAMPLE_PATTERNS:
            if bad in stext.lower():
                raise ValueError(f"Scene {idx+1} rejected: contains dummy placeholder '{stext}'")

        vkey = str(s.get("visual_keyword", "")).strip().lower()
        for bad in _DUMMY_SAMPLE_PATTERNS:
            if bad in vkey:
                raise ValueError(f"Scene {idx+1} rejected: visual_keyword contains placeholder '{vkey}'")

        words = stext.split()
        total_words += len(words)
        if any("\u0900" <= ch <= "\u097F" for ch in stext):
            has_hindi = True

    # Guardrail: Minimum 35 words across scenes (each word ~0.3s -> at least ~15-25s video)
    if total_words < 35:
        raise ValueError(f"Script payload rejected: script has only {total_words} words. Minimum required is 35 words to ensure a 20-30s reel.")

    # Guardrail: If Hindi language, verify Devanagari script is actually present
    if _get_content_language() in {"hindi", "hi", "hi-in"} and not has_hindi:
        raise ValueError("Script payload rejected: CONTENT_LANGUAGE is hindi but scenes contain no Devanagari characters.")

    return True


def _parse_script_payload(raw_text):
    clean_json = _extract_json_block(raw_text)
    payload = json.loads(clean_json)
    _validate_script_payload(payload)
    return payload


def _repair_script_json(raw_text, error_message):
    prompt = f"""
You must fix malformed JSON and return valid JSON only.

Rules:
- Keep the same schema with fields: title, scenes[].id, scenes[].text, scenes[].visual_keyword, scenes[].visual_mood
- CRITICAL: Provide realistic, full Hindi (Devanagari) script narration for each scene. NEVER output placeholder or dummy words like "Sample", "Sample text", or "Sample Title".
- Each scene must have complete spoken sentences (at least 15-20 words per scene, 3-4 scenes total).
- Do not add markdown fences.
- Escape quotes correctly.
- Ensure valid commas and brackets.

Previous parser error:
{error_message}

Malformed content:
{raw_text}
"""
    return _llm_prompt(prompt, json_mode=True)


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


# ── Hook framework rotation for maximum variety & emotional tension ──
_HOOK_FRAMEWORKS = [
    {
        "name": "situational_dilemma",
        "instruction": "Open with an ultra-relatable real-life situation. Example pattern: 'Jab wo ek din 2 minute mein reply kare aur agle din 10 ghante gayab... toh iska matlab samjho.' or 'Ever noticed her mood shift the second you stop texting first?'",
    },
    {
        "name": "contrarian_truth",
        "instruction": "Shatter a common belief with psychological reality. Example pattern: 'Har ladka sochta hai ki 24 ghante available rehna care dikhata hai, lekin female psychology kehti hai ye attraction ko destroy karta hai.'",
    },
    {
        "name": "micro_body_language",
        "instruction": "Decode a subtle, subconscious physical gesture. Example pattern: 'Jab koi ladki baat karte waqt bar bar eye contact break karke subtle smile kare, uska subconscious ye bol raha hota hai.'",
    },
    {
        "name": "the_curiosity_test",
        "instruction": "Frame an instant interactive test. Example pattern: 'Ye 5-second psychology test bata dega ki wo tumhe dost samajhti hai ya something more.' First frame must establish high stakes.",
    },
    {
        "name": "kabhii_nahi",
        "instruction": "Open with a punchy 'kabhi nahi' statement in Devanagari Hindi. Example: 'ये 3 गलतियां लड़कियां कभी उस लड़के के साथ नहीं करतीं जिसे वो पसंद करती हैं!' Full sentence on the very first frame.",
    },
    {
        "name": "unspoken_female_rule",
        "instruction": "Expose an unspoken behavioral dynamic. Example pattern: 'लड़कियों का एक unspoken rule होता है जो वो कभी मुंह से नहीं बोलेंगी, बस उनके behavior में दिखेगा...'",
    },
    {
        "name": "eye_contact_tension",
        "instruction": "Focus on gaze and tension. Example pattern: 'Jab wo kisi aur se baat karte hue bhi bar-bar tumhari taraf dekhe, toh dimaag mein kya chal raha hota hai? Decoded.'",
    },
    {
        "name": "withdrawal_effect",
        "instruction": "Focus on emotional boundaries and mystery. Example pattern: 'Jaise hi tum chase karna band karte ho, achanak uska interest kyu badh jata hai? Understand the psychology behind pull-back.'",
    },
]


def _pick_hook_framework(analytics_data=None, feedback_summary=""):
    """Choose a diverse hook framework to ensure constant variety and pattern interrupts."""
    chosen = random.choice(_HOOK_FRAMEWORKS)
    print(f"[HookEngine] Selected hook framework: '{chosen['name']}'")
    return chosen


def generate_script(topic, analytics_data=None, feedback_summary=""):
    """Generates a highly viral, punchy video script optimized for completion rate and natural conversational flow."""
    language = _get_content_language()
    language_rules = """
    Language rules:
    - Narration text MUST be in natural, conversational Hindi using STRICTLY Devanagari script (e.g. "लड़कियां" NOT "ladkiyan").
    - Keep pronunciation natural for Hindi TTS. Use conversational phrasing that flows smoothly when spoken.
    - CRITICAL: The `title` and `on_screen_text` MUST be in English or Roman Hinglish. NEVER use Devanagari script for titles or on-screen banners.
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
            print(f"[Series] Sequenced continuation detected! Injected previous script context.")
    except Exception as e:
        print(f"[Series] Warning check: could not fetch previous script context: {e}")

    # Build performance feedback block for the LLM
    instructions = ""
    if feedback_summary and feedback_summary.strip():
        instructions = f"""
    ══ REAL PERFORMANCE INSIGHTS ══
    {feedback_summary}
    ═══════════════════════════════
    Use this to craft a fresh, high-retention angle that outperforms previous reels.
    """

    hook_framework = _pick_hook_framework(analytics_data=analytics_data, feedback_summary=feedback_summary)

    prompt = f"""
    You are an expert viral content creator specializing in human behavior, relationship dynamics, and attraction psychology for Instagram Reels.
    Target Audience: Young men (18-30) in India looking for genuine, street-smart psychological clarity.
    Tone: Confident, insightful, relatable, like an older brother sharing game-changing truths. Not academic, not robotic, not depressing.

    Topic: "{topic}"
    Hook Framework: {hook_framework['name']} - {hook_framework['instruction']}
    {instructions}
    {language_rules}
    {previous_script_context}

    ── RETENTION & ENGAGEMENT BLUEPRINT (20–25 SECONDS TOTAL) ──
    Total Script Length: 55 to 75 spoken Hindi words across EXACTLY 3 or 4 scenes.
    
    Scene Breakdown:
    - Scene 1 (THE HOOK — 4-6s, 12-16 words):
      Voiceover MUST start INSTANTLY with an impossible-to-skip curiosity gap or relatable scenario.
      No intro, no fluff, no "Namaste". Launch right into the revelation or dilemma.
      Provide a punchy 3-5 word English/Hinglish `on_screen_text` hook that stops the thumb scroll.
    
    - Scene 2 (THE CORE PSYCHOLOGICAL TRUTH — 6-8s, 16-22 words):
      Explain the real subconscious mechanism or reason behind this behavior.
      Keep it grounded in human nature (e.g. how perception of value, comfort, or mystery actually works).
    
    - Scene 3 (THE TACTICAL SHIFT — 6-8s, 16-22 words):
      Deliver a clear, actionable mindset shift or practical response. What should the viewer actually do or understand?
    
    - Scene 4 (ENGAGEMENT, SHARE & INFINITE WATCH-LOOP — 4-5s, 10-14 words):
      End with a conversational question that naturally makes viewers want to share their opinion in comments.
      Include a natural share trigger (e.g., "Send this to a friend who needs this reminder").
      MANDATORY INFINITE WATCH-LOOP: The final 2-4 words of Scene 4 MUST be written so they seamlessly connect back into the beginning of Scene 1 when the video loops automatically (e.g. ending with "...और यही वजह है कि" or "...पर क्या तुम जानते हो कि", looping right into Scene 1). This tricks viewers into rewatching the hook and drives average watch time over 100%.

    RULES:
    1. Narration text (`text`) MUST be in fluent, natural Devanagari Hindi. Use conversational, punchy sentence rhythm.
    2. NEVER use generic AI cliches ("dekho dosto", "aaj hum baat karenge", "psychology kehti hai").
    3. `title`: Catchy English hook title (3-6 words, e.g. "The Silent Withdrawal Effect", "Testing or Disinterested?").
    4. `visual_keyword`: Provide cinematic, SITUATIONAL B-roll search terms (e.g. "man checking phone in dark room", "couple awkward silence cafe", "woman looking away contemplative street", "friends talking city night"). Avoid generic abstract words like 'psychology' or 'brain'.
    5. Output STRICT JSON ONLY. Do NOT include markdown code fences or conversational text.

    JSON SCHEMA:
    {{
        "title": "Catchy Viral Title",
        "hook_framework": "{hook_framework['name']}",
        "scenes": [
            {{
                "id": 1,
                "text": "Scene 1 Hindi narration in Devanagari",
                "on_screen_text": "3-5 word English hook",
                "visual_keyword": "cinematic situational b-roll term",
                "visual_mood": "mysterious",
                "emotional_beat": "curious"
            }},
            {{
                "id": 2,
                "text": "Scene 2 Hindi narration in Devanagari",
                "visual_keyword": "cinematic b-roll term",
                "visual_mood": "dramatic",
                "emotional_beat": "tense"
            }},
            {{
                "id": 3,
                "text": "Scene 3 Hindi narration in Devanagari",
                "visual_keyword": "cinematic b-roll term",
                "visual_mood": "confident",
                "emotional_beat": "enlightened"
            }},
            {{
                "id": 4,
                "text": "Scene 4 Hindi narration in Devanagari with comment trigger",
                "visual_keyword": "cinematic b-roll term",
                "visual_mood": "warm",
                "emotional_beat": "empowered"
            }}
        ]
    }}
    """

    return _llm_prompt(prompt, json_mode=True)


def generate_script_payload(topic, analytics_data=None, feedback_summary="", max_repairs=2):
    """Generate script and return a validated JSON payload with auto-repair and retry loops."""
    if feedback_summary:
        print("[Feedback] Injecting performance history into script prompt.")

    last_error = None
    for gen_attempt in range(2):
        try:
            raw = generate_script(topic, analytics_data=analytics_data, feedback_summary=feedback_summary)
        except Exception as gen_err:
            print(f"[Script] Generation attempt {gen_attempt + 1} failed: {gen_err}")
            last_error = gen_err
            continue

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
                last_error = exc
                if attempt >= max_repairs:
                    print(f"[Script] Validation/repair attempt {attempt + 1} failed: {exc}")
                    break
                print(f"[Script] Script validation issue: {exc}. Attempting repair ({attempt + 1}/{max_repairs})...")
                raw = _repair_script_json(raw, str(exc))

    raise RuntimeError(f"Failed to generate a valid high-retention script: {last_error}")


# ── Strategic Topic Pillars for Rich, Diverse Content ─────────────────
# 6 High-Performance Pillars designed to avoid audience fatigue:

_PILLAR_BODY_LANGUAGE = [
    "micro-expressions when someone is hiding attraction",
    "eye contact dynamics — what looking away downward vs to the side means",
    "the subtle physical proximity test people do without realizing",
    "nervous fidgeting vs comfortable silence in conversation",
    "voice pitch changes when talking to someone she finds attractive",
    "the head tilt and exposed wrist gesture decoded",
    "genuine smile vs polite social smile — how to spot the difference instantly",
    "why people touch their hair or neck when feeling emotional tension",
    "subconscious pupil dilation and what eye focus reveals",
    "directional feet placement — where someone's subconscious interest lies",
    "mirroring body language naturally vs faking it",
    "what prolonged eye contact in a crowd actually indicates",
    "the difference between friendly laughter and attraction laughter",
    "crossing arms — defensive barrier or just feeling cold?",
    "micro-glances across the room when they think you aren't looking",
    "the sudden adjustment of clothes or hair when you enter the room",
    "how body language changes when someone feels intimidated vs interested",
    "touch barriers — accidental touches that aren't actually accidental",
    "why confident silence is more attractive than constant talking",
    "facial tension signs when someone wants to text you but resists",
]

_PILLAR_TEXTING_DIGITAL = [
    "why she views your stories in seconds but replies to texts after hours",
    "the psychology behind sudden dry one-word replies",
    "late-night texting vs daytime texting dynamics explained",
    "the double-text dilemma — when it works and when it destroys leverage",
    "what it means when someone sends voice notes instead of typing",
    "the sudden shift from paragraphs to short replies decoded",
    "social media soft-launching and what profile interactions reveal",
    "the 24-hour reply delay — strategic calculation or disinterest?",
    "why people keep someone on delivered while staying active online",
    "meme-sharing psychology — the modern talking stage currency",
    "how to reset the vibe when a text conversation starts dying",
    "the unsend button psychology — what impulsive unsending reveals",
    "why asking open-ended questions beats the boring interview format",
    "what sudden disappearance followed by a random meme means",
    "the psychology of left on read — how to handle it with high value",
    "typing indicator anxiety and modern digital attachment",
    "why over-texting kills attraction before the first meetup",
    "the difference between texting for attention vs texting for connection",
    "how to transition from digital chat to real-world plans effortlessly",
    "why people check your profile repeatedly when there is silent friction",
]

_PILLAR_MIXED_SIGNALS_TESTS = [
    "compliance tests vs genuine boundaries — how to tell the difference",
    "the hot-and-cold cycle — why people pull back right when it gets close",
    "priority vs emotional backup — 3 brutal indicators of where you stand",
    "why some people test your emotional stability when they like you",
    "mixed signals mean one thing: mixed interest decoded",
    "the talking stage trap — how to avoid staying stuck for months",
    "why bringing up other suitors is often a subtle qualification test",
    "situationships vs intentional dating — recognizing the signs early",
    "the difference between playing hard to get and genuinely not caring",
    "what happens when you refuse to react to emotional bait",
    "how to handle unexpected cancellations with supreme calm",
    "the sudden cold shoulder after a great conversation explained",
    "why validation seekers keep you hooked without ever progressing",
    "the difference between healthy independence and emotional unavailability",
    "when someone says they are 'not ready for a relationship right now'",
    "testing your boundaries — why setting clear limits increases respect",
    "how to respond when someone gives you mixed signals repeatedly",
    "the fear of vulnerability masked as emotional coolness",
    "why over-explaining yourself instantly fails subtle tests",
    "the moment you stop chasing — how mixed signal givers react",
]

_PILLAR_ATTRACTION_SCARCITY = [
    "the scarcity principle — why 24/7 availability destroys attraction",
    "why people value what they have to invest effort to earn",
    "the quiet confidence shift that changes how others treat you",
    "why desperate approval-seeking repels emotional connection",
    "the art of holding your ground without getting aggressive",
    "why chasing validation from outside makes you easy to manipulate",
    "the power of walking away when your value isn't respected",
    "why emotional self-control is the rarest modern superpower",
    "the danger of putting anyone on an imaginary pedestal",
    "how having a mission outside dating naturally builds attraction",
    "why agreeing with everything makes conversations utterly boring",
    "the difference between arrogance and unshakeable self-respect",
    "why mystery and personal boundaries create natural intrigue",
    "the psychological cost of constantly apologizing for existing",
    "how needy energy leaks through even the smoothest words",
    "why people respect those who are comfortable saying 'no'",
    "the attraction law: you attract what you accept, not what you want",
    "why losing yourself to please someone always leads to heartbreak",
    "the difference between being kind and being a people-pleaser",
    "why high-value people never compete for someone's basic attention",
]

_PILLAR_CONTRARIAN_TRUTHS = [
    "the 'nice guy' paradox — why harmlessness is not the same as goodness",
    "what people say they want vs what actually sparks chemistry",
    "why being too understanding often leads to being taken for granted",
    "the brutal truth about being 'too nice' in early talking stages",
    "why people fall for emotional predictability vs dynamic presence",
    "the myth that effort equals attraction — the law of emotional return",
    "why closure is a myth and self-respect is the real answer",
    "the paradox of choice in modern dating — why more options make people lonelier",
    "why trying to 'fix' someone is a disguised ego trap",
    "the difference between genuine chemistry and trauma bonding",
    "why people stay in toxic dynamics longer than healthy ones",
    "the illusion of the 'one that got away' explained psychologically",
    "why silence after disrespect speaks louder than angry arguments",
    "the psychology of why jealousy is a confession of insecurity",
    "why unconditional support before commitment gets you friendzoned",
    "the brutal reality of emotional rebound connections",
    "why self-respect is the ultimate filter for genuine people",
    "the psychology of regret: why people only miss you after you move on",
    "why being comfortable alone makes you magnetic to others",
    "the truth about why people ghost instead of having an honest conversation",
]

_PILLAR_CONVERSATION_TENSION = [
    "how to break out of the boring interview mode in conversations",
    "the power of playful teasing vs boring validation in banter",
    "how to handle awkward silences without rushing to fill them",
    "the secret to storytelling that holds anyone's full attention",
    "why reacting less makes your words carry ten times more weight",
    "how to create emotional peaks and valleys in everyday talks",
    "the difference between being funny and being a clown for approval",
    "how to disagree playfully without creating bitter conflict",
    "the art of the pause — why slowing down your speech commands respect",
    "how to ask questions that make people open up about their passions",
    "why listening to what is NOT said is the ultimate social skill",
    "how to give compliments that feel genuine rather than desperate",
    "the psychology of conversational rhythm — matching energy effectively",
    "how to steer conversations away from mundane small talk",
    "why holding back personal details creates intense curiosity",
    "how to exit a conversation at the peak to leave them wanting more",
    "the power of self-deprecating humor without destroying your status",
    "how to respond to backhanded compliments with effortless composure",
    "the difference between deep conversation and trauma dumping",
    "why charismatic people make others feel like the only person in the room",
]

_ALL_PILLARS = [
    ("Body Language & Micro-Signals", _PILLAR_BODY_LANGUAGE),
    ("Texting & Digital Psychology", _PILLAR_TEXTING_DIGITAL),
    ("Mixed Signals & Attraction Tests", _PILLAR_MIXED_SIGNALS_TESTS),
    ("Attraction Physics & Scarcity", _PILLAR_ATTRACTION_SCARCITY),
    ("Contrarian Truths & Human Nature", _PILLAR_CONTRARIAN_TRUTHS),
    ("Conversation & Emotional Tension", _PILLAR_CONVERSATION_TENSION),
]


def generate_topic_from_domain(domain, analytics_data=None, feedback_summary="", used_topics=None):
    """Generate the next reel topic dynamically across 6 core psychology & attraction pillars."""
    used_topics_set = used_topics or set()
    avoid_block = ""
    if used_topics_set:
        recent_list = ", ".join(f'"{t}"' for t in list(used_topics_set)[-40:])
        avoid_block = f"""
CRITICAL DEDUPLICATION RULE:
Do NOT repeat or copy any of these recently used topics/problems:
{recent_list}
Your new topic MUST explore a fresh, distinctive scenario or angle that has NOT been covered recently.
"""

    # Pick a random pillar and seed angle to guarantee fresh content variety
    pillar_name, seed_pool = random.choice(_ALL_PILLARS)
    seed_angle = random.choice(seed_pool)
    print(f"[TopicEngine] Active Pillar: '{pillar_name}' | Seed Angle: '{seed_angle}'")

    prompt = f"""
You are a viral Instagram Reels strategist who understands human psychology, attraction dynamics, and young male relationship dilemmas in India (age 18-30).

Domain: "{domain}"
Current Strategic Pillar: "{pillar_name}"
Seed Concept for inspiration: "{seed_angle}"
{avoid_block}

Task:
Formulate exactly ONE fresh, high-curiosity emotional dilemma, burning question, or psychological truth for the next Instagram Reel that:
1. Addresses a specific, relatable real-world situation young men encounter in modern dating, texting, or social dynamics.
2. Has immediate scroll-stopping curiosity (makes someone think: "Wait, why does this happen?").
3. Is street-smart, psychologically grounded, and 100% Instagram-safe (no toxic manipulation or explicit content).
4. Is DIFFERENT from the recently used topics listed above.

Return ONLY a single plain-text statement or question, max 14 words, no quotes, no numbering.
"""

    content = _llm_prompt(prompt)
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        raise ValueError("LLM returned empty topic")
    topic = lines[0].strip(' "\'')
    return topic


