import os
from instagrapi import Client


def get_insta_client():
    """Logs into Instagram and returns the client using session persistence."""
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    sessionid_cookie = os.getenv("INSTA_SESSION_ID")

    if not username:
        print("[Analytics] WARNING: INSTA_USERNAME missing in .env — skipping analytics.")
        return None

    cl = Client()

    try:
        if sessionid_cookie:
            print(f"[Analytics] Logging in via session cookie for @{username}...")
            cl.login_by_sessionid(sessionid_cookie)
            print("[Analytics] Session cookie login successful.")
            return cl

        if os.path.exists("insta_session.json"):
            print(f"[Analytics] Loading saved session file for @{username}...")
            cl.load_settings("insta_session.json")
            print("[Analytics] Session file loaded.")
            return cl

        print(f"[Analytics] Attempting password login for @{username} (may be blocked on cloud)...")
        cl.login(username, password)
        print("[Analytics] Password login successful.")
        return cl

    except Exception as e:
        print(f"[Analytics] LOGIN FAILED for @{username}: {e}")
        print("[Analytics] Will fall back to saved history for feedback. No live data this run.")
        return None


def get_performance_data(cl):
    """Fetches views and likes for the last 7 reels. Returns a list or None."""
    if not cl:
        print("[Analytics] Skipping live fetch — not logged in.")
        return None

    try:
        print("[Analytics] Fetching recent reel performance data...")
        username = os.getenv("INSTA_USERNAME")
        user_id = cl.user_id_from_username(username)
        recent_posts = cl.user_medias(user_id, amount=10)

        analytics = []
        for post in recent_posts:
            # Only count Reels (media_type=2, product_type='clips')
            if post.media_type == 2 and post.product_type == "clips":
                analytics.append({
                    "topic_snippet": (post.caption_text or "")[:120].replace("\n", " ").strip(),
                    "views": post.view_count or 0,
                    "likes": post.like_count or 0,
                })

        if not analytics:
            print("[Analytics] No Reels found on the account yet.")
            return None

        print(f"[Analytics] Fetched data for {len(analytics)} reels.")
        return analytics

    except Exception as e:
        print(f"[Analytics] ERROR fetching performance data: {e}")
        return None


def post_video(cl, video_path, caption):
    """Uploads the finalized MP4 to Instagram Reels."""
    if not cl:
        print("Upload skipped (Not logged in).")
        return False

    try:
        print("Uploading Reel to Instagram (this usually takes 1-2 minutes)...")
        cl.clip_upload(video_path, caption)
        print("Success! Reel posted to Instagram.")
        return True
    except Exception as e:
        print(f"Upload Failed: {e}")
        return False
