import requests
import os
import random
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

_USED_PEXELS_VIDEO_IDS = set()
_USED_PEXELS_IMAGE_IDS = set()

# Bold Pexels search terms that return eye-catching attractive woman clips.
# Used as fallbacks when the AI-generated visual_keyword returns zero results.
_GIRL_FALLBACK_QUERIES = [
    "sexy woman dancing slow motion",
    "hot girl bikini beach cinematic",
    "attractive model lingerie photoshoot",
    "sexy girl dance moves aesthetic",
    "beautiful woman body fitness gym",
    "hot indian girl dancing bollywood",
    "sexy woman pool summer cinematic",
    "attractive girl lip bite close up",
    "woman dancing club neon lights",
    "hot model fashion runway slow motion",
    "sexy girl twerking dance party",
    "beautiful woman shower water cinematic",
    "attractive woman bedroom morning aesthetic",
    "hot girl car lifestyle luxury",
    "sexy dancer woman body movement",
]


def _build_realistic_query(query):
    """Bias stock search toward beautiful woman/girl footage with cinematic quality."""
    base = " ".join(str(query or "").split())
    # Quality tokens without over-constraining — Pexels handles natural language well.
    quality_tokens = "cinematic beautiful aesthetic"
    if not base:
        return random.choice(_GIRL_FALLBACK_QUERIES)
    lowered = base.lower()
    if "cartoon" in lowered or "anime" in lowered or "illustration" in lowered:
        base = base.replace("cartoon", "").replace("anime", "").replace("illustration", "")
    # If the query already mentions woman/girl/female/lady, just add quality tokens.
    # Otherwise inject "beautiful woman" to guarantee girl-focused results.
    has_girl_term = any(w in lowered for w in ["woman", "girl", "female", "lady", "model", "couple"])
    if not has_girl_term:
        base = f"{base} beautiful woman"
    return f"{base} {quality_tokens}".strip()


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


def fetch_pexels_video(query, output_path):
    """Fetches a stock video from Pexels. Falls back to beautiful-girl queries if primary fails."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found. Skipping video fetch.")
        return None
    
    headers = {"Authorization": api_key}
    search_query = _build_realistic_query(query)

    # Try primary query first
    result = _try_fetch_pexels_video(search_query, output_path, headers)
    if result:
        return result

    # Fallback: try 2 random proven beautiful-girl queries
    for fallback_q in random.sample(_GIRL_FALLBACK_QUERIES, min(2, len(_GIRL_FALLBACK_QUERIES))):
        print(f"Primary video query failed. Retrying with fallback: '{fallback_q}'")
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


def fetch_pexels_image(query, output_path):
    """Fetches a stock image from Pexels. Falls back to beautiful-girl queries if primary fails."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found. Skipping image fetch.")
        return None
    
    headers = {"Authorization": api_key}
    search_query = _build_realistic_query(query)

    # Try primary query first
    result = _try_fetch_pexels_image(search_query, output_path, headers)
    if result:
        return result

    # Fallback: try 2 random proven beautiful-girl queries
    for fallback_q in random.sample(_GIRL_FALLBACK_QUERIES, min(2, len(_GIRL_FALLBACK_QUERIES))):
        print(f"Primary image query failed. Retrying with fallback: '{fallback_q}'")
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
