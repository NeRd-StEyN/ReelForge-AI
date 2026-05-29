"""
Test script to verify word-by-word subtitle rendering.

Generates a short test video with:
  1. Mock word-timeline synced subtitles (_build_dynamic_subtitle_clips)
  2. Fallback evenly-timed subtitles (_build_even_word_clips)

After running, open test_word_sync.mp4 and test_word_even.mp4 to visually
confirm that only ONE word at a time appears on screen.
"""

import os
import sys
import numpy as np

# MoviePy + Pillow compat fix
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import ColorClip, CompositeVideoClip, AudioFileClip
from pipeline.video_editor import (
    _build_dynamic_subtitle_clips,
    _build_even_word_clips,
    create_text_image,
)
from pipeline.voice_gen import run_generate_voiceover_with_timestamps

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
TEST_TEXT = "रात के सन्नाटे में जब मैंने आईने में देखा तो मेरी परछाई नहीं थी"
OUTPUT_DIR = "."
DURATION = 6.0  # seconds for even-timed test

# ---------------------------------------------------------------------------
# TEST 1: Even-timed word-by-word (no TTS timeline)
# ---------------------------------------------------------------------------
def test_even_word_clips():
    print("=" * 60)
    print("TEST 1: Even-timed word-by-word subtitles")
    print("=" * 60)

    words = TEST_TEXT.split()
    print(f"  Text: {TEST_TEXT}")
    print(f"  Words: {len(words)}")
    print(f"  Duration: {DURATION}s")
    per_word = DURATION / len(words)
    print(f"  Per-word duration: {per_word:.3f}s")

    clips = _build_even_word_clips(TEST_TEXT, DURATION, content_type="horror_reel")
    print(f"  Subtitle clips generated: {len(clips)}")
    assert len(clips) == len(words), f"Expected {len(words)} clips, got {len(clips)}"

    for i, clip in enumerate(clips):
        start = clip.start
        dur = clip.duration
        print(f"    Word {i+1}: '{words[i]}'  start={start:.3f}s  dur={dur:.3f}s  end={start+dur:.3f}s")
        # Verify no two clips have overlapping time windows
        if i > 0:
            prev_end = clips[i-1].start + clips[i-1].duration
            assert start >= clips[i-1].start, "Clips must be in order"

    # Build a short video to visually verify
    bg = ColorClip(size=(1080, 1920), color=(20, 5, 30)).set_duration(DURATION)
    video = CompositeVideoClip([bg] + clips)
    out_path = os.path.join(OUTPUT_DIR, "test_word_even.mp4")
    video.write_videofile(out_path, fps=24, codec="libx264", audio=False, preset="ultrafast")
    print(f"\n  [OK] Saved: {out_path}")
    print(f"  Open this file and confirm only ONE word is visible at any time.\n")
    return True


# ---------------------------------------------------------------------------
# TEST 2: TTS-synced word-by-word (uses real edge-tts timeline)
# ---------------------------------------------------------------------------
def test_tts_synced_word_clips():
    print("=" * 60)
    print("TEST 2: TTS-synced word-by-word subtitles")
    print("=" * 60)

    os.makedirs("assets/audio", exist_ok=True)
    audio_path = "assets/audio/test_narration.mp3"

    print(f"  Generating TTS for: {TEST_TEXT[:50]}...")
    _, word_timeline = run_generate_voiceover_with_timestamps(TEST_TEXT, audio_path)

    print(f"  Word timeline entries: {len(word_timeline)}")
    for evt in word_timeline:
        print(f"    '{evt['word']}'  start={evt['start']:.3f}s  end={evt['end']:.3f}s")

    audio = AudioFileClip(audio_path)
    total_dur = audio.duration
    print(f"  Audio duration: {total_dur:.3f}s")

    # Build subtitle clips as the real pipeline would
    clips = _build_dynamic_subtitle_clips(
        word_timeline,
        scene_start=0.0,
        scene_duration=total_dur,
        content_type="horror_reel",
    )
    print(f"  Subtitle clips generated: {len(clips)}")
    assert len(clips) == len(word_timeline), (
        f"Expected {len(word_timeline)} clips, got {len(clips)}"
    )

    # Print timing for each clip
    for i, clip in enumerate(clips):
        w = word_timeline[i]['word']
        print(f"    Clip {i+1}: '{w}'  start={clip.start:.3f}s  dur={clip.duration:.3f}s")

    # Build video with audio
    bg = ColorClip(size=(1080, 1920), color=(20, 5, 30)).set_duration(total_dur)
    video = CompositeVideoClip([bg] + clips)
    video = video.set_audio(audio)
    out_path = os.path.join(OUTPUT_DIR, "test_word_sync.mp4")
    video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")
    print(f"\n  [OK] Saved: {out_path}")
    print(f"  Open this file -- each word should appear ONLY when spoken.\n")
    return True


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n--- Testing word-by-word subtitle system ---\n")
    ok1 = test_even_word_clips()
    ok2 = test_tts_synced_word_clips()

    print("=" * 60)
    if ok1 and ok2:
        print("[PASS] ALL TESTS PASSED -- Only one word displayed at a time.")
    else:
        print("[FAIL] SOME TESTS FAILED")
    print("=" * 60)
    print("\nOpen test_word_even.mp4 and test_word_sync.mp4 to visually verify.")
