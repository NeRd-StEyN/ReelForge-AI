import json

def generate_seo_metadata(topic, script_data):
    """Generates SEO title, description, and tags."""
    title = script_data.get('title', f"{topic} | Horror Reel")

    hook_line = f"You will not expect this: {topic}".strip()
    body_lines = [
        "A fast horror mystery reel built to keep you watching till the final twist.",
        "Watch till the end and tell me your theory in comments.",
    ]

    hashtags = [
        "#HorrorReel",
        "#ScaryFacts",
        "#Mystery",
        "#Reels",
        "#Shorts",
        "#" + topic.replace(" ", ""),
    ]

    description = "\n\n".join([hook_line] + body_lines + [" ".join(hashtags)])

    tags = [topic, "Horror", "Mystery", "AI Generated", "Reels"]
    
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=4)
