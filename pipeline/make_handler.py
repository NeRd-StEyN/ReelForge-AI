import json
import math
import os
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# Pending posts file — survives across GitHub Actions runs via cache
PENDING_POSTS_FILE = os.path.join("data", "pending_posts.jsonl")


def _safe_text(value, fallback: str = "") -> str:
    """Return clean text and guard against None/NaN values from upstream systems."""
    if value is None:
        return fallback
    if isinstance(value, float) and math.isnan(value):
        return fallback
    text = str(value).strip()
    if text.lower() == "nan":
        return fallback
    return text


# ---------------------------------------------------------------------------
# Pending posts — save / load / retry
# ---------------------------------------------------------------------------

def _save_pending_post(payload: dict) -> None:
    """Save a failed webhook payload to pending_posts.jsonl for retry on next run."""
    try:
        os.makedirs("data", exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
            "attempts": 1,
            "status": "pending",
        }
        with open(PENDING_POSTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[Pending] Reel saved to {PENDING_POSTS_FILE} — will retry on next run.")
    except Exception as exc:
        print(f"[Pending] Could not save pending post: {exc}")


def _load_all_pending() -> list:
    """Load all entries from pending_posts.jsonl (pending + sent)."""
    if not os.path.exists(PENDING_POSTS_FILE):
        return []
    entries = []
    with open(PENDING_POSTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _rewrite_pending_file(entries: list) -> None:
    """Rewrite the pending posts file with the given entries."""
    try:
        os.makedirs("data", exist_ok=True)
        with open(PENDING_POSTS_FILE, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        print(f"[Pending] Could not rewrite pending posts file: {exc}")


def _post_payload_to_make(payload: dict) -> bool:
    """Send a pre-built payload dict to the Make.com webhook. Returns True on success."""
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    if not webhook_url:
        print("[Pending] MAKE_WEBHOOK_URL not set — cannot retry.")
        return False
    try:
        response = requests.post(webhook_url, json=payload, timeout=60)
        if 200 <= response.status_code < 300:
            return True
        print(f"[Pending] Webhook returned {response.status_code}: {response.text}")
        return False
    except Exception as exc:
        print(f"[Pending] Webhook request failed: {exc}")
        return False


def retry_pending_posts() -> int:
    """
    Retry all pending posts at the start of a new pipeline run.
    Returns the number of posts successfully retried and posted.
    """
    all_entries = _load_all_pending()
    pending = [e for e in all_entries if e.get("status") == "pending"]

    if not pending:
        print("[Pending] No pending posts to retry.")
        return 0

    print(f"[Pending] Found {len(pending)} pending post(s) — retrying now...")
    retried_ok = 0

    for entry in all_entries:
        if entry.get("status") != "pending":
            continue

        entry["attempts"] = entry.get("attempts", 1) + 1
        payload = entry.get("payload", {})
        video_url = payload.get("url", "(unknown)")
        print(f"[Pending] Retrying post: {video_url[:80]}...")

        if _post_payload_to_make(payload):
            entry["status"] = "sent"
            entry["sent_at"] = datetime.now().isoformat()
            print(f"[Pending] ✅ Retry succeeded — reel posted to Instagram.")
            retried_ok += 1
        else:
            print(f"[Pending] ❌ Retry failed again — will try on next run.")

    _rewrite_pending_file(all_entries)
    return retried_ok


# ---------------------------------------------------------------------------
# Cloudinary upload
# ---------------------------------------------------------------------------

def upload_file_to_cloudinary(file_path: str) -> Optional[str]:
    """Upload a local MP4 or image to Cloudinary and return a publicly reachable direct URL."""
    if not os.path.exists(file_path):
        print(f"Upload skipped: file not found -> {file_path}")
        return None

    try:
        print(f"Uploading {file_path} to Cloudinary...")
        response = cloudinary.uploader.upload(
            file_path,
            resource_type="auto",
        )
        url = response.get("secure_url") or response.get("url")
        if not url:
            print("Cloudinary upload failed: missing URL in response")
            return None
        print(f"Cloudinary upload successful -> {url}")
        return url
    except Exception as exc:
        print(f"Cloudinary upload failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main webhook sender
# ---------------------------------------------------------------------------

def send_to_make_webhook(
    video_path: str,
    title: str,
    text: str,
    thumbnail_path: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> bool:
    """Send reel URL and caption parts to a Make.com webhook as JSON.
    
    If the webhook call fails AFTER a successful Cloudinary upload, the full
    payload is saved to data/pending_posts.jsonl so it can be retried on the
    next pipeline run — meaning no generated reel is ever silently lost.
    """
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")

    if not webhook_url:
        print("Upload skipped: MAKE_WEBHOOK_URL not found in .env")
        return False

    try:
        print("Preparing public video URL for Make.com webhook...")
        video_url = upload_file_to_cloudinary(video_path)
        if not video_url:
            return False

        cover_url = None
        if thumbnail_path and os.path.exists(thumbnail_path):
            print("Preparing public thumbnail URL for Make.com webhook...")
            cover_url = upload_file_to_cloudinary(thumbnail_path)

        safe_title = _safe_text(title, "AI Video")
        safe_text = _safe_text(text, "")
        caption = f"{safe_title}\n\n{safe_text}".strip()
        metadata = metadata if isinstance(metadata, dict) else {}
        hashtags = metadata.get("hashtags") or []
        first_comment = _safe_text(metadata.get("first_comment"), "")

        payload = {
            "url": video_url,
            "modifications": {
                "Subtitles": safe_title,
            },
            "text": safe_text,
            "caption": caption,
            "title": safe_title,
            # Story posting: tell Make.com to also post the thumbnail as a Story
            "post_story": True,
        }

        if cover_url:
            payload["cover_url"] = cover_url
        else:
            # Story posting requires a cover image — warn if missing
            print("[Make] [WARN] No cover_url available -- Make.com will skip Story posting.")
            payload["post_story"] = False

        if hashtags:
            payload["hashtags"] = hashtags

        if first_comment:
            payload["first_comment"] = first_comment

        hook_framework = _safe_text(metadata.get("hook_framework"), "")
        if hook_framework:
            payload["hook_framework"] = hook_framework

        # Send story poll data so Make.com can post the story on our behalf
        # (instagrapi cannot work from GitHub Actions cloud IPs)
        story_poll = metadata.get("story_poll")
        if isinstance(story_poll, dict) and story_poll.get("question"):
            payload["story_poll"] = story_poll

        print("Sending JSON payload to Make.com webhook...")
        response = requests.post(webhook_url, json=payload, timeout=60)

        if 200 <= response.status_code < 300:
            print("Success! Reel payload sent to Make.com.")
            return True

        print(
            f"Make.com webhook failed with status code {response.status_code}: {response.text}"
        )
        # ✅ Save to pending so next run can retry with the already-uploaded Cloudinary URL
        print("[Pending] Saving payload for retry on next run...")
        _save_pending_post(payload)
        return False

    except Exception as exc:
        print(f"Failed to post to Make.com: {exc}")
        # If we got a video_url before the crash, try to save it
        try:
            if "payload" in dir() and payload.get("url"):
                _save_pending_post(payload)
        except Exception:
            pass
        return False


def fetch_analytics_from_make() -> Optional[list]:
    """Fetch Instagram post insights from Make.com webhook.

    Executes only once per run (no retries) to strictly conserve Make.com operations.
    If it fails, it will safely fall back to local historical data.

    The response from Make.com may be:
      - A plain JSON array of media objects  →  used directly
      - A JSON object with a nested list     →  auto-extracted
    Both formats are handled.
    """
    import time as _time

    webhook_url = os.getenv("MAKE_ANALYTICS_WEBHOOK_URL")
    if not webhook_url:
        print("[Analytics] MAKE_ANALYTICS_WEBHOOK_URL not set — skipping Make.com analytics fetch.")
        print("[Analytics] To fix: Create an analytics scenario in Make.com and add the webhook URL")
        print("[Analytics]   to your .env / GitHub Secrets as MAKE_ANALYTICS_WEBHOOK_URL.")
        return None

    try:
        print("[Analytics] Fetching live performance data via Make.com (single attempt)...")
        response = requests.get(webhook_url, timeout=60)

        if 200 <= response.status_code < 300:
            # Check if it's the default Make.com "Accepted" response instead of JSON
            if "application/json" not in response.headers.get("Content-Type", "") or response.text.strip() == "Accepted":
                print("[Analytics] ❌ CRITICAL ERROR: Your Make.com scenario is missing a 'Webhook Response' module!")
                print("[Analytics] Make.com received the trigger, but returned plain text ('Accepted') instead of JSON data.")
                print("[Analytics] FIX: Add a 'Webhook Response' module at the end of your Make.com scenario and return the JSON array.")
                return None

            data = response.json()

            # Handle both list and dict-with-nested-list responses
            if isinstance(data, dict):
                # Make.com sometimes wraps results: {"data": [...]} or {"items": [...]}
                for key in ("data", "items", "results", "media"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
                else:
                    # Single-item dict — wrap it
                    data = [data]

            if isinstance(data, list):
                # Normalize field names — Make.com may return Graph API field names
                normalized = _normalize_analytics(data)
                print(f"[Analytics] [OK] Successfully fetched {len(normalized)} items from Make.com.")
                return normalized

            print(f"[Analytics] Make.com returned unexpected format: {type(data)}")
            # If format is totally wrong, don't retry and waste credits
            return None

        elif response.status_code == 429:
            print("[Analytics] Rate limited by Make.com (429).")
        else:
            print(f"[Analytics] Make.com webhook returned {response.status_code}: {response.text[:200]}")

    except requests.exceptions.Timeout:
        print("[Analytics] Request timed out.")
    except Exception as exc:
        print(f"[Analytics] Request failed: {exc}")

    print("[Analytics] [FAIL] Make.com fetch failed. Will use saved history.")
    return None


def _normalize_analytics(data: list) -> list:
    """Normalize Make.com / Graph API response to the format expected by feedback_loop.py.

    Make.com returns one entry *per metric per post*, e.g.:
        [
            {"id": "123", "name": "views",    "values": [{"value": 88}], "caption": "...", ...},
            {"id": "123", "name": "likes",    "values": [{"value": 5}],  "caption": "...", ...},
            {"id": "456", "name": "views",    "values": [{"value": 200}], ...},
            ...
        ]

    We group by post ID and merge all metrics into one dict per post with
    the simple keys that feedback_loop.py expects: views, likes, comments.
    """
    # Group entries by post ID
    posts = {}  # id -> {views, likes, comments, caption, ...}
    for item in data:
        if not isinstance(item, dict):
            continue

        post_id = str(item.get("id") or item.get("post_id") or "")
        if not post_id:
            continue

        if post_id not in posts:
            # Extract caption snippet from any entry for this post
            caption = (
                item.get("caption")
                or item.get("topic_snippet")
                or item.get("text")
                or ""
            )
            if isinstance(caption, str):
                caption = caption[:120].replace("\n", " ").strip()
                # Strip non-ASCII chars to prevent Windows cp1252 encoding crashes
                caption = caption.encode("ascii", errors="ignore").decode("ascii").strip()

            posts[post_id] = {
                "topic_snippet": caption,
                "views": 0,
                "likes": int(item.get("like_count") or 0),
                "comments": int(item.get("comments_count") or 0),
            }

        # Extract metric value from the "name" + "values" structure
        metric_name = str(item.get("name") or "").lower().strip()
        metric_values = item.get("values")
        if isinstance(metric_values, list) and metric_values:
            try:
                metric_value = int(metric_values[0].get("value", 0))
            except (ValueError, TypeError, AttributeError):
                metric_value = 0
        else:
            metric_value = 0

        # Map metric names to our simple keys
        if metric_name in ("views", "total_views", "ig_reels_video_view_total_count", "impressions"):
            posts[post_id]["views"] = max(posts[post_id]["views"], metric_value)
        elif metric_name in ("likes", "total_likes"):
            posts[post_id]["likes"] = max(posts[post_id]["likes"], metric_value)
        elif metric_name in ("comments", "total_comments"):
            posts[post_id]["comments"] = max(posts[post_id]["comments"], metric_value)

    # If the data was already in simple format (not per-metric), handle that too
    if not posts:
        for item in data:
            if not isinstance(item, dict):
                continue
            views = (
                item.get("views") or item.get("plays")
                or item.get("video_views") or item.get("impressions") or 0
            )
            likes = item.get("likes") or item.get("like_count") or 0
            comments = item.get("comments") or item.get("comment_count") or 0
            caption = (
                item.get("topic_snippet") or item.get("caption")
                or item.get("text") or ""
            )
            if isinstance(caption, str):
                caption = caption[:120].replace("\n", " ").strip()
                # Strip non-ASCII chars to prevent Windows cp1252 encoding crashes
                caption = caption.encode("ascii", errors="ignore").decode("ascii").strip()
            try:
                posts[str(id(item))] = {
                    "topic_snippet": caption,
                    "views": int(views),
                    "likes": int(likes),
                    "comments": int(comments),
                }
            except (ValueError, TypeError):
                continue

    return list(posts.values())


def check_make_webhook_health() -> dict:
    """Quick health-check: verify the Make.com webhook is reachable and the
    Instagram OAuth connection is alive.

    Returns a dict with 'healthy' (bool) and 'message' (str).
    Call this before/after posting to detect OAuth expiry early.
    """
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    analytics_url = os.getenv("MAKE_ANALYTICS_WEBHOOK_URL")

    status = {"healthy": True, "message": "All systems operational.", "details": {}}

    # Check reel webhook reachability
    if not webhook_url:
        status["healthy"] = False
        status["message"] = "MAKE_WEBHOOK_URL not configured."
        return status

    # Check analytics webhook
    if not analytics_url:
        status["details"]["analytics"] = "MAKE_ANALYTICS_WEBHOOK_URL not set — feedback loop disabled."
    else:
        try:
            resp = requests.get(analytics_url, timeout=15)
            if 200 <= resp.status_code < 300:
                status["details"]["analytics"] = "[OK] Analytics webhook responding."
            else:
                status["details"]["analytics"] = f"[WARN] Analytics webhook returned {resp.status_code}"
                # If analytics returns OAuth error text, flag it
                body = resp.text.lower()
                if "oauth" in body or "token" in body or "expired" in body:
                    status["healthy"] = False
                    status["message"] = "Instagram OAuth token may be expired. Reauthorize in Make.com."
        except Exception as exc:
            status["details"]["analytics"] = f"[FAIL] Analytics webhook unreachable: {exc}"

    return status
