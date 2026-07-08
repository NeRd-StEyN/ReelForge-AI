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
                    # Saves and comments are the highest-weight algorithm signals
                    # Instagram weights: saves (5x) > comments (3x) > likes (1x) > views (0.1x)
                    "comments": post.comment_count or 0,
                    "saves": getattr(post, "saved_count", None) or 0,
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


def _title_match_score(expected_title, caption_text):
    """
    Fuzzy title match: strips punctuation, splits into words, returns the
    fraction of title words found in the caption (0.0 – 1.0).
    A score >= 0.6 is considered a match so emoji/reordering/truncation
    by Make.com doesn't silently break story posting.
    """
    import re
    def _clean(text):
        return re.sub(r"[^\w\s]", " ", text.lower()).split()

    title_words = _clean(expected_title)
    caption_words = set(_clean(caption_text))

    if not title_words:
        return 0.0

    hits = sum(1 for w in title_words if w in caption_words)
    return hits / len(title_words)


def _share_reel_to_story(cl, post, thumbnail_path):
    """Attempt to share a reel post to story. Returns True on success."""
    try:
        if thumbnail_path and os.path.exists(thumbnail_path):
            cl.media_share_to_story(post.pk, background=thumbnail_path)
        else:
            cl.media_share_to_story(post.pk)
        print("[Story] Successfully posted Story promotion! 🚀")
        return True
    except Exception as story_exc:
        print(f"[Story] Failed sharing to story: {story_exc}")
        return False


def wait_and_share_reel_to_story(cl, username, expected_title, thumbnail_path, max_wait_seconds=900):
    """
    Polls Instagram for the newly uploaded Reel, then shares it to Story
    using the generated high-contrast thumbnail as the background.

    Strategy (in order):
      1. Fuzzy title match against the 3 most recent Reels (>=60% word overlap).
      2. After 10 min with no match, fall back to the single most-recently-posted
         Reel — this fires even if Make.com reformatted the caption completely.
      3. Timeout after 15 minutes (900s) total.
    """
    import time
    FUZZY_THRESHOLD = 0.6          # 60% of title words must appear in caption
    FALLBACK_AFTER_SECONDS = 600   # 10 min: switch to recency fallback

    if not cl:
        print("[Story] Skipping Story post — client not logged in.")
        return False

    print(f"[Story] Waiting for Reel '{expected_title}' to appear (timeout: {max_wait_seconds}s)...")
    start_time = time.time()

    try:
        user_id = cl.user_id_from_username(username)
    except Exception as e:
        print(f"[Story] Failed to get user ID: {e}")
        return False

    fallback_used = False

    while time.time() - start_time < max_wait_seconds:
        elapsed = time.time() - start_time

        try:
            print(f"[Story] Checking recent feed posts... (elapsed: {int(elapsed)}s)")
            recent_posts = cl.user_medias(user_id, amount=5)

            # Collect only Reels
            reels = [p for p in recent_posts if p.media_type == 2 and p.product_type == "clips"]

            # --- Strategy 1: Fuzzy title match ---
            for post in reels:
                caption_text = post.caption_text or ""
                score = _title_match_score(expected_title, caption_text)
                print(f"[Story] Reel pk={post.pk} match score: {score:.2f} (need >= {FUZZY_THRESHOLD})")
                if score >= FUZZY_THRESHOLD:
                    print(f"[Story] ✅ Fuzzy match found! Reel pk={post.pk}")
                    return _share_reel_to_story(cl, post, thumbnail_path)

            # --- Strategy 2: Recency fallback after 10 min ---
            if elapsed >= FALLBACK_AFTER_SECONDS and reels and not fallback_used:
                fallback_used = True
                # Pick the most recently posted reel (first in list = newest)
                newest = reels[0]
                print(
                    f"[Story] ⚠️ No title match after {int(elapsed)}s. "
                    f"Falling back to most recent Reel pk={newest.pk} (posted: {newest.taken_at})"
                )
                return _share_reel_to_story(cl, newest, thumbnail_path)

        except Exception as e:
            print(f"[Story] Error checking feed: {e}")

        print("[Story] Reel not found yet. Sleeping 45 seconds...")
        time.sleep(45)

    print(f"[Story] Timeout reached ({max_wait_seconds}s). Reel was not detected. Skipping Story.")
    return False
