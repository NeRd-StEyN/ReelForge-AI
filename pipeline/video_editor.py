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


# ── Karaoke-Style Subtitle Rendering ────────────────────────────────

def _draw_rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle as a subtitle background pill."""
    x1, y1, x2, y2 = xy
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    draw.rectangle([x1 + r, y1, x2 - r, y2], fill=fill)
    draw.rectangle([x1, y1 + r, x2, y2 - r], fill=fill)
    draw.pieslice([x1, y1, x1 + 2 * r, y1 + 2 * r], 180, 270, fill=fill)
    draw.pieslice([x2 - 2 * r, y1, x2, y1 + 2 * r], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - 2 * r, x1 + 2 * r, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - 2 * r, y2 - 2 * r, x2, y2], 0, 90, fill=fill)


import re

def _strip_unsupported_chars(text):
    """Strip anything that isn't Devanagari, Basic Latin, or standard punctuation to prevent tofu boxes."""
    # This aggressive whitelist removes ALL emojis, complex symbols, and unsupported foreign alphabets.
    return re.sub(r'[^\n\r\u0020-\u007E\u0900-\u097F\u2000-\u20CF]', '', str(text))

def create_text_image(text, size=(1080, 1920), font_size=100, highlight_word_index=-1):
    """Create premium karaoke-style subtitles with highlighted active word.
    
    - White text by default, active word highlighted in bright accent color
    - Semi-transparent dark pill background for readability
    - Bold stroke for contrast against any footage
    """
    text = _strip_unsupported_chars(text)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _load_caption_font(font_size)
    highlight_font = _load_caption_font(int(font_size * 1.15))  # Slightly bigger for active word

    if _contains_devanagari(text) and not _font_supports_devanagari(font):
        print(
            "Warning: Hindi subtitle font missing. Set SUBTITLE_FONT_PATH or keep AUTO_DOWNLOAD_HINDI_FONT=true."
        )
    
    clean_text = " ".join(str(text or "").replace("\n", " ").split())
    words = clean_text.split()
    if not words:
        return np.array(img)

    # Colors — premium white + neon accent scheme
    normal_color = (255, 255, 255)          # Clean white for non-active words
    highlight_color = (0, 255, 140)         # Neon green for active word
    stroke_color = (0, 0, 0)
    stroke_width = 6
    bg_pill_color = (0, 0, 0, 140)          # Semi-transparent dark background

    # Word wrapping
    lines = []
    current_line_words = []
    current_line_word_indices = []
    word_idx = 0

    for word in words:
        current_line_words.append(word)
        current_line_word_indices.append(word_idx)
        w = draw.textlength(" ".join(current_line_words), font=font)
        if w > size[0] - 160:
            current_line_words.pop()
            current_line_word_indices.pop()
            if current_line_words:
                lines.append((list(current_line_words), list(current_line_word_indices)))
            current_line_words = [word]
            current_line_word_indices = [word_idx]
        word_idx += 1

    if current_line_words:
        lines.append((list(current_line_words), list(current_line_word_indices)))

    if not lines:
        return np.array(img)

    line_spacing = int(font_size * 0.3)
    total_h = len(lines) * int(font_size * 1.2) + (max(0, len(lines) - 1) * line_spacing)
    # Keep subtitles in the lower third
    base_y = int(size[1] * 0.78) - (total_h // 2)

    # Draw background pill
    # Calculate total text block dimensions
    max_line_width = 0
    for line_words, _ in lines:
        w = draw.textlength(" ".join(line_words), font=font)
        max_line_width = max(max_line_width, w)

    pill_padding_x = 40
    pill_padding_y = 20
    pill_x1 = max(0, (size[0] - max_line_width) / 2 - pill_padding_x)
    pill_y1 = base_y - pill_padding_y
    pill_x2 = min(size[0], (size[0] + max_line_width) / 2 + pill_padding_x)
    pill_y2 = base_y + total_h + pill_padding_y
    _draw_rounded_rect(draw, (pill_x1, pill_y1, pill_x2, pill_y2), 24, bg_pill_color)

    current_y = base_y
    for line_words, line_word_indices in lines:
        full_line = " ".join(line_words)
        full_w = draw.textlength(full_line, font=font)
        x_start = (size[0] - full_w) / 2

        # Draw word by word for karaoke effect
        x_cursor = x_start
        for i, (word, w_idx) in enumerate(zip(line_words, line_word_indices)):
            is_active = (w_idx == highlight_word_index)
            use_font = highlight_font if is_active else font
            color = highlight_color if is_active else normal_color
            y_offset = -4 if is_active else 0  # Slight lift for active word

            # Draw stroke
            for adj_x in range(-stroke_width, stroke_width + 1, 2):
                for adj_y in range(-stroke_width, stroke_width + 1, 2):
                    draw.text((x_cursor + adj_x, current_y + adj_y + y_offset), word, font=use_font, fill=stroke_color)

            # Draw main text
            draw.text((x_cursor + 0, current_y + y_offset), word, font=use_font, fill=color)

            # Advance cursor (use normal font width for consistent spacing)
            word_w = draw.textlength(word + " ", font=font)
            x_cursor += word_w

        current_y += int(font_size * 1.2) + line_spacing

    return np.array(img)


def create_text_image_simple(text, size=(1080, 1920), font_size=100):
    """Simplified subtitle image for fallback — white text with stroke and pill background."""
    return create_text_image(text, size=size, font_size=font_size, highlight_word_index=-1)


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

    # Ken Burns slow zoom (1.0x -> 1.12x) for dynamic feel -- prevents static boring look.
    zoom_start = 1.0
    zoom_end = 1.12
    clip = clip.resize(lambda t: zoom_start + (zoom_end - zoom_start) * (t / max(0.1, duration)))
    # Re-crop to 1080x1920 after zoom to keep frame size consistent.
    clip = clip.resize((1080, 1920))

    # Apply cinematic colour grade for professional look
    clip = _apply_cinematic_grade(clip)

    return clip


def _apply_cinematic_grade(clip):
    """Apply a warm cinematic colour grade to make stock footage look professionally graded.
    
    Effect: boost contrast, warm the shadows (red/orange push), cool the highlights (blue push).
    This makes every clip look intentionally shot, not just pulled from a stock library.
    Results in a consistent visual identity across all reels.
    """
    def grade_frame(frame):
        # frame is H x W x 3 uint8 numpy array
        f = frame.astype(np.float32)

        # 1. Contrast boost: stretch luminance away from midpoint
        f = (f - 128.0) * 1.15 + 128.0

        # 2. Shadow warmth: lift reds and suppress blues in dark areas
        #    mask = how "dark" the pixel is (0.0 = bright, 1.0 = pure black)
        luminance = (f[..., 0] * 0.299 + f[..., 1] * 0.587 + f[..., 2] * 0.114)
        shadow_mask = np.clip(1.0 - luminance / 128.0, 0.0, 1.0)[..., np.newaxis]
        f[..., 0] += 12.0 * shadow_mask[..., 0]  # warm red in shadows
        f[..., 2] -= 10.0 * shadow_mask[..., 0]  # reduce blue in shadows

        # 3. Highlight cool: push slight blue in bright areas for cinematic split-tone
        highlight_mask = np.clip((luminance - 180.0) / 75.0, 0.0, 1.0)[..., np.newaxis]
        f[..., 2] += 8.0 * highlight_mask[..., 0]  # cool blue in highlights
        f[..., 1] -= 4.0 * highlight_mask[..., 0]  # slightly desaturate highlights

        # 4. Slight vignette: darken edges to draw eye to centre
        h, w = frame.shape[:2]
        cx, cy = w / 2.0, h / 2.0
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
        vignette = np.clip(1.0 - dist * 0.30, 0.55, 1.0)[..., np.newaxis]
        f = f * vignette

        return np.clip(f, 0, 255).astype(np.uint8)

    return clip.fl_image(grade_frame)


def _create_progress_bar_clip(total_duration, size=(1080, 1920), bar_height=8, color=(0, 240, 120)):
    """Create an animated neon progress bar that fills left-to-right over total_duration.
    
    Psychologically proven to increase watch time: viewers subconsciously want
    to 'finish' the bar. Placed at the very bottom edge of the frame.
    """
    def make_bar_frame(t):
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = min(1.0, t / max(0.1, total_duration))
        bar_width = int(size[0] * progress)
        bar_y = size[1] - bar_height - 2
        if bar_width > 0:
            # Main bar
            draw.rectangle([0, bar_y, bar_width, bar_y + bar_height], fill=color + (220,))
            # Bright leading edge glow
            glow_x = max(0, bar_width - 6)
            draw.rectangle([glow_x, bar_y - 1, bar_width, bar_y + bar_height + 1],
                           fill=(255, 255, 255, 160))
        return np.array(img)

    bar_clip = (
        ImageClip(make_bar_frame, ismask=False, duration=total_duration)
        .set_duration(total_duration)
    )
    return bar_clip


def _create_flash_frame(duration=0.08, size=(1080, 1920)):
    """Create a brief white flash clip used as a pattern-interrupt between scenes.
    
    A 3-4 frame white flash at scene boundaries prevents scroll-away at cut points
    (the most common viewer drop-off moment). Keeps attention locked.
    """
    img = Image.new('RGBA', size, (255, 255, 255, 200))
    flash = ImageClip(np.array(img)).set_duration(duration)
    flash = flash.crossfadein(duration * 0.4).crossfadeout(duration * 0.4)
    return flash



# ── Hook Overlay (Fixed Devanagari rendering) ───────────────────────

def _create_hook_overlay(topic="", duration=2.0, size=(1080, 1920)):
    """Create a bold title-card hook overlay for the first few seconds.
    
    Shows the reel's actual topic/title so viewers instantly know what it's about.
    This is the most critical fix: the first frame must communicate the VALUE
    within 1 second, even without audio.
    """
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Use the topic/scene text as the hook card — max 5 words so it reads instantly
    if topic and topic.strip():
        # Trim to first 5 words for instant readability on the hook card
        words = _strip_unsupported_chars(topic.strip()).split()
        hook_text = " ".join(words[:5])
        if len(words) > 5:
            hook_text += "..."
    else:
        hook_text = "\u092f\u0947 \u091c\u093e\u0928\u094b!"  # "ये जानो!" fallback

    font_size = 80
    font = _load_caption_font(font_size)

    # Word-wrap hook text to fit within frame
    words_list = hook_text.split()
    lines = []
    current = []
    for word in words_list:
        current.append(word)
        if draw.textlength(" ".join(current), font=font) > size[0] - 160:
            current.pop()
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    if not lines:
        lines = [hook_text]

    line_h = int(font_size * 1.25)
    total_h = len(lines) * line_h
    # Position in upper area — prominent but not blocking subtitles
    base_y = int(size[1] * 0.08)

    # Calculate pill bounds
    max_w = max(draw.textlength(l, font=font) for l in lines)
    pill_pad_x, pill_pad_y = 40, 16
    pill_x1 = (size[0] - max_w) / 2 - pill_pad_x
    pill_y1 = base_y - pill_pad_y
    pill_x2 = (size[0] + max_w) / 2 + pill_pad_x
    pill_y2 = base_y + total_h + pill_pad_y
    # Dark semi-transparent pill for readability over any background
    _draw_rounded_rect(draw, (pill_x1, pill_y1, pill_x2, pill_y2), 22, (0, 0, 0, 185))

    # Neon green accent bar on top of pill
    draw.rectangle([pill_x1 + 22, pill_y1, pill_x2 - 22, pill_y1 + 5], fill=(0, 240, 120))

    # Draw each line centered
    stroke_w = 5
    current_y = base_y
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (size[0] - w) / 2
        # Black stroke for legibility
        for ax in range(-stroke_w, stroke_w + 1, 2):
            for ay in range(-stroke_w, stroke_w + 1, 2):
                draw.text((x + ax, current_y + ay), line, font=font, fill=(0, 0, 0))
        # Bright white main text
        draw.text((x, current_y), line, font=font, fill=(255, 255, 255))
        current_y += line_h

    hook_clip = ImageClip(np.array(img)).set_duration(duration)
    # Smooth fade-in over first 0.3s
    hook_clip = hook_clip.crossfadein(min(0.3, duration * 0.2))
    return hook_clip


# ── CTA Overlay (Fixed Devanagari rendering) ────────────────────────

def _create_follow_cta(duration=2.5, size=(1080, 1920)):
    """Create a niche-specific 'Follow for more' CTA text overlay for the last seconds."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_caption_font(58)

    # Niche-specific CTAs — rotated for variety
    cta_options = [
        "\u092b\u093c\u0949\u0932\u094b \u0915\u0930\u094b \u2014 \u0906\u0930 \u0938\u0940\u0915\u094d\u0930\u0947\u091f \u0906\u090f\u0902\u0917\u0947!",   # "फ़ॉलो करो — और सीक्रेट आएंगे!"
        "\u0930\u094b\u091c \u0928\u092f\u0940 psychology \u2014 follow karo!",  # "रोज नयी psychology — follow karo!"
        "\u0938\u0940\u0916\u094b psychology \u2014 @itsun.known6969!",  # "सीखो psychology — @itsun.known6969!"
    ]
    cta_text = random.choice(cta_options)

    w = draw.textlength(cta_text, font=font)
    x = (size[0] - w) / 2
    y = int(size[1] * 0.10)

    # Semi-transparent background pill
    pill_pad_x, pill_pad_y = 30, 12
    _draw_rounded_rect(
        draw,
        (x - pill_pad_x, y - pill_pad_y, x + w + pill_pad_x, y + 65 + pill_pad_y),
        18,
        (0, 0, 0, 175),
    )

    # Neon green accent bar on top
    draw.rectangle([x - pill_pad_x + 18, y - pill_pad_y, x + w + pill_pad_x - 18, y - pill_pad_y + 5],
                   fill=(0, 240, 120))

    # Black stroke
    stroke_w = 5
    for ax in range(-stroke_w, stroke_w + 1, 2):
        for ay in range(-stroke_w, stroke_w + 1, 2):
            draw.text((x + ax, y + ay), cta_text, font=font, fill=(0, 0, 0))
    draw.text((x, y), cta_text, font=font, fill=(0, 255, 120))

    return ImageClip(np.array(img)).set_duration(duration)


# ── Background Music — Theme-Aware Multi-Track Pool ────────────────────────
# Each theme has a pool of 5 royalty-free tracks. A random one is picked each run.
# Each track has its own cached filename so all get cached after first download.
_BG_MUSIC_POOL = {
    "horror": [
        # Track 1: from env var (user-configured)
        {"url_env": "HORROR_BG_MUSIC_URL", "filename": "bg_horror_1.mp3", "volume": 0.35,
         "fallback_url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gathering%20Darkness.mp3"},
        # Track 2-5: royalty-free horror/dark tracks
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Fog.mp3",
         "filename": "bg_horror_2.mp3", "volume": 0.35},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Exhilarate.mp3",
         "filename": "bg_horror_3.mp3", "volume": 0.30},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Floating%20Cities.mp3",
         "filename": "bg_horror_4.mp3", "volume": 0.30},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Night%20Cave.mp3",
         "filename": "bg_horror_5.mp3", "volume": 0.35},
    ],
    "girl": [
        # Track 1: from env var (user-configured, currently Mesmerize)
        {"url_env": "GIRL_BG_MUSIC_URL", "filename": "bg_girl_1.mp3", "volume": 0.28,
         "fallback_url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mesmerize.mp3"},
        # Track 2-5: royalty-free romantic/chill/atmospheric tracks
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Chill%20Wave.mp3",
         "filename": "bg_girl_2.mp3", "volume": 0.28},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3",
         "filename": "bg_girl_3.mp3", "volume": 0.25},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Midnight%20Ride.mp3",
         "filename": "bg_girl_4.mp3", "volume": 0.28},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Relaxing%20Piano%20Music.mp3",
         "filename": "bg_girl_5.mp3", "volume": 0.22},
    ],
    "default": [
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Chill%20Wave.mp3",
         "filename": "bg_default_1.mp3", "volume": 0.28},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mesmerize.mp3",
         "filename": "bg_default_2.mp3", "volume": 0.28},
        {"url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Floating%20Cities.mp3",
         "filename": "bg_default_3.mp3", "volume": 0.28},
    ],
}


def _resolve_music_track(theme):
    """Pick a random music track from the theme pool. Returns (url, filename, volume)."""
    pool = _BG_MUSIC_POOL.get(theme) or _BG_MUSIC_POOL["default"]
    track = random.choice(pool)

    # Resolve URL: check env var first, then direct url, then fallback
    url_env_key = track.get("url_env")
    if url_env_key:
        env_url = os.getenv(url_env_key, "").strip()
        url = env_url if env_url else track.get("fallback_url", _BG_MUSIC_POOL["default"][0]["url"])
    else:
        url = track.get("url", _BG_MUSIC_POOL["default"][0]["url"])

    return url, track["filename"], track["volume"]


def _detect_content_theme(scenes=None, domain=""):
    """Detect whether content is horror-themed, girl-themed, or general."""
    combined = (domain + " " + " ".join(
        s.get("text", "") + " " + s.get("visual_keyword", "")
        for s in (scenes or [])
    )).lower()

    horror_signals = ["horror", "ghost", "bhoot", "darr", "scary", "haunted", "paranormal", "raat", "mystery", "dark"]
    girl_signals = ["girl", "ladki", "woman", "attract", "dating", "seduc", "love", "relationship", "body language"]

    horror_score = sum(1 for s in horror_signals if s in combined)
    girl_score = sum(1 for s in girl_signals if s in combined)

    if horror_score > girl_score:
        return "horror"
    elif girl_score > 0:
        return "girl"
    return "default"


def _maybe_download_bg_music(target_path, url):
    """Download a royalty-free background beat if not already cached."""
    if os.path.exists(target_path):
        return target_path

    if os.getenv("ENABLE_BG_MUSIC", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    try:
        print(f"Downloading background music to {target_path}...")
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            out_file.write(response.read())
        print("Background music downloaded.")
        return target_path
    except Exception as e:
        print(f"Could not download background music: {e}")
        return None


def _mix_background_music(narration_audio, total_duration, content_theme="default"):
    """Mix a randomly selected theme-appropriate background beat under the narration."""
    if os.getenv("ENABLE_BG_MUSIC", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return narration_audio

    bg_url, bg_filename, bg_volume = _resolve_music_track(content_theme)
    bg_path = os.path.join("assets", "audio", bg_filename)
    bg_path = _maybe_download_bg_music(bg_path, bg_url)
    print(f"[BGMusic] Theme: {content_theme} | Track: {bg_filename} | Volume: {bg_volume}")

    if not bg_path:
        print("[BGMusic] No music available — using narration only.")
        return narration_audio

    try:
        bg_music = AudioFileClip(bg_path)
        # Loop if shorter than the video.
        if bg_music.duration < total_duration:
            loops_needed = int(total_duration / bg_music.duration) + 1
            from moviepy.editor import concatenate_audioclips
            bg_music = concatenate_audioclips([bg_music] * loops_needed)
        bg_music = bg_music.subclip(0, total_duration)
        bg_music = bg_music.volumex(bg_volume)
        mixed = CompositeAudioClip([narration_audio, bg_music])
        return mixed
    except Exception as e:
        print(f"[BGMusic] Could not mix background music: {e}")
        return narration_audio


# ── Scene Duration Helpers ───────────────────────────────────────────

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


# ── Karaoke Dynamic Subtitle Clips ──────────────────────────────────

# Edge TTS WordBoundary events fire slightly before the word is actually
# heard in the rendered audio. This offset (in seconds) delays subtitle
# appearance so the caption and voice land at the exact same moment.
# Tune via env var SUBTITLE_SYNC_OFFSET_MS (default = 80ms).
_SUBTITLE_SYNC_OFFSET = float(os.getenv("SUBTITLE_SYNC_OFFSET_MS", "80")) / 1000.0

def _build_karaoke_subtitle_clips(events, scene_start, scene_duration, words_per_chunk=1):
    """Create karaoke-style rolling subtitle clips with per-word highlighting.
    
    Shows 2-3 words at a time. Each word gets highlighted in sequence while 
    the others stay white — premium viral reel caption style.
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

        chunk_words = [str(item.get('word', '')).strip() for item in chunk]

        # Create a separate clip for each word being highlighted within the chunk
        for word_pos, word_event in enumerate(chunk):
            word_start = float(word_event.get('start', 0.0))
            word_end = float(word_event.get('end', word_start + 0.3))

            # Apply sync offset: Edge TTS WordBoundary events arrive slightly
            # early relative to audible playback. Shift forward so the caption
            # appears exactly when the word is heard, not before.
            synced_start = word_start + _SUBTITLE_SYNC_OFFSET
            synced_end   = word_end   + _SUBTITLE_SYNC_OFFSET

            local_start = max(0.0, synced_start - scene_start)
            local_end = min(scene_duration, max(local_start + 0.15, synced_end - scene_start))

            # If this is the last word in chunk, extend until next chunk starts
            if word_pos == len(chunk) - 1:
                next_chunk_start = None
                if index + words_per_chunk < len(events):
                    next_chunk_start = float(events[index + words_per_chunk].get('start', 0.0)) + _SUBTITLE_SYNC_OFFSET
                    local_end = min(scene_duration, max(local_end, next_chunk_start - scene_start))

            local_duration = max(0.12, local_end - local_start)

            # Render the full chunk text with this word highlighted
            full_chunk = " ".join(chunk_words)
            text_img = create_text_image(
                full_chunk,
                font_size=100,
                highlight_word_index=word_pos,
            )
            txt_clip = (
                ImageClip(text_img)
                .set_start(local_start)
                .set_duration(local_duration)
            )
            clips.append(txt_clip)

        index += words_per_chunk

    return clips


def _build_dynamic_subtitle_clips(events, scene_start, scene_duration, words_per_chunk=1):
    """Backward-compatible wrapper — uses karaoke style."""
    return _build_karaoke_subtitle_clips(events, scene_start, scene_duration, words_per_chunk)


# ── Main Video Assembly ──────────────────────────────────────────────

def generate_thumbnail(title, output_path="output_thumbnail.jpg", size=(1080, 1920)):
    """
    Generate a bold text-on-gradient thumbnail image for the reel cover.
    This is shown as the static preview before anyone taps play.
    """
    title = _strip_unsupported_chars(str(title or "").strip())
    img = Image.new("RGB", size, (10, 10, 20))  # Dark base
    draw = ImageDraw.Draw(img)

    # Gradient background — dark purple to black
    for y in range(size[1]):
        ratio = y / size[1]
        r = int(25 * (1 - ratio))
        g = int(10 * (1 - ratio))
        b = int(60 * (1 - ratio) + 10)
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))

    # Neon accent stripe at top
    draw.rectangle([0, 0, size[0], 12], fill=(0, 220, 120))

    font_large = _load_caption_font(88)
    font_small = _load_caption_font(52)

    # Word-wrap title
    words = title.split()
    lines = []
    current = []
    for word in words:
        current.append(word)
        if draw.textlength(" ".join(current), font=font_large) > size[0] - 120:
            current.pop()
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))

    total_h = len(lines) * 110
    start_y = (size[1] // 2) - (total_h // 2) - 60

    for line in lines:
        w = draw.textlength(line, font=font_large)
        x = (size[0] - w) / 2
        # Shadow
        draw.text((x + 4, start_y + 4), line, font=font_large, fill=(0, 0, 0))
        # White text
        draw.text((x, start_y), line, font=font_large, fill=(255, 255, 255))
        start_y += 110

    # Neon green subtext
    sub = "Psychology Secrets"
    sub_w = draw.textlength(sub, font=font_small)
    draw.text(((size[0] - sub_w) / 2, start_y + 30), sub, font=font_small, fill=(0, 220, 120))

    # Bottom branding
    brand = "@itsun.known6969"
    brand_font = _load_caption_font(44)
    bw = draw.textlength(brand, font=brand_font)
    draw.text(((size[0] - bw) / 2, size[1] - 100), brand, font=brand_font, fill=(180, 180, 180))

    img.save(output_path, "JPEG", quality=95)
    print(f"[Thumbnail] Saved cover thumbnail: {output_path}")
    return output_path


def create_video(scenes, voiceovers, visuals, output_file, word_timeline=None, content_theme="default"):
    """Combines voiceovers and visuals into a final video with karaoke subtitles."""
    clips = []

    # Detect content theme for music selection if not provided
    if content_theme == "default":
        domain = os.getenv("CONTENT_DOMAIN", "")
        content_theme = _detect_content_theme(scenes, domain)
    print(f"Content theme detected: {content_theme}")

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
                subtitle_layers = _build_karaoke_subtitle_clips(
                    scene_word_events[i],
                    scene_starts[i],
                    duration,
                )
            if not subtitle_layers:
                words = str(scene.get('text', '')).replace("\n", " ").split()
                if words:
                    fake_events = []
                    dur_per_word = duration / len(words)
                    for idx, w in enumerate(words):
                        fake_events.append({
                            "word": w,
                            "start": scene_starts[i] + idx * dur_per_word,
                            "end": scene_starts[i] + (idx + 1) * dur_per_word
                        })
                    subtitle_layers = _build_karaoke_subtitle_clips(fake_events, scene_starts[i], duration, words_per_chunk=1)
                else:
                    subtitle_layers = []

            # Hook overlay on first scene (first 2 seconds) — now with fixed Devanagari font
            extra_overlays = []
            if i == 0:
                hook_duration = min(2.0, duration * 0.4)
                hook_overlay = _create_hook_overlay(
                    topic=scene.get("text", ""),
                    duration=hook_duration,
                )
                extra_overlays.append(hook_overlay)

            # CTA overlay on last scene (last 2.5 seconds)
            if i == len(scenes) - 1:
                cta_dur = min(2.5, duration * 0.5)
                cta_overlay = _create_follow_cta(duration=cta_dur).set_start(max(0, duration - cta_dur))
                extra_overlays.append(cta_overlay)

            # Flash transition between scenes (pattern interrupt at cut points)
            if i > 0:
                flash = _create_flash_frame(duration=0.08)
                clips.append(flash)

            video_scene = CompositeVideoClip([clip] + subtitle_layers + extra_overlays)
            clips.append(video_scene)

        print("Concatenating clips...")
        final_video = concatenate_videoclips(clips, method="compose")

        # Add neon progress bar across full video duration (proven watch-time booster)
        total_dur = narration.duration
        try:
            progress_bar = _create_progress_bar_clip(total_dur)
            final_video = CompositeVideoClip([final_video, progress_bar])
            print("[ProgressBar] Neon progress bar added.")
        except Exception as e:
            print(f"[ProgressBar] Warning: could not add progress bar: {e}")

        # Mix theme-appropriate background music under the narration.
        mixed_audio = _mix_background_music(narration, narration.duration, content_theme)
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

        # Generate cover thumbnail from first scene title
        title = scenes[0].get("text", "")[:60] if scenes else ""
        thumb_path = output_file.replace(".mp4", "_thumbnail.jpg")
        try:
            generate_thumbnail(title, output_path=thumb_path)
        except Exception as e:
            print(f"[Thumbnail] Warning: could not generate thumbnail: {e}")

        return output_file
    
    # Legacy per-scene voiceover mode
    for i, scene in enumerate(scenes):
        print(f"Processing clip {i+1}...")
        audio = AudioFileClip(voiceovers[i])
        duration = audio.duration

        clip = _prepare_visual_clip(visuals[i], duration)
        clip = clip.set_audio(audio)
        
        words = str(scene.get('text', '')).replace("\n", " ").split()
        if words:
            fake_events = []
            dur_per_word = duration / len(words)
            for idx, w in enumerate(words):
                fake_events.append({
                    "word": w,
                    "start": idx * dur_per_word,
                    "end": (idx + 1) * dur_per_word
                })
            subtitle_layers = _build_karaoke_subtitle_clips(fake_events, 0.0, duration, words_per_chunk=1)
        else:
            subtitle_layers = []
            
        extra_overlays = []
        if i == 0:
            hook_duration = min(2.0, duration * 0.4)
            hook_overlay = _create_hook_overlay(topic=scene.get("text", ""), duration=hook_duration)
            extra_overlays.append(hook_overlay)
        if i == len(scenes) - 1:
            cta_dur = min(2.5, duration * 0.5)
            cta_overlay = _create_follow_cta(duration=cta_dur).set_start(max(0, duration - cta_dur))
            extra_overlays.append(cta_overlay)

        video_scene = CompositeVideoClip([clip] + subtitle_layers + extra_overlays)
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
