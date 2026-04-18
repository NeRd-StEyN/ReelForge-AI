import edge_tts
import asyncio
import os

async def generate_voiceover(text, output_path, voice="en-US-GuyNeural"):
    """Generates a high-energy, fast-paced, high-retention voiceover file using edge-tts."""
    # Slightly slower than before to improve flow on longer 55-60s scripts.
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    await communicate.save(output_path)
    return output_path

def run_generate_voiceover(text, output_path, voice="en-US-GuyNeural"):
    """Wrapper to run the async voiceover generation."""
    asyncio.run(generate_voiceover(text, output_path, voice))
    return output_path
