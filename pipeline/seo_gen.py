import json
import random
from pipeline.script_gen import _llm_prompt


def _generate_ai_caption(topic, script_data):
    """Use LLM to generate a short, engaging, topic-specific caption with a debate-starter CTA."""
    title = script_data.get("title", topic)
    scene_texts = " | ".join(
        s.get("text", "")[:60] for s in script_data.get("scenes", [])
    )

    prompt = f"""
You are an Instagram caption specialist for viral Reels.
Write a SHORT, punchy caption for this reel about relationship psychology.

Reel title: "{title}"
Reel topic: "{topic}"
Script preview: {scene_texts}

Rules:
- CRITICAL: The VERY FIRST LINE must be under 90 characters total (including spaces and emoji).
  Instagram cuts off captions at ~125 chars before "more" — the hook MUST land fully in the first line.
  Example of a good first line (under 90 chars): "🔥 90% ladke ek cheez nahi karte jo attract karti hai"
- First line: 1 provocative hook sentence that makes people STOP and read. Use an emoji at the start.
- Second line: A MANDATORY comment-bait question that sparks debate and forces viewers to reply.
  This is the MOST IMPORTANT line for algorithm reach. Examples:
    "Kya tumhare saath bhi aisa hua hai? Drop a 🔥 neeche 👇"
    "Agree ho? Ya nahi? Comment karo 👇"
    "Kitno ke saath ye ho chuka hai? 👇"
  The question MUST end with an emoji + 👇 to drive comments.
- Third line: A SPECIFIC, urgent SAVE-focused CTA. Examples:
    "Save this — agli baar kaam aayega jab wo ignore kare 📌"
    "Save this so you never misread her signals again 📌"
    "Screenshot karo, apne aap ko remind karo 📌"
  Make the reason for saving feel PERSONAL and SPECIFIC to this topic, not generic.
- Fourth line (exact, do not change): "Follow @itsun.known6969 for daily relationship psychology secrets 🔑"
- Write in Hinglish (mix of Hindi and English) — natural Gen-Z Indian Instagram style
- Do NOT use generic phrases like "Tag a bro", "Double tap", "Share with bestie"
- Make it feel like a REAL person wrote it, not a bot

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
        # Fallback hashtags if LLM fails — 15 quality, niche-specific tags
        hashtags = [
            "#GirlPsychology", "#AttractionPsychology", "#BodyLanguageTips",
            "#DatingAdviceIndia", "#MaleSelfImprovement", "#RelationshipDecoding",
            "#HumanBehavior", "#ConfidenceTips", "#IndianDatingAdvice",
            "#PsychologyFacts", "#MentalStrength",
            "#लड़कियां", "#आकर्षण", "#मनोविज्ञान", "#दिलकीबात",
        ]

    return hashtags[:15]  # Cap at 15 hashtags — quality over quantity


def _generate_first_comment(topic, script_data):
    """Generate a punchy self-comment to seed engagement immediately after posting.
    
    The FIRST comment on a reel creates social proof and invites others to reply.
    A reel with 0 comments feels dead — a seeded question makes it feel alive.
    Post this as the account's own first comment right after uploading.
    """
    title = script_data.get("title", topic)
    prompt = f"""
You are writing the FIRST comment that the account owner will post on their own reel immediately after uploading.
This comment is the most important comment — it sets the tone and invites others to engage.

Reel title: "{title}"
Reel topic: "{topic}"

Rules:
- Write a SHORT, punchy question that makes people WANT to reply (max 15 words)
- Must be in Hinglish (mix of Hindi + English) — Gen-Z Indian style
- End with an emoji that signals a reply is expected (e.g., 👇, 🔥, 💬, ❤️)
- Make it personal/relatable — like the account owner is genuinely curious about viewers' opinions
- Do NOT just repeat the caption — ask something specific about their personal experience
- Examples:
    "Kitno ke saath aisa hua hai? Batao 👇"
    "Agree? Ya tumhara experience alag tha? 🔥"
    "Maine yahi feel kiya tha — tumhara kya? 💬"

Return ONLY the comment text, nothing else.
"""
    try:
        return _llm_prompt(prompt).strip()
    except Exception:
        # Fallback comment options
        fallbacks = [
            "Kya tumhare saath bhi aisa hua hai? Batao 👇",
            "Agree ho ya nahi? Comment karo 🔥",
            "Ye experience kitno ka hai? 💬",
        ]
        return random.choice(fallbacks)


def generate_seo_metadata(topic, script_data):
    """Generates engagement-optimized SEO metadata with AI-written captions and smart hashtags."""
    title = script_data.get('title', f"{topic}")

    # AI-generated contextual caption
    try:
        caption_body = _generate_ai_caption(topic, script_data)
    except Exception as e:
        print(f"AI caption generation failed, using fallback: {e}")
        caption_body = f"🔥 {topic}\n\nSach hai ya nahi? Comment karo 👇\nFollow @itsun.known6969 for more 🧠"

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
        first_comment = "Kya tumhare saath bhi aisa hua hai? Batao 👇"

    # Build the full description: caption + enough line breaks to push hashtags below the fold
    # Using 5 dots ensures hashtags stay hidden behind the "more" button
    description = f"{caption_body}\n.\n.\n.\n.\n.\n{' '.join(hashtags)}"

    tags = [topic, "Psychology", "Attraction", "Body Language", "Reels", "India"]
    
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "first_comment": first_comment,  # Post this as the account's first comment after upload
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
