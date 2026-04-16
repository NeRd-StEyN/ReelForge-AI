import os
import math
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()


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


def upload_video_to_tmpfiles(video_path: str) -> Optional[str]:
    """Upload a local MP4 to tmpfiles and return a publicly reachable direct URL."""
    if not os.path.exists(video_path):
        print(f"Upload skipped: file not found -> {video_path}")
        return None

    try:
        with open(video_path, "rb") as video_file:
            response = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": video_file},
                timeout=180,
            )
        response.raise_for_status()
        data = response.json()

        page_url = data.get("data", {}).get("url")
        if not page_url:
            print("tmpfiles upload failed: missing URL in response")
            return None

        # Convert share page URL into direct download URL required by Make/Instagram.
        return page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except Exception as exc:
        print(f"tmpfiles upload failed: {exc}")
        return None


def send_to_make_webhook(video_path: str, title: str, text: str) -> bool:
    """Send reel URL and caption parts to a Make.com webhook as JSON."""
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")

    if not webhook_url:
        print("Upload skipped: MAKE_WEBHOOK_URL not found in .env")
        return False

    try:
        print("Preparing public video URL for Make.com webhook...")
        video_url = upload_video_to_tmpfiles(video_path)
        if not video_url:
            return False

        safe_title = _safe_text(title, "AI Video")
        safe_text = _safe_text(text, "")
        caption = f"{safe_title}\n\n{safe_text}".strip()

        payload = {
            "url": video_url,
            "modifications": {
                "Subtitles": safe_title,
            },
            "text": safe_text,
            "caption": caption,
        }

        print("Sending JSON payload to Make.com webhook...")
        response = requests.post(webhook_url, json=payload, timeout=60)

        if 200 <= response.status_code < 300:
            print("Success! Reel payload sent to Make.com.")
            return True

        print(
            f"Make.com webhook failed with status code {response.status_code}: {response.text}"
        )
        return False
    except Exception as exc:
        print(f"Failed to post to Make.com: {exc}")
        return False
