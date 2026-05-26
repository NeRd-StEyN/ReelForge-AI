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


def generate_script(topic, analytics_data=None, content_type="horror_reel"):
    """Generates a video script based on the topic, past analytics, and content type.
    
    content_type can be:
    - "horror_story": Longer narrative horror story with a girl protagonist (for story posts)
    - "horror_reel": Short, punchy mysterious horror reveal reel (for reels)
    - "girl_facts": Bold, seductive girl psychology / dating facts reel
    """
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

    if content_type == "horror_story":
        # Longer horror story format — 4 scenes, ~45-50 seconds
        prompt = f"""
    You are a viral Instagram horror storyteller specialized in mysterious, spine-chilling stories involving girls — haunted encounters, paranormal events, cursed places, ghost girls, and unexplained mysteries.
    Your audience is young people (18-30) who love short horror stories, creepy content, and mysterious girl-themed narratives.
    The content must be eerie, suspenseful, and deeply unsettling — the kind that makes people STOP scrolling and watch with goosebumps.
    {instructions}
    {language_rules}
    
    Create a gripping, terrifying horror STORY script for this topic: "{topic}".
    The story must feature a girl as the central mysterious/horror figure — a ghost girl, a cursed woman, a possessed girl, a mysterious stranger, etc.

    Story structure you must follow:
    - Scene 1: HOOK — Start with a terrifying, mysterious opening that instantly creates dread AND ends with an INCOMPLETE REVEAL that forces the viewer to keep watching (e.g. "us ladki ki aankhein khuli thi lekin wo zinda nahi thi... aur sabse darawni baat ye thi ki..."). The hook MUST leave a question unanswered.
    - Scene 2: BUILD — Introduce the eerie backstory. End this scene with an OPEN LOOP cliffhanger (e.g. "lekin jab unhone uska kamra khola toh jo dikha wo...", "par asli kahani toh tab shuru hui jab..."). NEVER resolve the mystery here — tease what's coming.
    - Scene 3: CLIMAX — The most terrifying moment. Escalate the horror but again end with a PATTERN INTERRUPT (e.g. "lekin ruko... sabse darawni baat toh ye hai..."). Make the viewer think they got the answer but reveal there's something WORSE.
    - Scene 4: TWIST ENDING — A chilling final revelation that NOBODY expected. This must completely flip the story. The payoff must be so shocking that viewers replay it and share it.

    CRITICAL RETENTION RULES (follow ALL of these or the script will FAIL):
    - EVERY scene MUST end with an open loop or cliffhanger — a sentence that starts a thought but doesn't finish it, forcing the viewer to stay for the next scene.
    - Use "lekin...", "par...", "aur jab...", "sabse darawni baat toh..." as transition bridges between scenes.
    - Scene 1 must create a CURIOSITY GAP — state something shocking but withhold the key detail.
    - Scene 2 must use ESCALATION — each detail must be scarier than the last, building toward something the viewer NEEDS to know.
    - Scene 3 must use a PATTERN INTERRUPT — just when the viewer thinks they know the ending, introduce a new terrifying element.
    - Scene 4 must deliver a DOPAMINE PAYOFF — the twist must be so good that the viewer feels compelled to rewatch, share, or comment.
    - NEVER reveal the main twist before Scene 4. The entire script must build toward ONE final shocking moment.
    - Use incomplete sentences as bridges: "aur phir jo hua..." "lekin kahani yahan khatam nahi hoti..." "par sabse bura toh ye tha ki..."

    Hard requirements:
    - First line must be a TERRIFYING hook that instantly stops scroll in under 10 words.
    - The story MUST feature a girl/woman as the central horror element.
    - Build suspense with each scene — each one must escalate the dread.
    - Use atmospheric, cinematic language — dark, foggy, cold, whispers, shadows.
    - Topics should revolve around: ghost girls, haunted places, cursed women, mysterious disappearances, possessed girls, paranormal encounters with women, urban legends about girls.
    - End with a twist that gives chills.
    - Script should read in about 45 to 55 seconds.
    - Target total word count around 120 to 150 words.
    - Keep language dark, mysterious, atmospheric, and conversational — like someone whispering a true horror story.
    - Stay within Instagram guidelines — scary but not gory/graphic.
    - Return exactly 4 scenes.
    - Each scene text must be one long flowing sentence (or two tightly connected clauses).
    - Keep each scene text around 30 to 40 words.
    - Avoid line breaks inside scene text.
    - Use natural connectors so narration sounds like one continuous horror story.
    - Every scene must have a distinct visual_keyword that returns dark, eerie, horror-themed footage from stock libraries.
    - visual_keyword MUST include atmospheric horror terms like: "dark forest fog night", "abandoned building shadows", "creepy girl dark hallway", "ghost woman white dress", "horror dark room candle", "mysterious woman fog cinematic" — spine-chilling visuals.
    - visual_keyword should feature girl/woman elements where possible for thematic consistency.
    - visual_keyword must target realistic footage (cinematic, dark lighting, fog, shadows), avoid cartoon/anime.
    
    Format the output as strict JSON with the following structure:
    {{
        "title": "A terrifying viral horror title",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken words for this scene",
                "visual_keyword": "Dark atmospheric horror term (e.g. 'creepy girl standing dark abandoned hallway fog cinematic')"
            }}
        ]
    }}
    Provide only the valid JSON, no markdown formatting blocks.
    """
    elif content_type == "girl_facts":
        # Bold girl facts reel — 3 scenes, ~30-35 seconds
        prompt = f"""
    You are a viral Instagram Reels strategist specialized in bold, seductive, and provocative content about girls, dating, and attraction.
    Your audience is young men (18-30) who love bold content about what girls secretly want, seduction, body language, and intimate dating dynamics.
    The content must be bold, flirty, and slightly naughty — the kind that makes guys STOP scrolling immediately.
    {instructions}
    {language_rules}
    
    Create a highly engaging, bold, seductive reel script for this topic: "{topic}".
    The content style must be provocative, flirty storytelling about girls' secret desires, seduction psychology, and bold dating truths.

    Retention framework you must follow:
    - Scene 1 HOOK: Start with a BOLD, slightly naughty hook that no guy can skip AND immediately create a CURIOSITY GAP — hint at something wild but don't reveal it (e.g. "ladkiyan raat ko akele mein ye sochti hain... aur teesri cheez sunke tum hil jaoge", "agar ladki ye karti hai toh iska matlab... lekin pehle do cheezein sun lo"). The hook MUST leave the viewer desperate to know what comes next.
    - Scene 2 BUILD: Tease with evidence and escalate the seduction — but end with an OPEN LOOP cliffhanger (e.g. "lekin jo baat koi nahi batata wo ye hai...", "aur sabse wild cheez toh ab aane wali hai..."). NEVER give the best reveal here — always promise something spicier in the next scene.
    - Scene 3 PAYOFF: Deliver the most mind-blowing, provocative truth. This must be SO good that guys feel they MUST share it, save it, or rewatch it. End with a mic-drop moment.

    CRITICAL RETENTION RULES (follow ALL of these or the script will FAIL):
    - EVERY scene transition MUST have an open loop — an incomplete thought that forces the viewer to keep watching.
    - Scene 1 must create IRRESISTIBLE CURIOSITY — state a bold claim but withhold the juiciest detail.
    - Scene 2 must use ESCALATION + TEASE — give a partial reveal that's exciting but hint that the REAL secret is still coming.
    - Scene 3 must deliver a DOPAMINE PAYOFF — the final reveal must be so bold and surprising that viewers replay it.
    - Use transition phrases like: "lekin ruko...", "aur sabse badi baat toh...", "par ye toh kuch nahi, asli raaz toh...", "number 3 sunke hosh ud jayenge..."
    - NEVER front-load the best content. The most shocking/exciting reveal MUST be in Scene 3.
    - The script must feel like peeling layers — each scene reveals something bolder than the last.

    Hard requirements:
    - First line must be a BOLD hook that instantly stops scroll in under 8 words.
    - The hook must be slightly naughty or seductive — trigger male fantasy and curiosity.
    - Use suggestive language that hints but doesn't cross into explicit territory (Instagram safe but bold).
    - Topics should revolve around: what girls secretly desire, seduction body language, things girls do when attracted, bedroom psychology, what turns girls on, intimate secrets girls never say out loud.
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
    else:
        # Short horror reel format — 3 scenes, ~30-35 seconds
        prompt = f"""
    You are a viral Instagram Reels strategist specialized in mysterious, spine-chilling, and creepy content about haunted girls, ghost stories, and paranormal encounters with women.
    Your audience is young people (18-30) who love horror content, mysterious stories about girls, and creepy unexplained phenomena.
    The content must be eerie, suspenseful, and deeply unsettling — the kind that makes people STOP scrolling and watch with goosebumps.
    {instructions}
    {language_rules}
    
    Create a highly engaging, terrifying reel script for this topic: "{topic}".
    The content style must be mysterious, horror-themed involving girls — ghost sightings, cursed women, haunted encounters, creepy girl behavior, paranormal female figures.

    Retention framework you must follow:
    - Scene 1 HOOK: Start with a TERRIFYING, mysterious hook that creates instant dread AND a CURIOSITY GAP — reveal something shocking but withhold the key detail (e.g. "raat ke 3 baje wo ladki phir dikhi... lekin is baar kuch alag tha", "us ladki ki photo mein kuch ajeeb tha... jo dekhne ke baad log phone phenk dete hain"). The viewer MUST feel they can't swipe away without knowing what happened.
    - Scene 2 BUILD: Escalate the horror with creepy evidence — but end with an OPEN LOOP cliffhanger (e.g. "lekin sabse darawni baat toh ye hai ki...", "aur jab unhone camera check kiya toh jo dikha wo..."). NEVER reveal the twist here — tease that the worst is yet to come.
    - Scene 3 PAYOFF: Deliver a BONE-CHILLING twist that nobody expected. The reveal must be so terrifying that viewers get actual goosebumps, rewatch it, and share it. End with a haunting final line.

    CRITICAL RETENTION RULES (follow ALL of these or the script will FAIL):
    - EVERY scene MUST end with an open loop or cliffhanger — an incomplete thought that makes it IMPOSSIBLE to swipe away.
    - Scene 1 must create MORBID CURIOSITY — state something terrifying but withhold the crucial detail that explains it.
    - Scene 2 must use FEAR ESCALATION — each detail scarier than the last, ending with "lekin ye toh kuch nahi... asli kahani toh ab shuru hoti hai..."
    - Scene 3 must deliver a SHOCK TWIST PAYOFF — the final reveal must flip everything the viewer assumed, giving them chills.
    - Use transition phrases like: "lekin ruko...", "par kahani yahan khatam nahi hoti...", "aur sabse bura toh ye tha ki...", "jab sach samne aaya toh..."
    - NEVER reveal the main horror before Scene 3. The entire script must build toward ONE terrifying final moment.
    - The script must feel like descending into darkness — each scene pulls the viewer deeper into the horror.

    Hard requirements:
    - First line must be a TERRIFYING hook that instantly stops scroll in under 8 words.
    - The hook must be eerie and mysterious — trigger fear and morbid curiosity.
    - Use dark, atmospheric language that creates a sense of dread (Instagram safe but deeply unsettling).
    - Topics should revolve around: ghost girls, haunted places where girls died, cursed women, mysterious girl disappearances, paranormal encounters with women, creepy things girls do at night, urban horror legends about girls, possessed girls, ghostly female figures.
    - End with a bone-chilling truth or terrifying twist.
    - Script should read in about 30 to 35 seconds (SHORT reels get higher completion rate = more views).
    - Target total word count around 80 to 100 words.
    - Keep language dark, mysterious, atmospheric, and conversational — like someone whispering a true horror story at midnight.
    - Stay within Instagram guidelines — scary but not gory/graphic.
    - Return exactly 3 scenes.
    - Each scene text must be one long flowing sentence (or two tightly connected clauses), not short choppy lines.
    - Keep each scene text around 25 to 35 words for fast punchy delivery.
    - Avoid line breaks inside scene text.
    - Use natural connectors so narration sounds like one continuous horror story.
    - Every scene must have a distinct visual_keyword that returns dark, eerie, horror-themed footage from stock libraries.
    - visual_keyword MUST include atmospheric horror terms like: "dark forest fog night", "abandoned building shadows", "creepy girl dark hallway", "ghost woman white dress", "horror dark room candle", "mysterious woman fog cinematic" — spine-chilling visuals.
    - visual_keyword should feature girl/woman elements where possible for thematic consistency.
    - visual_keyword must target realistic footage (cinematic, dark lighting, fog, shadows), avoid cartoon/anime.
    
    Format the output as strict JSON with the following structure:
    {{
        "title": "A terrifying viral horror title",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken words for this scene",
                "visual_keyword": "Dark atmospheric horror term (e.g. 'creepy girl standing dark abandoned hallway fog cinematic')"
            }}
        ]
    }}
    Provide only the valid JSON, no markdown formatting blocks.
    """

    return _openrouter_prompt(prompt)


def generate_script_payload(topic, analytics_data=None, max_repairs=2, content_type="horror_reel"):
    """Generate script and return a validated JSON payload with auto-repair retries."""
    raw = generate_script(topic, analytics_data, content_type=content_type)

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

def generate_topic_from_domain(domain, analytics_data=None, feedback_summary="", content_type="horror_reel"):
    """Generate the next reel/story topic inside one domain using recent performance feedback."""
    analytics_text = analytics_data if analytics_data else "No analytics yet"

    if content_type == "horror_story":
        prompt = f"""
You are a short-form horror content strategist specialized in mysterious, spine-chilling viral stories about girls and paranormal encounters.
Your target audience is young people (18-30) on Instagram who love horror stories, ghost girl narratives, and mysterious creepy content.

Domain to stay inside: "{domain}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram horror STORY (longer format) that stays inside the domain,
iterates on what performed best, and has VERY strong horror hook potential.
Topic must be mysterious, terrifying, and involve a girl — ghost encounter, cursed woman, haunted place, paranormal mystery.
The idea should naturally allow: a terrifying opening hook, suspenseful buildup, and a chilling twist ending.

Great topic examples (for inspiration, don't copy exactly):
- The ghost girl who appears every midnight at the old bridge
- She died 50 years ago but her room is still warm
- The cursed photograph that shows a girl nobody remembers
- A mysterious girl who knocks on doors at 3 AM
- The abandoned hospital where nurses still hear a girl crying
- She was found alive in a grave after 7 days
- The girl in the mirror who blinks when you don't
- A school's haunted floor where a girl vanished decades ago
- The last voicemail from a girl who was already dead

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""
    elif content_type == "girl_facts":
        prompt = f"""
You are a short-form content strategist specialized in bold, provocative viral reels about girls, seduction, and attraction.
Your target audience is young men (18-30) on Instagram who love bold, slightly naughty content about women's secret desires, dating, and seduction.

Domain to stay inside: "girl psychology and dating secrets"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that is bold, provocative, and seductive,
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
    else:
        prompt = f"""
You are a short-form horror content strategist specialized in mysterious, spine-chilling viral reels about girls and paranormal encounters.
Your target audience is young people (18-30) on Instagram who love horror content, ghost girl stories, and mysterious creepy reels.

Domain to stay inside: "{domain}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram horror REEL (short format) that stays inside the domain,
iterates on what performed best, and has VERY strong horror hook potential.
Topic must be mysterious, terrifying, and involve a girl — ghost sighting, cursed woman, haunted place, paranormal mystery.
The idea should naturally allow: a terrifying curiosity hook, creepy buildup, and a bone-chilling reveal.

Great topic examples (for inspiration, don't copy exactly):
- Signs a ghost girl is watching you right now
- 3 haunted places where girls died mysteriously
- Things possessed girls do at 3 AM that nobody talks about
- Why some girls see ghosts and others don't
- Creepy things girls have found in abandoned houses
- Real ghost girl encounters caught on camera
- The girl who predicted her own death
- 3 warning signs a girl near you is not human
- Mysterious disappearances of girls that were never solved

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    content = _openrouter_prompt(prompt)
    return content.splitlines()[0].strip()
