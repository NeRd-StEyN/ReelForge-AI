import edge_tts
import asyncio
import os


def _ticks_to_seconds(ticks):
    """Convert 100ns ticks used by Edge events into seconds."""
    return float(ticks or 0) / 10_000_000.0

async def generate_voiceover(text, output_path, voice="hi-IN-SwaraNeural"):
    """Generates a high-energy, fast-paced, high-retention voiceover file using edge-tts."""
    # Neutral rate sounds more natural with longer paragraph narration.
    communicate = edge_tts.Communicate(text, voice, rate="+18%")
    await communicate.save(output_path)
    return output_path


async def generate_voiceover_with_timestamps(text, output_path, voice="hi-IN-SwaraNeural"):
    """Generate voiceover and return word timing events for subtitle sync."""
    communicate = edge_tts.Communicate(text, voice, rate="+18%")
    word_timeline = []

    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type")
            if chunk_type == "audio":
                audio_file.write(chunk.get("data", b""))
            elif chunk_type == "WordBoundary":
                word_text = str(chunk.get("text", "")).strip()
                if not word_text:
                    continue
                start = _ticks_to_seconds(chunk.get("offset"))
                duration = _ticks_to_seconds(chunk.get("duration"))
                word_timeline.append(
                    {
                        "word": word_text,
                        "start": start,
                        "end": start + max(0.05, duration),
                    }
                )

    return output_path, word_timeline

def run_generate_voiceover(text, output_path, voice="hi-IN-SwaraNeural"):
    """Wrapper to run the async voiceover generation."""
    asyncio.run(generate_voiceover(text, output_path, voice))
    return output_path


def run_generate_voiceover_with_timestamps(text, output_path, voice="hi-IN-SwaraNeural"):
    """Wrapper to generate voiceover plus word-level timestamps."""
    return asyncio.run(generate_voiceover_with_timestamps(text, output_path, voice))
