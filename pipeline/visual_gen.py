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


# ── Diverse visual fallback queries with mood/color variety ──────────
# Each entry has a different visual mood to prevent same-looking thumbnails
_DIVERSE_FALLBACK_QUERIES = [
    # Warm/golden mood
    "woman walking golden hour city street cinematic",
    "beautiful woman sunset beach golden light portrait",
    "confident woman cafe window warm light aesthetic",
    # Cool/neon mood
    "woman neon lights city night cinematic portrait",
    "attractive woman dark moody blue lighting portrait",
    "girl dancing club neon purple lights slow motion",
    # Natural/bright mood
    "beautiful woman garden flowers natural light portrait",
    "woman laughing bright daylight outdoor candid",
    "girl running through field bright sun cinematic",
    # Dark/dramatic mood
    "woman silhouette dramatic lighting studio portrait",
    "mysterious woman dark background spotlight cinematic",
    "woman rain night street moody cinematic slow motion",
    # Horror/Mystery mood
    "creepy abandoned hospital dark hallway cinematic",
    "misty dark forest night scary slow motion",
    "shadowy figure standing in dark room cinematic",
    "old cursed house vintage footage aesthetic",
    "unsolved mystery crime scene tape dark moody",
    # Elegant/luxury mood
    "elegant woman fashion photoshoot studio lighting",
    "woman luxury car lifestyle cinematic golden",
    "model walking runway slow motion dramatic lighting",
    # Energetic/action mood
    "woman dancing energetic movement colorful background",
    "fit woman gym workout cinematic slow motion",
    "woman spinning dress wind movement aesthetic",
]

# Mood-specific visual modifiers to inject variety into AI-generated keywords
_MOOD_MODIFIERS = {
    "mysterious": ["moody dark lighting", "mysterious shadows", "dim blue tones", "fog atmosphere"],
    "confident": ["bright natural light", "golden hour warm", "strong pose cinematic", "urban street style"],
    "dramatic": ["dramatic spotlight", "high contrast", "rain cinematic", "silhouette backlit"],
    "warm": ["golden hour", "warm tones sunset", "cozy aesthetic lighting", "candlelight intimate"],
    "dark": ["dark moody", "shadow play", "night neon", "low key lighting"],
    "horror": ["creepy fog", "abandoned dark", "scary shadow", "horror cinematic", "haunted house lighting"],
    "energetic": ["vibrant colors", "dynamic movement", "fast paced", "colorful neon"],
    "elegant": ["studio lighting", "luxury aesthetic", "fashion editorial", "minimalist clean"],
    "neutral": ["cinematic natural", "soft lighting", "aesthetic portrait", "clean composition"],
}


def _build_realistic_query(query, visual_mood="neutral", scene_index=0):
    """Build a diverse stock search query with mood-aware modifiers."""
    base = " ".join(str(query or "").split())

    if not base:
        return random.choice(_DIVERSE_FALLBACK_QUERIES)

    lowered = base.lower()

    # Remove cartoon/anime/illustration terms
    for remove_term in ["cartoon", "anime", "illustration", "drawing", "sketch"]:
        if remove_term in lowered:
            base = base.replace(remove_term, "").strip()
            lowered = base.lower()

    # Ensure we have people-related terms
    has_person_term = any(w in lowered for w in ["woman", "girl", "female", "lady", "model", "couple", "man", "person", "people"])
    if not has_person_term:
        base = f"{base} woman portrait"

    # Add mood-specific modifiers for visual variety
    mood_mods = _MOOD_MODIFIERS.get(visual_mood, _MOOD_MODIFIERS["neutral"])
    selected_mod = random.choice(mood_mods)

    # Add scene-index-based color bias to prevent same-looking consecutive scenes
    color_variety = ["", "warm tones", "cool tones", "high contrast", "soft pastel"][scene_index % 5]

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
