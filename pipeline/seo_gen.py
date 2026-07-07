import json
import random
from pipeline.script_gen import _llm_prompt


def _generate_ai_caption(topic, script_data):
    """Use LLM to generate a short, engaging, topic-specific caption with a debate-starter CTA."""
    title = script_data.get("title", topic)
    hook_framework = script_data.get("hook_framework", "")
    scene_texts = " | ".join(
        s.get("text", "")[:60] for s in script_data.get("scenes", [])
    )

    # Extra instruction for test_format framework (our highest performer)
    test_format_tip = ""
    if hook_framework in ("test_format", "kabhii_nahi"):
        test_format_tip = """
SPECIAL RULE for this hook framework: The first line MUST use either:
  (a) 'Test' framing: 'Friendzone Test: [short consequence]' style, OR
  (b) Incomplete sentence with '...' that cuts off: 'लड़कियां कभी नहीं...'
This is our PROVEN highest-performing opener style on this account."""

    prompt = f"""
You are an Instagram caption specialist for viral Reels.
Write a SHORT, punchy caption for this reel about relationship psychology.

Reel title: "{title}"
Reel topic: "{topic}"
Hook framework: "{hook_framework or 'not specified'}"
Script preview: {scene_texts}
{test_format_tip}

Rules:
- CRITICAL: The VERY FIRST LINE must be under 90 characters total (including spaces and emoji).
  Instagram cuts off captions at ~125 chars before "more" — the hook MUST land fully in the first line.
  Example of a good first line (under 90 chars): "🔥 90% ladke ek cheez nahi karte jo attract karti hai"
- First line: 1 provocative hook sentence that makes people STOP and read. Use an emoji at the start.
- Second line: A MANDATORY comment-bait question with a NUMBERED reply prompt.
  This forces the algorithm to prioritize the reel based on comment volume. Examples:
    "कितनो के साथ ये हो चुका है? Comment 1 अगर हाँ, 2 अगर नहीं 👇"
    "आपका kya answer hai? 1 = हाँ, 2 = नहीं, 3 = नहीं पता 👇"
    The question MUST end with a numbered option list + 👇 emoji.
- Third line: A SPECIFIC, urgent SAVE-focused CTA. Examples:
    "Save this — agli baar kaam aayega jab wo ignore kare 📌"
    "Save this so you never misread her signals again 📌"
    "Screenshot karo, apne aap ko remind karo 📌"
  Make the reason for saving feel PERSONAL and SPECIFIC to this topic, not generic.
- Fourth line: A like-bait line that triggers emotional resonance WITHOUT literally saying 'like karo'.
  Examples:
    "Like karo agar ye tumhare saath bhi hua hai 💯"
    "Agar tumne ye feel kiya hai, double tap karo ❤️"
    "92% log ye miss karte hain — tum nahi karte agar ye dekh raha hai 🔥"
- Fifth line (exact, do not change): "Follow @itsun.known6969 for daily relationship psychology secrets 🔑"
- Write in Hinglish (mix of Hindi and English) — natural Gen-Z Indian Instagram style
- Do NOT use generic phrases like "Tag a bro", "Double tap", "Share with bestie"
- Make it feel like a REAL person wrote it, not a bot
- If the hook framework suggests curiosity or controversy, keep the first line sharper and more specific.

Return ONLY the caption text, no quotes, no markdown.
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
        return _llm_prompt(prompt).strip()
    except Exception:
        fallbacks = [
            "Friendzone exist hi nahi karta — ye sirf ek excuse hai. Sach ya jhooth? 👇",
            "Agar wo tumhe copy karti hai toh 100% interested hai. Disagree karo toh reason batao 👇",
            "Ye baat koi nahi bolta but ye sach hai — agree karte ho? 👇",
        ]
        return random.choice(fallbacks)



def _generate_series_title(topic, script_data):
    """Generate a series-continuation title for Part 2 planning.
    
    When a reel goes viral (1K+ views), the next step is always a Part 2.
    This function generates what 'Part 2' would be called so it can be
    logged and auto-suggested in future topic generation cycles.
    """
    title = script_data.get("title", topic)
    hook_framework = script_data.get("hook_framework", "")
    prompt = f"""
Given this viral reel title: "{title}" (topic: {topic}),
generate a single short 'Part 2' title that:
- Continues the story/revelation naturally
- Uses the same emotional hook style
- Starts with 'Part 2:' prefix
- Is max 8 words
- Stays in the same niche (relationship psychology, attraction, body language)

Example: If Part 1 was 'Friendzone Test: Spot It Or Stay Stuck?'
Part 2 could be: 'Part 2: Escape The Friendzone Using This'

Return ONLY the Part 2 title, nothing else.
"""
    try:
        result = _llm_prompt(prompt).strip()
        # Ensure it starts with Part 2:
        if not result.lower().startswith("part 2"):
            result = f"Part 2: {result}"
        return result[:60]  # cap length
    except Exception:
        return f"Part 2: {title[:40]}"


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
        caption_body = f"🔥 {topic}\n\nSach hai ya nahi? Comment 1 = haan, 2 = nahi 👇\nFollow @itsun.known6969 for more 🧠"

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
