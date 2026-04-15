import json

def generate_seo_metadata(topic, script_data):
    """Generates SEO title, description, and tags."""
    title = script_data.get('title', f"{topic} - Short Video")
    description = f"Video about {topic}.\n\n"
    description += "Like and share if you found this interesting!\n\n"
    description += "#" + topic.replace(" ", "") + " #AI #Shorts"
    
    tags = [topic, "AI Generated", "Documentary", "Education"]
    
    return {
        "title": title,
        "description": description,
        "tags": tags
    }

def save_metadata(metadata, output_path):
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=4)
