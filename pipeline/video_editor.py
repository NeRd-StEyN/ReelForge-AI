from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, CompositeAudioClip
import moviepy.video.fx.all as vfx
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os
import random
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

def create_text_image(text, size=(1080, 1920), font_size=150, content_type=None):
    """Create high-contrast word-pop subtitles for mobile reels.
    
    Color-coded per content type: red for horror, pink for girl facts, white default.
    """
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
    
    line_spacing = int(font_size * 0.25)
    total_h = len(lines) * font_size + (max(0, len(lines) - 1) * line_spacing)
    # Position subtitles at 75% height — slightly higher for word-pop visibility.
    current_y = int(size[1] * 0.75) - (total_h // 2)
    
    # Color-coded text per content type for thematic consistency.
    if content_type in ("horror_reel", "horror_story"):
        text_color = (255, 50, 50)       # Blood red for horror
    elif content_type == "girl_facts":
        text_color = (255, 105, 180)     # Hot pink for girl facts
    else:
        text_color = (255, 255, 255)     # White default
    stroke_color = (0, 0, 0)
    stroke_width = 10
    shadow_color = (0, 0, 0, 200)
    shadow_offset = (5, 5)
    
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
        
        # Draw heavy stroke behind text for readability against any footage.
        for adj_x in range(-stroke_width, stroke_width+1):
            for adj_y in range(-stroke_width, stroke_width+1):
                draw.text((x+adj_x, current_y+adj_y), line, font=font, fill=stroke_color)
                
        # Draw main text — crisp white for word-pop impact.
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


def _apply_color_grade(clip, content_type):
    """Apply content-specific color grading to a visual clip."""
    if content_type in ("horror_reel", "horror_story"):
        # Dark blue desaturated horror look
        def horror_grade(frame):
            f = frame.astype(np.float32)
            gray = np.mean(f, axis=2, keepdims=True)
            f = f * 0.5 + gray * 0.5   # desaturate 50%
            f[:,:,0] *= 0.7             # red down
            f[:,:,1] *= 0.75            # green down
            f[:,:,2] *= 1.15            # blue up
            f *= 0.75                   # darken overall
            return np.clip(f, 0, 255).astype(np.uint8)
        return clip.fl_image(horror_grade)
    elif content_type == "girl_facts":
        # Warm vibrant look
        def warm_grade(frame):
            f = frame.astype(np.float32)
            f[:,:,0] *= 1.12            # red up
            f[:,:,1] *= 0.95            # green slight down
            f[:,:,2] *= 0.85            # blue down
            f *= 1.05                   # slight brighten
            return np.clip(f, 0, 255).astype(np.uint8)
        return clip.fl_image(warm_grade)
    return clip


def _create_flash_overlay(duration, scene_duration, content_type):
    """Create a brief flash overlay at the start of a scene for transitions."""
    if content_type in ("horror_reel", "horror_story"):
        # Dark red flash for horror
        color = [80, 0, 0, 180]
    else:
        # Soft white flash for girl facts
        color = [255, 255, 255, 160]
    flash_img = np.full((1920, 1080, 4), color, dtype=np.uint8)
    flash_clip = ImageClip(flash_img).set_duration(min(duration, scene_duration))
    return flash_clip


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


# --- Content-specific background music ---
_BG_MUSIC_URLS = {
    "horror": os.getenv("HORROR_BG_MUSIC_URL",
        "https://cdn.pixabay.com/audio/2024/02/14/audio_8e8580ef47.mp3"),  # Dark suspense ambient
    "girl": os.getenv("GIRL_BG_MUSIC_URL",
        "https://cdn.pixabay.com/audio/2024/11/01/audio_1f6b285aea.mp3"),  # Chill lo-fi beat
}


def _maybe_download_bg_music(target_path, url):
    """Download a royalty-free background beat if not already cached."""
    if os.path.exists(target_path):
        return target_path
    if os.getenv("ENABLE_BG_MUSIC", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    try:
        print(f"Downloading background music from {url[:60]}...")
        urllib.request.urlretrieve(url, target_path)
        print("Background music downloaded.")
        return target_path
    except Exception as e:
        print(f"Could not download background music: {e}")
        return None


def _mix_background_music(narration_audio, total_duration, content_type=None):
    """Mix a content-specific low-volume background beat under the narration."""
    if content_type in ("horror_reel", "horror_story"):
        filename = "bg_music_horror.mp3"
        url = _BG_MUSIC_URLS["horror"]
        volume = 0.18  # Slightly louder for horror ambiance
    else:
        filename = "bg_music_girl.mp3"
        url = _BG_MUSIC_URLS["girl"]
        volume = 0.12

    bg_path = os.path.join("assets", "audio", filename)
    bg_path = _maybe_download_bg_music(bg_path, url)
    if not bg_path:
        return narration_audio

    try:
        bg_music = AudioFileClip(bg_path)
        if bg_music.duration < total_duration:
            loops_needed = int(total_duration / bg_music.duration) + 1
            from moviepy.editor import concatenate_audioclips
            bg_music = concatenate_audioclips([bg_music] * loops_needed)
        bg_music = bg_music.subclip(0, total_duration)
        bg_music = bg_music.volumex(volume)
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


def _build_dynamic_subtitle_clips(events, scene_start, scene_duration, words_per_chunk=1, content_type=None):
    """Create word-by-word karaoke-style subtitle clips synced to spoken timing.
    
    Shows ONE word at a time in big bold font, perfectly synced to when the
    voice speaks it — the viral TikTok/Reels "word pop" caption style that
    keeps viewers reading and watching till the end.
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
        local_end = min(scene_duration, max(local_start + 0.25, last_end - scene_start))
        local_duration = max(0.15, local_end - local_start)

        # Big bold single-word caption — color-coded per content type.
        text_img = create_text_image(chunk_text, font_size=130, content_type=content_type)
        txt_clip = (
            ImageClip(text_img)
            .set_start(local_start)
            .set_duration(local_duration)
        )
        clips.append(txt_clip)
        index += words_per_chunk

    return clips


def _build_even_word_clips(text, total_duration, content_type=None):
    """Fallback: show one word at a time, evenly spaced across the duration.
    
    Used when word-level timing from TTS is unavailable. Each word gets
    an equal share of the total duration so only one word is visible at a time.
    """
    words = _split_words(text)
    if not words:
        return []

    clips = []
    word_duration = total_duration / len(words)

    for idx, word in enumerate(words):
        start = idx * word_duration
        dur = max(0.15, word_duration)
        text_img = create_text_image(word, font_size=130, content_type=content_type)
        clip = (
            ImageClip(text_img)
            .set_start(start)
            .set_duration(dur)
        )
        clips.append(clip)

    return clips


def generate_thumbnail(title, content_type, output_path, size=(1080, 1920)):
    """Generate an eye-catching cover/thumbnail image for the reel grid."""
    # Background color per content type
    if content_type in ("horror_reel", "horror_story"):
        bg_color = (10, 5, 20)  # Near-black with purple tint
        text_color = (255, 50, 50)  # Blood red
        accent = (80, 0, 0)
    else:
        bg_color = (25, 5, 15)  # Dark warm
        text_color = (255, 105, 180)  # Hot pink
        accent = (80, 20, 40)

    img = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(img)

    # Draw accent gradient bars
    for y in range(0, size[1], 4):
        alpha = max(0, 1.0 - abs(y - size[1] * 0.5) / (size[1] * 0.5))
        bar_color = tuple(int(c * alpha * 0.3) for c in accent)
        draw.rectangle([0, y, size[0], y + 2], fill=bar_color)

    font = _load_caption_font(90)
    # Word-wrap the title
    words = title.split()
    lines = []
    current = []
    for w in words:
        current.append(w)
        if draw.textlength(" ".join(current), font=font) > size[0] - 160:
            current.pop()
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))

    total_h = len(lines) * 110
    y_start = (size[1] - total_h) // 2
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        x = (size[0] - w) / 2
        # Stroke
        for ax in range(-6, 7):
            for ay in range(-6, 7):
                draw.text((x+ax, y_start+ay), line, font=font, fill=(0, 0, 0))
        draw.text((x, y_start), line, font=font, fill=text_color)
        y_start += 110

    img.save(output_path, quality=95)
    print(f"Thumbnail saved to {output_path}")
    return output_path


def create_video(scenes, voiceovers, visuals, output_file, word_timeline=None, content_type=None):
    """Combines voiceovers and visuals into a final video with content-aware effects."""
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

            # Apply content-specific color grading
            clip = _apply_color_grade(clip, content_type)

            # Dramatic zoom on last horror scene for twist reveal effect
            if content_type in ("horror_reel", "horror_story") and i == len(scenes) - 1:
                zoom_start = 1.0
                zoom_end = 1.25  # More aggressive zoom for dramatic twist
                clip = clip.resize(lambda t: zoom_start + (zoom_end - zoom_start) * (t / max(0.1, duration)))
                clip = clip.resize((1080, 1920))

            subtitle_layers = []
            if i < len(scene_word_events) and scene_word_events[i]:
                subtitle_layers = _build_dynamic_subtitle_clips(
                    scene_word_events[i],
                    scene_starts[i],
                    duration,
                    content_type=content_type,
                )
            if not subtitle_layers:
                # Fallback: split scene text into single words, evenly timed
                subtitle_layers = _build_even_word_clips(
                    scene['text'], duration, content_type=content_type
                )

            # Flash transition overlay at the start of every scene except the first
            extra_overlays = []
            if i > 0:
                flash = _create_flash_overlay(0.1, duration, content_type)
                extra_overlays.append(flash)

            video_scene = CompositeVideoClip([clip] + subtitle_layers + extra_overlays)
            clips.append(video_scene)

        print("Concatenating clips...")
        final_video = concatenate_videoclips(clips, method="compose")

        # Mix content-specific background music under the narration.
        mixed_audio = _mix_background_music(narration, narration.duration, content_type=content_type)
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
        clip = _apply_color_grade(clip, content_type)
        clip = clip.set_audio(audio)
        
        # Word-by-word subtitles (one word at a time on screen)
        subtitle_layers = _build_even_word_clips(
            scene['text'], duration, content_type=content_type
        )
        
        extra_overlays = []
        if i > 0:
            flash = _create_flash_overlay(0.1, duration, content_type)
            extra_overlays.append(flash)

        video_scene = CompositeVideoClip([clip] + subtitle_layers + extra_overlays)
        clips.append(video_scene)
    
    print("Concatenating clips...")
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.06)
    
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
