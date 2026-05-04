from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, CompositeAudioClip
import moviepy.video.fx.all as vfx
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os
import urllib.request


def _contains_devanagari(text):
    for ch in str(text or ""):
        if "\u0900" <= ch <= "\u097F":
            return True
    return False


def _render_signature(font, text):
    canvas = Image.new("L", (700, 140), 0)
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 6), text, font=font, fill=255)
    return canvas.tobytes()


def _font_supports_devanagari(font):
    """Heuristic: rendered Hindi should not look identical to tofu box fallback."""
    try:
        sample = "कहानी रात डरावना"
        tofu = "□□□□□□□□□□□□"
        return _render_signature(font, sample) != _render_signature(font, tofu)
    except Exception:
        return False


def _maybe_download_noto_devanagari_bold(target_path):
    if os.path.exists(target_path):
        return target_path

    if os.getenv("AUTO_DOWNLOAD_HINDI_FONT", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    url = (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/"
        "NotoSansDevanagari/NotoSansDevanagari-Bold.ttf"
    )
    try:
        urllib.request.urlretrieve(url, target_path)
        return target_path
    except Exception:
        return None


def _load_caption_font(font_size):
    """Load a bold Hindi-capable caption font across runners."""
    env_font = (os.getenv("SUBTITLE_FONT_PATH") or "").strip()
    bundled_noto = os.path.join("assets", "fonts", "NotoSansDevanagari-Bold.ttf")
    _maybe_download_noto_devanagari_bold(bundled_noto)

    font_candidates = [
        env_font,
        bundled_noto,
        "C:/Windows/Fonts/KohinoorDevanagari-Bold.ttf",
        "C:/Windows/Fonts/KohinoorDevanagari-Regular.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/Library/Fonts/NotoSansDevanagari-Bold.ttf",
        "/Library/Fonts/Mangal.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "NotoSansDevanagari-Bold.ttf",
        "Nirmala.ttf",
        "mangal.ttf",
        "arialbd.ttf",
        "DejaVuSans-Bold.ttf",
    ]

    for font_path in font_candidates:
        if not font_path:
            continue
        try:
            loaded = ImageFont.truetype(font_path, font_size)
            if _font_supports_devanagari(loaded):
                return loaded
        except Exception:
            continue

    return ImageFont.load_default()

def create_text_image(text, size=(1080, 1920), font_size=150):
    """Create high-contrast yellow outlined subtitles for mobile reels."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _load_caption_font(font_size)
    if _contains_devanagari(text) and not _font_supports_devanagari(font):
        print(
            "Warning: Hindi subtitle font missing. Set SUBTITLE_FONT_PATH or keep AUTO_DOWNLOAD_HINDI_FONT=true."
        )
    
    clean_text = " ".join(str(text or "").replace("\n", " ").split())
    words = clean_text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        w = draw.textlength(" ".join(current_line), font=font)
        # Wrap text to fit a readable lower-third block with side padding.
        if w > size[0] - 140:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    if not lines:
        return np.array(img)
    
    line_spacing = int(font_size * 0.22)
    total_h = len(lines) * font_size + (max(0, len(lines) - 1) * line_spacing)
    # Keep subtitles around the lower third similar to short-form caption style.
    current_y = int(size[1] * 0.80) - (total_h // 2)
    
    text_color = (255, 210, 30)
    stroke_color = (0, 0, 0)
    stroke_width = 8
    shadow_color = (0, 0, 0, 185)
    shadow_offset = (4, 4)
    
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (size[0] - w) / 2

        # Draw soft shadow first so text remains visible even on bright frames.
        draw.text(
            (x + shadow_offset[0], current_y + shadow_offset[1]),
            line,
            font=font,
            fill=shadow_color,
        )
        
        # Draw stroke behind text for readability against bright/dark footage.
        for adj_x in range(-stroke_width, stroke_width+1):
            for adj_y in range(-stroke_width, stroke_width+1):
                draw.text((x+adj_x, current_y+adj_y), line, font=font, fill=stroke_color)
                
        # Draw main text.
        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += font_size + line_spacing
        
    return np.array(img)


def _prepare_visual_clip(visual_path, duration):
    """Load, fit, duration-lock, and apply Ken Burns zoom for 1080x1920 reels."""
    if visual_path.endswith(('.mp4', '.mov')):
        clip = VideoFileClip(visual_path).set_duration(duration)
        if clip.duration < duration:
            clip = clip.fx(vfx.loop, duration=duration)
    else:
        clip = ImageClip(visual_path).set_duration(duration)

    w, h = clip.size
    target_ratio = 1080 / 1920
    current_ratio = w / h

    if current_ratio > target_ratio:
        clip = clip.resize(height=1920)
        w_new = clip.size[0]
        clip = clip.crop(x1=(w_new - 1080) / 2, y1=0, x2=(w_new + 1080) / 2, y2=1920)
    else:
        clip = clip.resize(width=1080)
        h_new = clip.size[1]
        clip = clip.crop(x1=0, y1=(h_new - 1920) / 2, x2=1080, y2=(h_new + 1920) / 2)

    # Ken Burns slow zoom (1.0x → 1.12x) for dynamic feel — prevents static boring look.
    zoom_start = 1.0
    zoom_end = 1.12
    clip = clip.resize(lambda t: zoom_start + (zoom_end - zoom_start) * (t / max(0.1, duration)))
    # Re-crop to 1080x1920 after zoom to keep frame size consistent.
    clip = clip.resize((1080, 1920))

    return clip


def _create_hook_overlay(duration=2.5, size=(1080, 1920)):
    """Create a bold 'WAIT FOR IT 🔥' hook text for the first few seconds."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_caption_font(80)

    hook_texts = ["👆 SUNNA PADEGA 🔥", "RUKO... 🔥", "WAIT FOR IT 👀", "YE SUNLO 😏"]
    import random
    hook_text = random.choice(hook_texts)

    w = draw.textlength(hook_text, font=font)
    x = (size[0] - w) / 2
    y = int(size[1] * 0.12)  # Top area

    # Black stroke for readability
    stroke_w = 6
    for ax in range(-stroke_w, stroke_w + 1):
        for ay in range(-stroke_w, stroke_w + 1):
            draw.text((x + ax, y + ay), hook_text, font=font, fill=(0, 0, 0))
    draw.text((x, y), hook_text, font=font, fill=(255, 60, 60))

    return ImageClip(np.array(img)).set_duration(duration)


def _create_follow_cta(duration=3.0, size=(1080, 1920)):
    """Create a 'Follow for Part 2 🔥' CTA text for the last few seconds."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_caption_font(70)

    cta_text = "FOLLOW FOR PART 2 🔥"
    w = draw.textlength(cta_text, font=font)
    x = (size[0] - w) / 2
    y = int(size[1] * 0.15)  # Top area, below hook position

    # Black stroke
    stroke_w = 5
    for ax in range(-stroke_w, stroke_w + 1):
        for ay in range(-stroke_w, stroke_w + 1):
            draw.text((x + ax, y + ay), cta_text, font=font, fill=(0, 0, 0))
    draw.text((x, y), cta_text, font=font, fill=(0, 255, 100))

    return ImageClip(np.array(img)).set_duration(duration)


def _maybe_download_bg_music(target_path):
    """Download a royalty-free background beat if not already cached."""
    if os.path.exists(target_path):
        return target_path

    if os.getenv("ENABLE_BG_MUSIC", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    # Free royalty-free lo-fi beat from Pixabay (CC0 license).
    url = "https://cdn.pixabay.com/audio/2024/11/01/audio_1f6b285aea.mp3"
    try:
        print("Downloading background music...")
        urllib.request.urlretrieve(url, target_path)
        print("Background music downloaded.")
        return target_path
    except Exception as e:
        print(f"Could not download background music: {e}")
        return None


def _mix_background_music(narration_audio, total_duration):
    """Mix a low-volume background beat under the narration for energy."""
    bg_path = os.path.join("assets", "audio", "bg_music.mp3")
    bg_path = _maybe_download_bg_music(bg_path)
    if not bg_path:
        return narration_audio

    try:
        bg_music = AudioFileClip(bg_path)
        # Loop if shorter than the video.
        if bg_music.duration < total_duration:
            loops_needed = int(total_duration / bg_music.duration) + 1
            from moviepy.editor import concatenate_audioclips
            bg_music = concatenate_audioclips([bg_music] * loops_needed)
        bg_music = bg_music.subclip(0, total_duration)
        # Keep background music at 12% volume so voice stays clear.
        bg_music = bg_music.volumex(0.12)
        mixed = CompositeAudioClip([narration_audio, bg_music])
        return mixed
    except Exception as e:
        print(f"Could not mix background music: {e}")
        return narration_audio


def _scene_durations_from_word_weights(scenes, total_duration, min_duration=2.0):
    """Distribute total narration time across scenes by word count with a floor."""
    if not scenes:
        return []

    count = len(scenes)
    safe_min = min(min_duration, max(0.4, total_duration / count))
    word_weights = [max(1, len(str(scene.get('text', '')).split())) for scene in scenes]
    weight_sum = sum(word_weights)

    extra_budget = max(0.0, total_duration - (count * safe_min))
    durations = [safe_min + (extra_budget * (w / weight_sum)) for w in word_weights]

    # Keep exact sync with audio by correcting float drift on last segment.
    drift = total_duration - sum(durations)
    durations[-1] += drift
    return durations


def _split_words(text):
    return [w for w in str(text or "").replace("\n", " ").split() if w]


def _assign_timeline_to_scenes(scenes, word_timeline):
    """Assign word events to scenes by each scene's script word count."""
    if not scenes:
        return []

    timeline = list(word_timeline or [])
    cursor = 0
    assignments = []

    for i, scene in enumerate(scenes):
        desired = max(1, len(_split_words(scene.get('text', ''))))
        remaining_scenes = len(scenes) - i
        remaining_words = max(0, len(timeline) - cursor)

        if remaining_scenes <= 1:
            take = remaining_words
        else:
            min_left_for_rest = remaining_scenes - 1
            take = min(desired, max(1, remaining_words - min_left_for_rest))
            if remaining_words <= min_left_for_rest:
                take = 0

        assignments.append(timeline[cursor: cursor + take])
        cursor += take

    if assignments and cursor < len(timeline):
        assignments[-1].extend(timeline[cursor:])

    return assignments


def _scene_durations_from_timeline(scene_word_events, total_duration):
    """Build scene durations based on real word timing boundaries."""
    count = len(scene_word_events)
    if count == 0:
        return []

    starts = [None] * count
    for i, events in enumerate(scene_word_events):
        if events:
            starts[i] = max(0.0, float(events[0].get('start', 0.0)))

    scene_starts = [0.0] * count
    for i in range(1, count):
        if starts[i] is not None:
            scene_starts[i] = starts[i]
        else:
            scene_starts[i] = scene_starts[i - 1]

    durations = []
    for i in range(count):
        start = scene_starts[i]
        end = scene_starts[i + 1] if i + 1 < count else total_duration
        durations.append(max(0.4, end - start))

    drift = total_duration - sum(durations)
    durations[-1] += drift
    return durations


def _build_dynamic_subtitle_clips(events, scene_start, scene_duration, words_per_chunk=3):
    """Create rolling subtitle clips aligned to spoken word boundaries.
    
    Shows 2-3 words at a time in big bold font, synced to when the voice
    speaks them — the standard viral reel caption style.
    """
    clips = []
    if not events:
        return clips

    index = 0
    while index < len(events):
        chunk = events[index: index + words_per_chunk]
        chunk_text = " ".join(str(item.get('word', '')).strip() for item in chunk).strip()
        if not chunk_text:
            index += words_per_chunk
            continue

        first_start = float(chunk[0].get('start', 0.0))
        last_end = float(chunk[-1].get('end', first_start + 0.3))
        local_start = max(0.0, first_start - scene_start)
        local_end = min(scene_duration, max(local_start + 0.35, last_end - scene_start))
        local_duration = max(0.2, local_end - local_start)

        # Big bold font for word-synced captions — easy to read on mobile.
        text_img = create_text_image(chunk_text, font_size=100)
        txt_clip = (
            ImageClip(text_img)
            .set_start(local_start)
            .set_duration(local_duration)
        )
        clips.append(txt_clip)
        index += words_per_chunk

    return clips

def create_video(scenes, voiceovers, visuals, output_file, word_timeline=None):
    """Combines voiceovers and visuals into a final video."""
    clips = []

    # Continuous narration mode: one TTS file over multiple visual scenes.
    if isinstance(voiceovers, str):
        narration = AudioFileClip(voiceovers)
        scene_word_events = _assign_timeline_to_scenes(scenes, word_timeline or [])
        if word_timeline:
            durations = _scene_durations_from_timeline(scene_word_events, narration.duration)
        else:
            durations = _scene_durations_from_word_weights(scenes, narration.duration)

        scene_starts = []
        acc = 0.0
        for d in durations:
            scene_starts.append(acc)
            acc += d

        for i, scene in enumerate(scenes):
            print(f"Processing clip {i+1}...")
            duration = durations[i]
            clip = _prepare_visual_clip(visuals[i], duration)

            subtitle_layers = []
            if i < len(scene_word_events) and scene_word_events[i]:
                subtitle_layers = _build_dynamic_subtitle_clips(
                    scene_word_events[i],
                    scene_starts[i],
                    duration,
                )
            if not subtitle_layers:
                text_img = create_text_image(scene['text'], font_size=100)
                subtitle_layers = [ImageClip(text_img).set_duration(duration)]

            # Add hook text overlay on first scene (first 2.5 seconds).
            extra_overlays = []
            if i == 0:
                hook_overlay = _create_hook_overlay(duration=min(2.5, duration))
                extra_overlays.append(hook_overlay)

            # Add "Follow for Part 2" CTA on last scene (last 3 seconds).
            if i == len(scenes) - 1:
                cta_dur = min(3.0, duration)
                cta_overlay = _create_follow_cta(duration=cta_dur).set_start(max(0, duration - cta_dur))
                extra_overlays.append(cta_overlay)

            video_scene = CompositeVideoClip([clip] + subtitle_layers + extra_overlays)
            clips.append(video_scene)

        print("Concatenating clips...")
        final_video = concatenate_videoclips(clips, method="compose")

        # Mix background music under the narration for energy.
        mixed_audio = _mix_background_music(narration, narration.duration)
        final_video = final_video.set_audio(mixed_audio)
        final_video = final_video.set_duration(narration.duration)

        print(f"Writing file: {output_file}")
        final_video.write_videofile(
            output_file,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            bitrate="10000k",
            threads=4,
            preset="medium",
        )
        return output_file
    
    for i, scene in enumerate(scenes):
        print(f"Processing clip {i+1}...")
        audio = AudioFileClip(voiceovers[i])
        duration = audio.duration

        clip = _prepare_visual_clip(visuals[i], duration)
        
        clip = clip.set_audio(audio)
        
        # Add subtitle using PIL
        text_img = create_text_image(scene['text'], font_size=100)
        txt_clip = ImageClip(text_img).set_duration(duration)
        
        video_scene = CompositeVideoClip([clip, txt_clip])
        clips.append(video_scene)
    
    print("Concatenating clips...")
    # Slight overlap helps hide tiny seam pauses between scene TTS chunks.
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.06)
    
    print(f"Writing file: {output_file}")
    final_video.write_videofile(
        output_file,
        fps=30,  # 30 fps is stable and platform-friendly for reels.
        codec="libx264",
        audio_codec="aac",
        bitrate="10000k",  # Higher bitrate for cleaner 1080x1920 output.
        threads=4,
        preset="medium",  # Better quality compression than ultrafast.
    )
    return output_file
