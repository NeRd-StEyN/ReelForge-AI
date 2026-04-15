import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

def generate_script(topic, analytics_data=None):
    """Generates a highly viral video script based on the topic and past analytics."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
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
    You are a viral TikTok & YouTube Shorts strategist.
    {instructions}
    
    Your directive is to create a highly engaging, concise, fast-paced script for the topic: "{topic}".
    The hook (first 3 seconds) must be absolutely irresistible.
    The script should be exactly 45-60 seconds when read aloud fast.
    
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
    
    response = model.generate_content(prompt)
    return response.text
