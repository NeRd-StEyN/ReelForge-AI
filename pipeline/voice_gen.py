import edge_tts
import asyncio
import os


def _ticks_to_seconds(ticks):
    """Convert 100ns ticks used by Edge events into seconds."""
    return float(ticks or 0) / 10_000_000.0

async def generate_voiceover(text, output_path, voice="hi-IN-SwaraNeural"):
    """Generates a high-energy, fast-paced, high-retention voiceover file using edge-tts."""
    # Neutral rate sounds more natural with longer paragraph narration.
    communicate = edge_tts.Communicate(text, voice, rate="+12%")
    await communicate.save(output_path)
    return output_path


async def generate_voiceover_with_timestamps(text, output_path, voice="hi-IN-SwaraNeural"):
    """Generate voiceover and return word timing events for subtitle sync.

    Handles both edge-tts versions:
    - Old versions emit WordBoundary events (direct per-word timing).
    - v7+ only emits SentenceBoundary events, so we split each sentence's
      time range evenly across its words to synthesize per-word timing.
    """
    communicate = edge_tts.Communicate(text, voice, rate="+12%")
    word_timeline = []
    sentence_events = []

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
            elif chunk_type == "SentenceBoundary":
                sentence_events.append(chunk)

    # If WordBoundary events were found, use them directly (older edge-tts).
    if word_timeline:
        return output_path, word_timeline

    # edge-tts v7+: only SentenceBoundary available.
    # Split each sentence's duration evenly across its words.
    if sentence_events:
        for evt in sentence_events:
            sentence_text = str(evt.get("text", "")).strip()
            words = [w for w in sentence_text.split() if w]
            if not words:
                continue

            sent_start = _ticks_to_seconds(evt.get("offset"))
            sent_duration = _ticks_to_seconds(evt.get("duration"))
            if sent_duration <= 0:
                sent_duration = len(words) * 0.3  # fallback ~300ms/word

            per_word = sent_duration / len(words)
            for i, word in enumerate(words):
                w_start = sent_start + i * per_word
                w_end = w_start + per_word
                word_timeline.append(
                    {
                        "word": word,
                        "start": w_start,
                        "end": w_end,
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
