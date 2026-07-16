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
        }

        if cover_url:
            payload["cover_url"] = cover_url

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
    """Fetch Instagram post insights from Make.com webhook."""
    webhook_url = os.getenv("MAKE_ANALYTICS_WEBHOOK_URL")
    if not webhook_url:
        print("[Analytics] MAKE_ANALYTICS_WEBHOOK_URL not set — skipping Make.com analytics fetch.")
        return None

    try:
        print(f"[Analytics] Fetching live performance data via Make.com webhook...")
        response = requests.get(webhook_url, timeout=60)
        
        if 200 <= response.status_code < 300:
            data = response.json()
            if isinstance(data, list):
                print(f"[Analytics] Successfully fetched {len(data)} items from Make.com.")
                return data
            else:
                print(f"[Analytics] Make.com returned invalid format (expected list): {type(data)}")
                return None
                
        print(f"[Analytics] Make.com webhook failed with status code {response.status_code}: {response.text}")
        return None
    except Exception as exc:
        print(f"[Analytics] Failed to fetch analytics from Make.com: {exc}")
        return None
