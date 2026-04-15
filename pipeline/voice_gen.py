import edge_tts
import asyncio
import os

async def generate_voiceover(text, output_path, voice="en-US-ChristopherNeural"):
    """Generates a fast-paced, high-retention voiceover file using edge-tts."""
    # Rate +10% increases engagement for short-form content
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)
    return output_path

def run_generate_voiceover(text, output_path, voice="en-US-ChristopherNeural"):
    """Wrapper to run the async voiceover generation."""
    asyncio.run(generate_voiceover(text, output_path, voice))
    return output_path
