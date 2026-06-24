import os
import json
import re
import glob

# CRITICAL FIX for MoviePy 1.x crashing on modern Pillow 10+
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from pipeline.script_gen import generate_script_payload
from pipeline.voice_gen import run_generate_voiceover, run_generate_voiceover_with_timestamps
from pipeline.visual_gen import fetch_pexels_video, fetch_pexels_image, create_placeholder_image
from pipeline.video_editor import create_video
from pipeline.seo_gen import generate_seo_metadata, save_metadata
from pipeline.insta_handler import get_insta_client, get_performance_data
from dotenv import load_dotenv

load_dotenv()

def clean_json_response(response_text):
    """Extracts JSON from a response string that might contain markdown blocks."""
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if match:
        return match.group(0)
    return response_text


def _env_flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _get_tts_voice():
    return (os.getenv("TTS_VOICE") or "hi-IN-SwaraNeural").strip()


def cleanup_generated_assets():
    """Remove old generated scene files so each run starts clean."""
    patterns = [
        "assets/audio/scene_*.mp3",
        "assets/audio/full_narration.mp3",
        "assets/video/scene_*.mp4",
        "assets/images/scene_*.jpg",
        "assets/images/placeholder_*.jpg",
        "output_videoTEMP_MPY_wvf_snd.mp4",
    ]

    removed = 0
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass

    print(f"Cleanup complete. Removed {removed} old generated files.")

def main(topic, feedback_summary="", tts_voice_override=None):
    print(f"Starting pipeline...")
    tts_voice = tts_voice_override or _get_tts_voice()
    print(f"[Voice] TTS voice: {tts_voice}")

    if _env_flag("AUTO_CLEANUP_ASSETS", "true"):
        cleanup_generated_assets()

    # 0. Optional: Fetch Instagram analytics for feedback-based scripting.
    analytics_data = None
    if _env_flag("ENABLE_INSTAGRAM_ANALYTICS", "false"):
        cl = get_insta_client()
        analytics_data = get_performance_data(cl)
        if analytics_data:
            print(f"[Analytics] Live data fetched: {len(analytics_data)} reels.")
        else:
            print("[Analytics] Live fetch failed — script will use saved history if available.")
    else:
        print("Skipping Instagram analytics login (ENABLE_INSTAGRAM_ANALYTICS=false).")

    # 1. Generate Script using AI Feedback
    print(f"Brainstorming script using topic: '{topic}' and past performance data...")
    script_json = generate_script_payload(topic, analytics_data=analytics_data, feedback_summary=feedback_summary)

    scenes = script_json['scenes']
    print(f"Done Script generated with {len(scenes)} scenes.")
    
    use_single_narration = _env_flag("SINGLE_NARRATION_MODE", "true")
    voiceover_paths = []
    visual_paths = []
    word_timeline = None
    
    # Create asset folders if they don't exist
    os.makedirs("assets/audio", exist_ok=True)
    os.makedirs("assets/video", exist_ok=True)
    os.makedirs("assets/images", exist_ok=True)
    
    for i, scene in enumerate(scenes):
        print(f"Processing scene {i+1}/{len(scenes)}...")
        if not use_single_narration:
            # Legacy mode: generate one voice clip per scene.
            vo_path = f"assets/audio/scene_{i+1}.mp3"
            run_generate_voiceover(scene['text'], vo_path, voice=tts_voice)
            voiceover_paths.append(vo_path)
        
        # Get visual mood from scene data (new field from updated script_gen)
        visual_mood = scene.get('visual_mood', 'neutral')

        # 3. Fetch Visuals — with mood and scene index for diversity
        visual_path = f"assets/video/scene_{i+1}.mp4"
        # Try video first
        res = fetch_pexels_video(
            scene['visual_keyword'],
            visual_path,
            visual_mood=visual_mood,
            scene_index=i,
        )
        if not res:
            # Fallback to image
            visual_path = f"assets/images/scene_{i+1}.jpg"
            res = fetch_pexels_image(
                scene['visual_keyword'],
                visual_path,
                visual_mood=visual_mood,
                scene_index=i,
            )
        
        if not res:
            print(f"No visual found for scene {i+1}. Using placeholder.")
            visual_path = f"assets/images/placeholder_{i+1}.jpg"
            create_placeholder_image(visual_path, scene['visual_keyword'])
            visual_paths.append(visual_path)
        else:
            visual_paths.append(visual_path)
            
    if use_single_narration:
        print("Generating one continuous narration track for smoother voice flow...")
        full_narration_text = " ".join(
            " ".join(str(scene.get('text', '')).replace("\n", " ").split())
            for scene in scenes
        ).strip()
        full_narration_path = "assets/audio/full_narration.mp3"
        _, word_timeline = run_generate_voiceover_with_timestamps(
            full_narration_text,
            full_narration_path,
            voice=tts_voice,
        )
        voice_input = full_narration_path
    else:
        voice_input = voiceover_paths

    print("Assembling final video...")
    output_file = "output_video.mp4"
    # Pass content theme for theme-aware background music selection
    create_video(
        scenes,
        voice_input,
        visual_paths,
        output_file,
        word_timeline=word_timeline,
        content_theme="default",  # Auto-detected from scenes + domain inside create_video
    )
    
    # 5. Generate SEO Metadata
    print("Generating SEO metadata...")
    metadata = generate_seo_metadata(topic, script_json)
    save_metadata(metadata, "video_metadata.json")
    
    # 6. Auto Send to Make.com
    caption_tags = metadata.get('hashtags') or metadata.get('tags') or []
    caption_text = f"{metadata.get('description', '')}".strip()
    from pipeline.make_handler import send_to_make_webhook
    send_to_make_webhook(output_file, metadata.get('title', 'AI Video'), caption_text)
    
    print(f"Pipeline complete! Video saved to: {output_file}")
    print(f"Metadata saved to: video_metadata.json")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        # Instead of prompting, generate a generic topic to allow seamless headless cron execution
        topic = "A shocking, unknown, and fascinating fact"
    main(topic)
