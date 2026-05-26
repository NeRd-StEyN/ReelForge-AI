import json
import random

def generate_seo_metadata(topic, script_data, content_type="horror_reel"):
    """Generates engagement-optimized SEO metadata based on content type."""
    title = script_data.get('title', f"{topic}")

    if content_type == "girl_facts":
        # Bold girl facts SEO
        hook_line = f"🔥 {topic}".strip()

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

        tags = [topic, "Girl Facts", "Dating", "Attraction", "Bold", "Reels"]
    else:
        # Horror content SEO (horror_reel and horror_story)
        hook_line = f"😱 {topic}".strip()

        cta_pool = [
            "Comment 😱 if this gave you chills 👇",
            "Tag someone who gets scared easily 💀",
            "Double tap if you got goosebumps 😨",
            "Share this horror story with friends 📩",
            "Save this for a scary night — you'll need it 📌",
            "Comment 'NEXT' for part 2 👻",
            "DM this to someone who loves horror 💬",
            "Type '💀' if this creeped you out 👇",
            "Comment if you'd survive this story 🪦",
            "Watch till end for the twist 😈",
        ]
        selected_ctas = random.sample(cta_pool, min(3, len(cta_pool)))

        body_lines = selected_ctas + [
            "",
            "Follow for daily horror stories 👻🖤",
            "Part 2? Comment 'MORE' 👇😱",
        ]

        hashtags = [
            "#HorrorStory",
            "#GhostGirl",
            "#CreepyStories",
            "#HorrorReels",
            "#Paranormal",
            "#ScaryStories",
            "#HauntedPlaces",
            "#GhostEncounter",
            "#DarkStories",
            "#HorrorFacts",
            "#Reels",
            "#Viral",
            "#ExplorePage",
            "#CreepyFacts",
            "#ForYou",
            "#Trending",
            "#MysteryStories",
            "#HorrorHindi",
        ]

        tags = [topic, "Horror Story", "Ghost Girl", "Paranormal", "Scary", "Reels"]

    description = "\n".join([hook_line, ""] + body_lines + ["", " ".join(hashtags)])

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=4)
