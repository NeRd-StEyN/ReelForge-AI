import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_openrouter_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables. Please add it to your .env file.")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

def generate_script(topic, analytics_data=None):
    """Generates a highly viral video script based on the topic and past analytics."""
    client = get_openrouter_client()
    
    instructions = ""
    if analytics_data and analytics_data != "No previous reels found. Start fresh!" and "Error" not in analytics_data:
        instructions = f"""
    CRITICAL ANALYTICS FEEDBACK:
    Here is the performance data for my recent videos: 
    {analytics_data}
    
    Look at which topics or styles got the HIGHEST views and likes. 
    Use that knowledge to brainstorm a hook and topic that expands on what the audience already loves!
    """

    prompt = f"""
    You are a viral TikTok & YouTube Shorts strategist specializing in HORROR and PARANORMAL reels.
    {instructions}
    
    Your directive is to create a highly engaging, terrifying, suspenseful, fast-paced script for the topic: "{topic}".
    The hook (first 3 seconds) must be absolutely paralyzing and terrifying to stop the viewer from scrolling. Use dark psychology to hook them immediately.
    The total script when read aloud fast MUST strictly be 40 to 45 seconds long. NEVER exceed 50 seconds in length! Focus on mysterious, scary, unsettling narratives!
    
    Format the output as strict JSON with the following structure:
    {{
        "title": "A catchy viral title",
        "scenes": [
            {{
                "id": 1,
                "text": "The spoken words for this scene",
                "visual_keyword": "Highly specific visual term to search stock footage for (e.g. 'mysterious dark galaxy space explosion')"
            }}
        ]
    }}
    Provide only the valid JSON, no markdown formatting blocks.
    """
    
    response = client.chat.completions.create(
        model="openai/gpt-4o", # Upgraded to best-in-class GPT-4o for ultimate script creativity
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    # OpenRouter returns markdown JSON sometimes, so we strip out common markdown formatting
    content = response.choices[0].message.content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    return content.strip()

def generate_topic_from_domain(domain, analytics_data=None, feedback_summary=""):
    """Generate the next reel topic inside one domain using recent performance feedback."""
    client = get_openrouter_client()

    analytics_text = analytics_data if analytics_data else "No analytics yet"

    prompt = f"""
You are a short-form content strategist.

Domain to stay inside: "{domain}"
Recent post analytics data: {analytics_text}
Historical feedback summary: {feedback_summary}

Task:
Propose exactly ONE topic idea for the next Instagram Reel that stays inside the domain,
iterates on what performed best, and has high hook potential.

Return only a single plain-text topic line, max 12 words, no quotes, no numbering.
"""

    response = client.chat.completions.create(
        model="openai/gpt-4o", 
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip().splitlines()[0].strip()
