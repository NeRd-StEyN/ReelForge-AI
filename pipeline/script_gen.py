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
_OPENROUTER_PRIMARY_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
_fallback_env = os.getenv("OPENROUTER_FALLBACK_MODELS", "openrouter/free,meta-llama/llama-3.3-70b-instruct:free,google/gemini-1.5-flash")
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
        "maxOutputTokens": 2048,
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
        "max_tokens": 1500,
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
        Provide a clear, highly practical action or solution the viewer can take today. Not abstract psychology, but a tangible fix.
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
    1. Generate 3 to 5 scenes (total 60-80 words across all scenes). This ensures a full 22-30 second reel.
    2. Each scene's `text` MUST be a complete spoken thought in pure Devanagari Hindi (15-25 words each).
    3. For `visual_keyword`, YOU MUST provide LITERAL, highly-specific human actions (e.g., "close up couple holding hands", "person looking at phone in dark", "woman smiling over shoulder"). DO NOT use abstract words like "psychology", "mind", or "brain". We need real human B-roll.
    4. Each scene MUST have a `visual_mood` (mysterious, confident, dramatic, intense, dark, energetic, elegant, or horror).
    5. Final scene MUST include a CTA for comments (poll or question) and share trigger.
    6. Output strict JSON only.

    JSON STRUCTURE:
    {{
        "title": "A catchy viral title (max 8 words)",
        "hook_framework": "curiosity_gap",
        "brainstorming_scratchpad": {{
            "problems": "List 3 specific pain points the audience has about this.",
            "hooks": "Brainstorm 5 distinct text hooks.",
            "selection": "Explain why the chosen hook is the best."
        }},
        "scenes": [
            {{
                "id": 1,
                "text": "Scene 1 narration (Hook — curious energy)",
                "on_screen_text": "Short 3-5 word scroll-stopping text (MUST be different from narration)",
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

    return _llm_prompt(prompt, json_mode=True)


def generate_script_payload(topic, analytics_data=None, feedback_summary="", max_repairs=2):
    """Generate script and return a validated JSON payload with auto-repair and retry loops."""
    if feedback_summary:
        print(f"[Feedback] Injecting performance history into script prompt.")

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
                
                # Retention Engineering Pass
                payload = _audit_script_payload(payload)
                
                return payload
            except Exception as exc:
                last_error = exc
                if attempt >= max_repairs:
                    print(f"[Script] Validation/repair attempt {attempt + 1} failed: {exc}")
                    break
                print(f"[Script] Script validation issue: {exc}. Attempting repair ({attempt + 1}/{max_repairs})...")
                raw = _repair_script_json(raw, str(exc))

    raise RuntimeError(f"Failed to generate a valid high-retention script: {last_error}")


def _audit_script_payload(payload):
    """Retention Engineering pass: audit the generated script for filler words and curiosity gaps."""
    import json
    print("[Script] Running Retention Engineering audit pass...")
    prompt = f"""
    You are a Retention Editor for Instagram Reels.
    Your task is to take this generated JSON script and optimize it for maximum retention.
    
    RULES:
    1. Remove all slow introductions, filler words, and unnecessary fluff.
    2. Shorten sentences to make them punchier.
    3. Maximize curiosity gaps in the on_screen_text and hook.
    4. Keep the exact same JSON schema and keys. Do not change the overall structure.
    
    Original Script JSON:
    {json.dumps(payload, ensure_ascii=False, indent=2)}
    
    Return only the optimized JSON.
    """
    optimized_raw = _llm_prompt(prompt, json_mode=True)
    try:
        optimized_payload = json.loads(optimized_raw)
        return optimized_payload
    except Exception as e:
        print(f"[Script] Audit pass failed to return valid JSON ({{e}}). Falling back to original payload.")
        return payload



# ── Topic sub-category pools for maximum retention & viral reach ──────
# Based on REAL analytics (July 2026):
# TIER 1A — Friendzone/Situationship/Mixed Signals: 2.5K-6.3K views (HIGHEST VIEWS)
# TIER 1B — Mirror Psychology & Eye Contact Secrets: 1.5K-3.5K views (HIGHEST SHARE RATE)
# TIER 2 HIGH — Eye contact, texting, jealousy: 800-2K views
# TIER 2 DARK — Dark psychology, power dynamics: emerging viral niche

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
    "why she texts you first but never asks to meet — decoded",
    "talking stage trap — signs she wants more vs just passing time",
    "Part 2: Escape The Friendzone Using This One Shift",
    "Part 2: Situationship Exit — How to Make Her Choose",
    "Part 3: The One Mindset That Breaks The Friendzone Forever",
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
    "she laughs at everything you say — mirror effect or just friendly?",
    "why she subconsciously changes her voice pitch around you — psychology",
]

_TOPIC_TIER2_HIGH = [
    # Eye contact & texting — proven 800-2K view range
    "eye contact secrets — what her first glance really reveals",
    "eye contact trap — why girls look away when you catch them watching",
    "texting psychology — what her reply speed actually means",
    "jealousy test — one move to check if she genuinely cares",
    "signs she's attracted but hiding it — body language tell",
    "what happens when you go silent — the power of withdrawal",
    "3 things that instantly kill attraction without you knowing",
    "the psychology of why being too available destroys attraction",
    "her smile decoded — the difference between polite and genuine",
    "why she watches your story but never replies to your texts",
    "double blue tick but no reply — what she's really thinking",
    "she said 'haha' — what different laughing responses actually mean",
    "when she starts sending you memes — attraction signal decoded",
    "why she gets angry when you ignore her — psychology explained",
    "the 3-day rule — does going silent make her miss you more?",
    "she replied instantly then suddenly went slow — what changed?",
    "why she says 'I'm fine' but clearly isn't — female psychology",
    "what it means when she keeps bringing up her ex in conversation",
]

_TOPIC_TIER2_DARK = [
    # Dark psychology & power dynamics — emerging viral niche for 18-30 male audience
    "dark psychology tricks she uses when she wants your attention",
    "why she plays hard to get — the psychological game behind it",
    "push-pull psychology — why she gets closer when you pull away",
    "the silent treatment — psychological power move or genuine hurt?",
    "why ignoring her completely changes her behavior — dark psychology",
    "she's testing your confidence — here's how to pass every time",
    "manipulation vs testing — how to tell the difference instantly",
    "why she gets cold right when things were getting good — decoded",
    "social proof psychology — why she wants you more when others do",
    "the scarcity principle — why less availability creates more attraction",
    "why she tells her friends about you before telling you she likes you",
    "gaslighting vs mixed signals — learn the difference before it's too late",
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

    # Strict pool: ONLY TIER 1 topics (proven viral: Friendzone & Mirroring)
    # TIER 2 HIGH was removed as per your request to strictly stick to the best performers.
    women_topics_pool = (
        _TOPIC_TIER1A_FRIENDZONE
        + _TOPIC_TIER1B_MIRROR
    )
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
4. CRITICAL: NEVER suggest topics about dark psychology, manipulation, gaslighting, or toxic behavior. Instagram's classifier suppresses these topics to 100 views. Keep it positive, analytical, and safe.
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
Propose exactly ONE core emotional problem or burning question for the next Instagram Reel that:
1. Strictly adheres to today's Target Niche guidelines listed above
2. Represents a specific, painful, or confusing situation the audience faces (e.g. "I don't know if she is testing me or friendzoning me").
3. Is bold, relatable, street-smart, and Instagram-safe
4. Is DIFFERENT from the recently used problems listed above

Return only a single plain-text problem statement, max 15 words, no quotes, no numbering.
"""

    content = _llm_prompt(prompt)
    lines = content.splitlines()
    if not lines:
        raise ValueError("LLM returned empty topic")
    return lines[0].strip()

