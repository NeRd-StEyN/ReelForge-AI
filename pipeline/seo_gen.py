import json
import random
from pipeline.script_gen import _llm_prompt


def _get_insta_handle():
    user = (os.getenv("INSTA_USERNAME") or "itsun.known6969").strip()
    return f"@{user}" if not user.startswith("@") else user


def _generate_ai_caption(topic, script_data):
    """Use LLM to generate a short, engaging, topic-specific caption with a debate-starter CTA."""
    title = script_data.get("title", topic)
    hook_framework = script_data.get("hook_framework", "")
    scene_texts = " | ".join(
        s.get("text", "")[:60] for s in script_data.get("scenes", [])
    )
    handle = _get_insta_handle()

    # Extra instruction for test_format framework (our highest performer)
    test_format_tip = ""
    if hook_framework in ("test_format", "kabhii_nahi"):
        test_format_tip = """
SPECIAL RULE for this hook framework: The first line MUST use either:
  (a) 'Test' framing: 'Friendzone Test: [short consequence]' style, OR
  (b) Incomplete sentence with '...' that cuts off: 'लड़कियां कभी नहीं...'
This is our PROVEN highest-performing opener style on this account."""

    prompt = f"""
You are an Instagram caption specialist for viral relationship & psychology Reels.
Write a SHORT, magnetic caption for this reel.

Reel title: "{title}"
Reel topic: "{topic}"
Hook framework: "{hook_framework or 'not specified'}"
Script preview: {scene_texts}
{test_format_tip}

Rules:
- Line 1 (THE HOOK): Must be under 90 characters total (including emoji). Instagram cuts off before 'more'. Make it impossible not to tap 'more'.
- Line 2 (THE CORE INSIGHT): 1-2 punchy sentences in conversational Hinglish expanding on the reel's psychological insight.
- Line 3 (THE ENGAGEMENT TRIGGER): An authentic, provocative question that makes people want to write their own opinion or personal story in the comments. End with 👇.
  (Do NOT use rigid 'Comment 1 or 2' voting — ask for genuine thoughts, agreement/disagreement, or experiences).
- Line 4 (VALUE/SAVE CTA): A natural reason to bookmark or share this reel (e.g., "Is insight ko save kar lo — real life mein kaam aayega 📌").
- Line 5 (Exact handle CTA): "Follow {handle} for daily relationship psychology secrets 🔑"
- Style: Fluent Hinglish (mix of Hindi & English) — natural Gen-Z / millennial Indian Instagram style.
- Make it sound like a real person sharing an eye-opening observation, NOT an automated template.

Return ONLY the 5-line caption text, no quotes, no markdown fences.
"""
    raw = _llm_prompt(prompt).strip()

    # Guard: ensure first line fits before Instagram's 'more' cutoff
    lines = raw.split("\n")
    if lines and len(lines[0]) > 120:
        lines[0] = lines[0][:117] + "..."
        raw = "\n".join(lines)

    return raw


def _generate_ai_hashtags(topic, script_data):
    """Use LLM to generate a mix of niche, medium, and broad hashtags specific to the topic."""
    prompt = f"""
Generate Instagram hashtags for a Reel about: "{topic}"
The content is in Hindi/Hinglish targeting young Indian men (18-30) interested in psychology, attraction, and relationships.

Rules:
- Return EXACTLY 15 hashtags — no more, no less. Research shows 12-15 targeted tags outperform 28-30 for reach on small accounts.
- Mix: 5 niche hashtags (10k-100k posts), 5 medium (100k-1M posts), 5 broad (1M-10M posts)
- Include 2-3 Hindi hashtags only (e.g., #लड़कियां, #दिलकीबात, #रिश्ते, #आकर्षण, #मनोविज्ञान)
- ALL hashtags must be directly relevant to this specific topic — no generic lifestyle tags
- DO NOT use: #Viral, #ExplorePage, #ForYou, #Trending, #FYP — useless for small accounts
- DO NOT use: #Reels, #Instagram, #Love — too broad
- DO NOT use: #MensJournal, #MensHealth — these are magazine brands, completely irrelevant
- DO NOT use slang or offensive tags like #लड़कीपटाओ — Instagram may suppress reach for these
- DO NOT use celebrity or brand hashtags unrelated to the content
- Each hashtag must start with #
- Format: space-separated on a single line

Good examples of quality hashtags for this niche:
#GirlPsychology #AttractionPsychology #BodyLanguageTips #DatingAdviceIndia #MaleSelfImprovement
#RelationshipDecoding #HumanBehavior #ConfidenceTips #IndianDatingAdvice
#लड़कियां #आकर्षण #मनोविज्ञान

Return ONLY the hashtags, nothing else.
"""
    raw = _llm_prompt(prompt).strip()
    # Parse hashtags from the response
    hashtags = [tag.strip() for tag in raw.replace("\n", " ").split() if tag.strip().startswith("#")]
    
    # Block known irrelevant or spammy hashtags regardless of LLM output
    _BLOCKED_HASHTAGS = {
        "#mensjounal", "#mensjournal", "#mensheath", "#menshealth",
        "#लड़कीपटाओ", "#ladkipatao", "#viral", "#explorepage",
        "#foryou", "#fyp", "#trending", "#reels", "#instagram",
        "#love", "#instagood", "#photooftheday", "#fashion",
    }
    hashtags = [tag for tag in hashtags if tag.lower() not in _BLOCKED_HASHTAGS]

    # Ensure we have a reasonable number
    if len(hashtags) < 5:
        hashtags = [
            "#GirlPsychology", "#AttractionPsychology", "#BodyLanguageTips",
            "#DatingAdviceIndia", "#MaleSelfImprovement", "#RelationshipDecoding",
            "#HumanBehavior", "#ConfidenceTips", "#IndianDatingAdvice",
            "#PsychologyFacts", "#MentalStrength",
            "#लड़कियां", "#आकर्षण", "#मनोविज्ञान", "#दिलकीबात",
        ]

    return hashtags[:15]  # Cap at 15 hashtags — quality over quantity


def _generate_first_comment(topic, script_data):
    """Generate a debate-triggering first comment to seed engagement immediately after posting.

    Switched from 1/2 numbered voting to CONTROVERSY-style comments.
    Analytics show 0 organic comments — numbered voting gets single-character responses
    which Instagram weights as low-quality engagement.
    Controversy prompts get PARAGRAPH responses = high-quality engagement signals.
    """
    title = script_data.get("title", topic)
    prompt = f"""
You are writing the FIRST comment that the account owner will post on their own reel immediately after uploading.
This comment must spark a DEBATE — not just a yes/no vote. It must make people DEFEND their opinion in the replies.

Reel title: "{title}"
Reel topic: "{topic}"

Rules:
- Write a SHORT, polarizing statement or question that splits the audience 50/50 (max 15 words)
- It should provoke strong reactions from BOTH sides — some will agree angrily, some will disagree angrily
- PROVEN PATTERNS for this niche:
  * Friendzone topics: "Friendzone exist hi nahi karta — ladke khud apne aap ko friendzone karte hain" → debate starter
  * Mirror topics: "Agar wo copy nahi karti toh bhai tu friend zone mein hai, seedha baat" → controversy
  * General: Bold claim that half the audience agrees with and half strongly disagrees with
- Must be in Hinglish (mix of Hindi + English) — Gen-Z Indian style
- End with "sach ya jhooth? 👇" or "agree? 👇" or "galat hu toh batao 👇" to invite replies
- Do NOT use numbered voting format (1=haan, 2=nahi) — that gets low-quality single-character comments
- We want PARAGRAPHS from people arguing — that's what the algorithm reads as high engagement

Return ONLY the comment text, nothing else.
"""
    try:
        result = _llm_prompt(prompt).strip()
        # Validate: must be non-empty and contain real words (not just emoji/punctuation)
        import re as _re
        real_words = _re.sub(r'[^\w\s]', '', result, flags=_re.UNICODE).strip()
        if not result or len(real_words) < 10:
            raise ValueError(f"LLM returned too-short comment: '{result}'")
        # Truncate to Instagram-safe length (hard limit ~2200 chars, keep well under)
        if len(result) > 500:
            result = result[:500].rsplit(" ", 1)[0]
        return result
    except Exception:
        fallbacks = [
            "Friendzone exist hi nahi karta — ye sirf ek excuse hai. Sach ya jhooth? 👇",
            "Agar wo tumhe copy karti hai toh 100% interested hai. Disagree karo toh reason batao 👇",
            "Ye baat koi nahi bolta but ye sach hai — agree karte ho? 👇",
            "Mixed signals matlab wo confused hai ya tum? Apna jawab do 👇",
        ]
        return random.choice(fallbacks)



def _generate_series_title(topic, script_data):
    """Generate a series-continuation title (e.g. Part 2, Part 3) for viral planning.
    
    Extracts the current Part number if present (defaults to Part 1) and generates
    the next sequential part title (e.g., Part 3 after Part 2) to continue high-performing topics.
    """
    import re
    title = script_data.get("title", topic)
    
    # Detect if we are already in a series and get the current part number
    current_part = 1
    match = re.search(r'part\s*(\d+)', (topic + " " + title).lower())
    if match:
        try:
            current_part = int(match.group(1))
        except ValueError:
            pass
            
    next_part = current_part + 1
    prefix = f"Part {next_part}"
    
    prompt = f"""
Given this viral reel title: "{title}" (topic: {topic}), which is Part {current_part} of a series,
generate a single short '{prefix}' title that:
- Continues the story/revelation naturally
- Uses the same emotional hook style
- Starts with '{prefix}:' prefix
- Is max 8 words
- Stays in the same niche (relationship psychology, attraction, body language)

Example: If Part 1 was 'Friendzone Test: Spot It Or Stay Stuck?'
Part 2 could be: 'Part 2: Escape The Friendzone Using This'
If Part 2 was 'Part 2: Escape The Friendzone Using This'
Part 3 could be: 'Part 3: The Secret Phrase That Reverses It'

Return ONLY the {prefix} title, nothing else.
"""
    try:
        result = _llm_prompt(prompt).strip()
        # Ensure it starts with the correct prefix
        if not result.lower().startswith(prefix.lower()):
            result = f"{prefix}: {result}"
        return result[:60]  # cap length
    except Exception:
        return f"{prefix}: {title[:40]}"


def _generate_story_poll(topic, script_data):
    """Generate a story poll question to drive traffic from Stories back to the reel.
    
    After posting a reel, posting a Story with a poll that links back to the reel
    is one of the most effective ways to amplify reach. The poll forces engagement
    and Instagram shows it to more people.
    """
    title = script_data.get("title", topic)
    try:
        prompt = f"""
Create a simple 2-option Instagram Story poll question for this reel: "{title}" (topic: {topic})

Rules:
- Question: max 20 words, in Hinglish, provocative
- Option 1: short (max 3 words), the 'yes/agree' answer
- Option 2: short (max 3 words), the 'no/disagree' answer  
- Make the poll force a strong opinion — no neutral answers

Return in this exact format:
QUESTION: [question text]
OPTION_1: [yes option]
OPTION_2: [no option]
"""
        raw = _llm_prompt(prompt).strip()
        lines = {}
        for line in raw.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                lines[key.strip().upper()] = val.strip()
        return {
            "question": lines.get("QUESTION", f"Ye {topic} relatable hai?"),
            "option_1": lines.get("OPTION_1", "Haan 🔥"),
            "option_2": lines.get("OPTION_2", "Nahi 🤔"),
        }
    except Exception:
        return {
            "question": f"Ye {topic[:30]} relatable hai tumhare liye?",
            "option_1": "Haan 🔥",
            "option_2": "Nahi 🤔",
        }


def generate_seo_metadata(topic, script_data):
    """Generates engagement-optimized SEO metadata with AI-written captions and smart hashtags."""
    title = script_data.get('title', f"{topic}")

    # AI-generated contextual caption
    try:
        caption_body = _generate_ai_caption(topic, script_data)
    except Exception as e:
        print(f"AI caption generation failed, using fallback: {e}")
        handle = _get_insta_handle()
        caption_body = f"🔥 {topic}\n\nSach hai ya alag soch hai? Apni ray comments mein share karo 👇\nIs insight ko save zaroor kar lena 📌\nFollow {handle} for daily psychology secrets 🔑"

    # AI-generated topic-specific hashtags
    try:
        hashtags = _generate_ai_hashtags(topic, script_data)
    except Exception as e:
        print(f"AI hashtag generation failed, using fallback: {e}")
        hashtags = [
            "#GirlPsychology", "#AttractionPsychology", "#BodyLanguageTips",
            "#DatingAdviceIndia", "#MaleSelfImprovement", "#RelationshipDecoding",
            "#HumanBehavior", "#ConfidenceTips", "#IndianDatingAdvice",
            "#PsychologyFacts", "#MentalStrength",
            "#लड़कियां", "#आकर्षण", "#मनोविज्ञान", "#दिलकीबात",
        ]

    # Generate first-comment seed for immediate social proof after posting
    try:
        first_comment = _generate_first_comment(topic, script_data)
        print(f"[SEO] First comment seeded: {first_comment[:60]}...")
    except Exception as e:
        print(f"[SEO] First comment generation failed: {e}")
        first_comment = "Kya tumhare saath bhi aisa hua hai? 1 = haan, 2 = nahi 👇"

    # Generate Part 2 title for series continuation tracking
    try:
        series_next_title = _generate_series_title(topic, script_data)
        print(f"[SEO] Series Part 2 queued: {series_next_title}")
    except Exception as e:
        print(f"[SEO] Series title generation failed: {e}")
        series_next_title = ""

    # Generate Story poll for cross-promotion
    try:
        story_poll = _generate_story_poll(topic, script_data)
        print(f"[SEO] Story poll: {story_poll.get('question', '')}")
    except Exception as e:
        print(f"[SEO] Story poll generation failed: {e}")
        story_poll = {"question": f"Ye {topic[:30]} relatable hai?", "option_1": "Haan 🔥", "option_2": "Nahi 🤔"}

    # Build the full description: caption + enough line breaks to push hashtags below the fold
    # Using 5 dots ensures hashtags stay hidden behind the "more" button
    description = f"{caption_body}\n.\n.\n.\n.\n.\n{' '.join(hashtags)}"

    tags = [topic, "Psychology", "Attraction", "Body Language", "Reels", "India"]
    
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "first_comment": first_comment,         # Post as account's first comment after upload
        "series_next_title": series_next_title,  # Suggested Part 2 title for series continuation
        "story_poll": story_poll,                # Post as Story poll to drive reel traffic
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
