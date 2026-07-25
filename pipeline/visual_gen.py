import requests
import os
import json
import random
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

_USED_PEXELS_VIDEO_IDS = set()
_USED_PEXELS_IMAGE_IDS = set()

# Persistent blacklist file to avoid repeating visuals across runs
_BLACKLIST_FILE = os.path.join("data", "pexels_used_ids.json")


def _load_persistent_blacklist():
    """Load previously used Pexels IDs from disk to avoid visual repetition."""
    global _USED_PEXELS_VIDEO_IDS, _USED_PEXELS_IMAGE_IDS
    try:
        if os.path.exists(_BLACKLIST_FILE):
            with open(_BLACKLIST_FILE, "r") as f:
                data = json.load(f)
            _USED_PEXELS_VIDEO_IDS.update(data.get("video_ids", []))
            _USED_PEXELS_IMAGE_IDS.update(data.get("image_ids", []))
    except Exception:
        pass


def _save_persistent_blacklist():
    """Save used Pexels IDs to disk for cross-run deduplication."""
    try:
        os.makedirs(os.path.dirname(_BLACKLIST_FILE), exist_ok=True)
        # Keep only the last 500 IDs to prevent the list from growing forever
        video_ids = list(_USED_PEXELS_VIDEO_IDS)[-500:]
        image_ids = list(_USED_PEXELS_IMAGE_IDS)[-500:]
        with open(_BLACKLIST_FILE, "w") as f:
            json.dump({"video_ids": video_ids, "image_ids": image_ids}, f)
    except Exception:
        pass


# Load blacklist on module import
_load_persistent_blacklist()


# ── Diverse visual fallback queries strictly anchored to niche aesthetics ──────────
# All queries are anchored to close-up portraits, eye contact, moody lighting, and subtle facial expressions
_DIVERSE_FALLBACK_QUERIES = [
    # Eye contact & intense glances
    "intense eye contact woman portrait close up cinematic",
    "woman looking at camera dramatic eyes portrait moody",
    "close up woman eyes intense glance cinematic portrait",
    # Warm/golden attraction mood
    "confident woman subtle smile camera golden hour portrait",
    "attractive woman sunset beach eye contact cinematic",
    "woman close up face warm light aesthetic portrait",
    # Cool/neon suspense mood
    "mysterious woman neon lighting close up eyes cinematic",
    "attractive woman dark moody shadow eye contact portrait",
    "girl subtle glance club neon lighting slow motion",
    # Dark/dramatic psychology mood
    "woman silhouette intense eyes dramatic lighting portrait",
    "mysterious woman dark background spotlight close up",
    "woman moody rain lighting face portrait cinematic",
    # Elegant/subtle mood
    "elegant woman fashion studio lighting close up face",
    "woman luxury aesthetic subtle glance cinematic",
    "model intense gaze dramatic lighting portrait",
]

# Mood-specific visual modifiers for deep emotional alignment
_MOOD_MODIFIERS = {
    "mysterious": ["intense glance dark lighting", "mysterious shadows close up", "dim blue eyes portrait", "fog atmosphere face"],
    "confident": ["direct eye contact camera", "golden hour gaze", "confident smile close up", "urban street portrait"],
    "dramatic": ["dramatic spotlight eyes", "high contrast face", "rain cinematic glance", "silhouette eyes backlit"],
    "warm": ["golden hour smile", "warm tones gaze", "intimate eye contact", "candlelight close up face"],
    "dark": ["dark moody eyes", "shadow play portrait", "night neon gaze", "low key lighting face"],
    "energetic": ["intense gaze dynamic", "fast zoom eye contact", "vibrant colors portrait"],
    "elegant": ["studio lighting face", "luxury aesthetic glance", "fashion editorial eyes", "minimalist portrait"],
    "neutral": ["cinematic eye contact", "soft lighting close up", "aesthetic portrait gaze", "clean face composition"],
}

# Words that indicate completely off-topic stock footage (must be stripped)
_OFF_TOPIC_BLACKLIST = [
    "prosthetic", "balloon", "party", "hospital", "office", "laptop",
    "sports", "group", "gym", "workout", "abandoned", "zombie", "monster"
]


def _build_realistic_query(query, visual_mood="neutral", scene_index=0):
    """Build a realistic, highly relevant stock search query anchored to face & eye aesthetics."""
    base = " ".join(str(query or "").split()).lower()

    # Remove off-topic blacklisted words
    for bad_word in _OFF_TOPIC_BLACKLIST:
        if bad_word in base:
            base = base.replace(bad_word, "").strip()

    # Remove cartoon/anime/illustration terms
    for remove_term in ["cartoon", "anime", "illustration", "drawing", "sketch"]:
        if remove_term in base:
            base = base.replace(remove_term, "").strip()

    if not base:
        return random.choice(_DIVERSE_FALLBACK_QUERIES)

    # Ensure query has explicit face/eye/portrait anchors for Niche Relevance
    has_anchor = any(w in base for w in ["eye", "face", "portrait", "glance", "gaze", "close up", "looking"])
    if not has_anchor:
        base = f"{base} close up face portrait"

    has_person = any(w in base for w in ["woman", "girl", "female", "lady", "model", "man", "person"])
    if not has_person:
        base = f"woman {base}"

    # Add mood-specific modifiers for visual variety
    mood_mods = _MOOD_MODIFIERS.get(visual_mood, _MOOD_MODIFIERS["neutral"])
    selected_mod = random.choice(mood_mods)

    # Color bias per scene to keep sequence visually distinct
    color_variety = ["", "warm tones", "cool tones", "high contrast", "soft light"][scene_index % 5]

    return f"{base} {selected_mod} {color_variety} cinematic".strip()


def _pick_diverse_pexels_item(items, used_ids):
    """Prefer unseen assets first, then fall back to any item if exhausted."""
    unseen = [item for item in items if item.get("id") not in used_ids]
    pool = unseen if unseen else items
    if not pool:
        return None
    choice = random.choice(pool)
    item_id = choice.get("id")
    if item_id is not None:
        used_ids.add(item_id)
        _save_persistent_blacklist()  # Persist after each pick
    return choice

def _try_fetch_pexels_video(search_query, output_path, headers):
    """Internal helper: attempt to fetch a video for a single search query."""
    for page in random.sample([1, 2, 3, 4, 5], 3):
        url = f"https://api.pexels.com/videos/search?query={search_query}&per_page=15&page={page}&orientation=portrait&size=large"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            continue

        data = response.json()
        if data.get('total_results', 0) <= 0:
            continue

        picked_video = _pick_diverse_pexels_item(data.get('videos', []), _USED_PEXELS_VIDEO_IDS)
        if not picked_video:
            continue

        video_files = picked_video.get('video_files', [])
        if not video_files:
            continue

        # Find the highest resolution video (often HD/4K)
        best_video = max(video_files, key=lambda v: (v.get('width', 0) or 0) * (v.get('height', 0) or 0))
        video_url = best_video['link']
        # Download the video
        video_data = requests.get(video_url).content
        with open(output_path, 'wb') as f:
            f.write(video_data)
        return output_path
    return None


def fetch_pexels_video(query, output_path, visual_mood="neutral", scene_index=0):
    """Fetches a stock video from Pexels with mood-aware diversity. Falls back to varied queries."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found. Skipping video fetch.")
        return None
    
    headers = {"Authorization": api_key}
    search_query = _build_realistic_query(query, visual_mood, scene_index)
    print(f"  Pexels video search: '{search_query}' (mood: {visual_mood})")

    # Try primary query first
    result = _try_fetch_pexels_video(search_query, output_path, headers)
    if result:
        return result

    # Fallback: try 2 random diverse queries (mood-filtered if possible)
    mood_filtered = [q for q in _DIVERSE_FALLBACK_QUERIES if any(m in q.lower() for m in _MOOD_MODIFIERS.get(visual_mood, ["cinematic"]))]
    fallback_pool = mood_filtered if mood_filtered else _DIVERSE_FALLBACK_QUERIES
    for fallback_q in random.sample(fallback_pool, min(2, len(fallback_pool))):
        print(f"  Primary video query failed. Retrying with fallback: '{fallback_q}'")
        result = _try_fetch_pexels_video(fallback_q, output_path, headers)
        if result:
            return result

    return None

def _try_fetch_pexels_image(search_query, output_path, headers):
    """Internal helper: attempt to fetch an image for a single search query."""
    for page in random.sample([1, 2, 3, 4, 5], 3):
        url = f"https://api.pexels.com/v1/search?query={search_query}&per_page=15&page={page}&orientation=portrait"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            continue

        data = response.json()
        if data.get('total_results', 0) <= 0:
            continue

        picked_photo = _pick_diverse_pexels_item(data.get('photos', []), _USED_PEXELS_IMAGE_IDS)
        if not picked_photo:
            continue

        image_url = picked_photo['src']['large']
        image_data = requests.get(image_url).content
        with open(output_path, 'wb') as f:
            f.write(image_data)
        return output_path
    return None


def fetch_pexels_image(query, output_path, visual_mood="neutral", scene_index=0):
    """Fetches a stock image from Pexels with mood-aware diversity."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found. Skipping image fetch.")
        return None
    
    headers = {"Authorization": api_key}
    search_query = _build_realistic_query(query, visual_mood, scene_index)
    print(f"  Pexels image search: '{search_query}' (mood: {visual_mood})")

    # Try primary query first
    result = _try_fetch_pexels_image(search_query, output_path, headers)
    if result:
        return result

    # Fallback: try 2 random diverse queries
    mood_filtered = [q for q in _DIVERSE_FALLBACK_QUERIES if any(m in q.lower() for m in _MOOD_MODIFIERS.get(visual_mood, ["cinematic"]))]
    fallback_pool = mood_filtered if mood_filtered else _DIVERSE_FALLBACK_QUERIES
    for fallback_q in random.sample(fallback_pool, min(2, len(fallback_pool))):
        print(f"  Primary image query failed. Retrying with fallback: '{fallback_q}'")
        result = _try_fetch_pexels_image(fallback_q, output_path, headers)
        if result:
            return result

    return None

def create_placeholder_image(output_path, text="Visual Placeholder"):
    """Creates a simple placeholder image."""
    img = Image.new('RGB', (1080, 1920), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    # Using default font for portability in this snippet
    d.text((400, 960), text, fill=(255, 255, 255))
    img.save(output_path)
    return output_path
