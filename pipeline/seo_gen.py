import json
import random

def generate_seo_metadata(topic, script_data):
    """Generates engagement-optimized SEO metadata for bold girl/dating content."""
    title = script_data.get('title', f"{topic} | Bold Facts")

    hook_line = f"🔥 {topic}".strip()

    # Randomized CTAs to keep captions fresh and drive different engagement signals.
    cta_pool = [
        "Comment 🔥 if you agree 👇",
        "Tag a bro who needs this 😏",
        "Double tap if this blew your mind 💥",
        "Share this with your bestie 📩",
        "Save this for later — you'll need it 📌",
        "Comment 'YES' if you relate 🙌",
        "DM this to someone who needs to hear this 💬",
        "Type '💯' if this is facts 👇",
    ]
    selected_ctas = random.sample(cta_pool, min(3, len(cta_pool)))

    body_lines = selected_ctas + [
        "",
        "Follow for more bold facts about girls 💋",
        "Part 2? Comment 'MORE' 👇🔥",
    ]

    hashtags = [
        "#GirlFacts",
        "#DatingTips",
        "#AttractionPsychology",
        "#RelationshipSecrets",
        "#BoldFacts",
        "#WhatGirlsWant",
        "#SeductionTips",
        "#Reels",
        "#Viral",
        "#ExplorePage",
        "#LoveTips",
        "#GirlPsychology",
        "#ForYou",
        "#Trending",
    ]

    description = "\n".join([hook_line, ""] + body_lines + ["", " ".join(hashtags)])

    tags = [topic, "Girl Facts", "Dating", "Attraction", "Bold", "Reels"]
    
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=4)
