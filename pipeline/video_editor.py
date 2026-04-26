from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
import moviepy.video.fx.all as vfx
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os


def _load_caption_font(font_size):
    """Load a bold caption font reliably across Windows/Linux/macOS runners."""
    font_candidates = [
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "Nirmala.ttf",
        "mangal.ttf",
        "arialbd.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception:
            continue
    return ImageFont.load_default()

def create_text_image(text, size=(1080, 1920), font_size=150):
    """Create high-contrast yellow outlined subtitles for mobile reels."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _load_caption_font(font_size)
    
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
    """Load, fit, and duration-lock a visual for 1080x1920 reels."""
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

    return clip


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


def _build_dynamic_subtitle_clips(events, scene_start, scene_duration, words_per_chunk=1):
    """Create rolling subtitle clips aligned to spoken word boundaries."""
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

        text_img = create_text_image(chunk_text, font_size=68)
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
                text_img = create_text_image(scene['text'], font_size=72)
                subtitle_layers = [ImageClip(text_img).set_duration(duration)]

            video_scene = CompositeVideoClip([clip] + subtitle_layers)
            clips.append(video_scene)

        print("Concatenating clips...")
        final_video = concatenate_videoclips(clips, method="compose").set_audio(narration)
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
        text_img = create_text_image(scene['text'], font_size=72)
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
