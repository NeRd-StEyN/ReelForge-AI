import json
import random
from pipeline.script_gen import _openrouter_prompt


def _generate_ai_caption(topic, script_data):
    """Use LLM to generate a short, engaging, topic-specific caption with a debate-starter CTA."""
    title = script_data.get("title", topic)
    scene_texts = " | ".join(
        s.get("text", "")[:60] for s in script_data.get("scenes", [])
    )

    prompt = f"""
You are an Instagram caption specialist for viral Reels. 
Write a SHORT, punchy caption for this reel.

Reel title: "{title}"
Reel topic: "{topic}"
Script preview: {scene_texts}

Rules:
- First line: 1 provocative hook sentence (under 15 words) that makes people STOP and read. Use an emoji at the start.
- Second line: A controversial question that forces people to comment and debate (under 12 words). End with 👇
- Third line: ONE specific CTA tied to the topic (e.g., "Save this for your next date 📌" or "Tag someone who needs to hear this 💬")
- Fourth line: "Follow @itsun.known6969 for daily mind-blowing facts 🧠"
- Keep it under 200 characters total (before hashtags)
- Write in Hinglish (mix of Hindi and English) — natural Gen-Z Indian Instagram style
- Do NOT use generic phrases like "Tag a bro", "Double tap", "Share with bestie"
- Make it feel like a REAL person wrote it, not a bot

Return ONLY the caption text, no quotes, no markdown.
"""
    return _openrouter_prompt(prompt).strip()


def _generate_ai_hashtags(topic, script_data):
    """Use LLM to generate a mix of niche, medium, and broad hashtags specific to the topic."""
    prompt = f"""
Generate Instagram hashtags for a Reel about: "{topic}"
The content is in Hindi/Hinglish targeting young Indian men (18-30) interested in psychology, attraction, and relationships.

Rules:
- Return EXACTLY 18 hashtags
- Mix: 6 niche hashtags (10k-100k posts), 6 medium (100k-1M posts), 6 broad (1M-10M posts)
- Include 4-5 Hindi hashtags (e.g., #लड़कियां, #दिलकीबात, #रिश्ते, #आकर्षण)
- Include topic-specific hashtags (not generic ones)
- DO NOT use: #Viral, #ExplorePage, #ForYou, #Trending, #FYP — these are useless for small accounts
- DO NOT use: #Reels — too broad
- Each hashtag must start with #
- Format: space-separated on a single line

Good examples of effective hashtags:
#GirlPsychology #AttractionScience #BodyLanguageTips #DatingIndia #MaleSelfImprovement
#RelationshipAdvice #HumanBehavior #ConfidenceTips #IndianReels #MentalHealth
#लड़कियां #आकर्षण #दिलकीबात #रिश्ते

Return ONLY the hashtags, nothing else.
"""
    raw = _openrouter_prompt(prompt).strip()
    # Parse hashtags from the response
    hashtags = [tag.strip() for tag in raw.replace("\n", " ").split() if tag.strip().startswith("#")]
    
    # Ensure we have a reasonable number
    if len(hashtags) < 5:
        # Fallback hashtags if LLM fails
        hashtags = [
            "#GirlPsychology", "#AttractionFacts", "#BodyLanguage",
            "#DatingTips", "#RelationshipAdvice", "#MaleSelfImprovement",
            "#HumanBehavior", "#ConfidenceBoost", "#IndianReels",
            "#MindBlown", "#PsychologyFacts", "#AttractHer",
            "#लड़कियां", "#आकर्षण", "#दिलकीबात",
            "#SelfImprovement", "#MentalStrength", "#DatingIndia",
        ]
    
    return hashtags[:20]  # Cap at 20 hashtags max


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
            "#GirlPsychology", "#AttractionFacts", "#BodyLanguage",
            "#DatingTips", "#RelationshipAdvice", "#MaleSelfImprovement",
            "#HumanBehavior", "#ConfidenceBoost", "#IndianReels",
            "#MindBlown", "#PsychologyFacts", "#AttractHer",
            "#लड़कियां", "#आकर्षण", "#दिलकीबात",
            "#SelfImprovement", "#MentalStrength", "#DatingIndia",
        ]

    # Build the full description: caption + line break + hashtags below the fold
    description = f"{caption_body}\n.\n.\n.\n{' '.join(hashtags)}"

    tags = [topic, "Psychology", "Attraction", "Body Language", "Reels", "India"]
    
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
