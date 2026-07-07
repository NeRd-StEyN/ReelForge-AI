import os
import math
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


def send_to_make_webhook(
    video_path: str,
    title: str,
    text: str,
    thumbnail_path: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> bool:
    """Send reel URL and caption parts to a Make.com webhook as JSON."""
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
