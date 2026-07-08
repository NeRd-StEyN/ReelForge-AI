import os
from instagrapi import Client


def get_insta_client():
    """Logs into Instagram and returns the client using session persistence.

    Login priority (most reliable → least):
      1. insta_session.json  — full session file written by generate_session.py
                               or by GitHub Actions from the INSTA_SESSION secret.
                               Most stable; survives longer than a single cookie.
      2. INSTA_SESSION_ID    — single sessionid cookie (legacy fallback).
      3. Password login      — last resort; often blocked on cloud IPs.
    """
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    sessionid_cookie = os.getenv("INSTA_SESSION_ID")

    if not username:
        print("[Analytics] WARNING: INSTA_USERNAME missing in .env — skipping analytics.")
        return None

    cl = Client()

    try:
        # ── Priority 1: Full session file (most reliable) ──────────────
        if os.path.exists("insta_session.json"):
            print(f"[Analytics] Loading full session file for @{username}...")
            cl.load_settings("insta_session.json")
            print("[Analytics] Session file loaded successfully.")
            return cl

        # ── Priority 2: Single session cookie (legacy) ─────────────────
        if sessionid_cookie:
            print(f"[Analytics] Logging in via session cookie for @{username}...")
            cl.login_by_sessionid(sessionid_cookie)
            print("[Analytics] Session cookie login successful.")
            return cl

        # ── Priority 3: Password login (often blocked on cloud runners) ─
        print(f"[Analytics] ⚠️  No session file or cookie found. Attempting password login for @{username}...")
        print("[Analytics] NOTE: Password login is often blocked on GitHub Actions IPs.")
        cl.login(username, password)
        print("[Analytics] Password login successful.")
        return cl

    except Exception as e:
        print(f"[Analytics] LOGIN FAILED for @{username}: {e}")
        print("[Analytics] Tip: Run generate_session.py locally and save output to INSTA_SESSION GitHub Secret.")
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


def post_poll_story(cl, thumbnail_path, story_poll):
    """
    Posts a separate Story slide with a poll sticker.
    This drives viewers from Stories back to the Reel — one of the highest
    engagement amplifiers on Instagram.

    story_poll dict format:
        {"question": "...", "option_1": "...", "option_2": "..."}
    """
    if not cl or not story_poll or not isinstance(story_poll, dict):
        print("[Poll] No poll data — skipping poll story.")
        return False

    question = story_poll.get("question", "").strip()
    opt1     = story_poll.get("option_1", "Haan 🔥").strip()[:20]
    opt2     = story_poll.get("option_2", "Nahi 🤔").strip()[:20]

    if not question:
        print("[Poll] Empty question — skipping poll story.")
        return False

    # Background: use thumbnail if available, else create a plain dark card
    bg_path = thumbnail_path if (thumbnail_path and os.path.exists(thumbnail_path)) else None
    if not bg_path:
        print("[Poll] No thumbnail found — will use plain black background for poll story.")
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (1080, 1920), color=(15, 15, 15))
            fallback_path = "assets/images/poll_bg.jpg"
            os.makedirs("assets/images", exist_ok=True)
            img.save(fallback_path)
            bg_path = fallback_path
        except Exception as img_err:
            print(f"[Poll] Could not create fallback image: {img_err}")
            return False

    try:
        from instagrapi.types import StoryPollSticker, StoryPoll, StoryBuildedMedia
        print(f"[Poll] Posting poll story: '{question}' | {opt1} / {opt2}")

        poll_sticker = StoryPollSticker(
            poll=StoryPoll(
                question=question[:80],  # Instagram caps at 80 chars
                tallies=[
                    {"text": opt1, "font_size": 35.0},
                    {"text": opt2, "font_size": 35.0},
                ],
            ),
            x=0.5,
            y=0.75,
            width=0.6,
            height=0.12,
            rotation=0.0,
        )

        cl.photo_upload_to_story(
            path=bg_path,
            poll_sticker=poll_sticker,
        )
        print("[Poll] ✅ Poll story posted successfully!")
        return True

    except ImportError:
        print("[Poll] StoryPollSticker not available in this instagrapi version — trying legacy API...")
    except Exception as exc:
        print(f"[Poll] poll_sticker API failed ({exc}), trying legacy dict approach...")

    # Legacy fallback: pass poll as a plain dict (older instagrapi builds)
    try:
        cl.photo_upload_to_story(
            path=bg_path,
            poll_sticker={
                "question": question[:80],
                "options": [opt1, opt2],
                "x": 0.5,
                "y": 0.75,
            },
        )
        print("[Poll] ✅ Poll story posted (legacy dict mode).")
        return True
    except Exception as fallback_exc:
        print(f"[Poll] ❌ Poll story failed entirely: {fallback_exc}")
        return False


def _share_reel_to_story(cl, post, thumbnail_path, story_poll=None, first_comment=None):
    """Attempt to share a reel post to story. Returns True on success.
    If first_comment is provided, it posts a comment on the reel.
    If story_poll is provided, also posts a follow-up poll story slide.
    """
    try:
        if thumbnail_path and os.path.exists(thumbnail_path):
            cl.media_share_to_story(post.pk, background=thumbnail_path)
        else:
            cl.media_share_to_story(post.pk)
        print("[Story] Successfully posted Story promotion! 🚀")

        # Post the AI-generated first comment to spark debate
        if first_comment:
            try:
                import time
                time.sleep(2)  # Pause to avoid rate limits
                print(f"[Comment] Posting first comment: '{first_comment[:50]}...'")
                cl.media_comment(post.pk, str(first_comment))
                print("[Comment] ✅ First comment posted successfully!")
            except Exception as comment_err:
                print(f"[Comment] Failed to post first comment: {comment_err}")

        # Post poll slide immediately after the reel share card
        if story_poll:
            import time
            time.sleep(3)  # brief pause so Instagram doesn't rate-limit back-to-back stories
            post_poll_story(cl, thumbnail_path, story_poll)

        return True
    except Exception as story_exc:
        print(f"[Story] Failed sharing to story: {story_exc}")
        return False


def wait_and_share_reel_to_story(cl, username, expected_title, thumbnail_path, story_poll=None, first_comment=None, max_wait_seconds=900):
    """
    Polls Instagram for the newly uploaded Reel, then shares it to Story
    using the generated high-contrast thumbnail as the background.
    If first_comment is provided, it posts a comment on the Reel to spark debate.
    If story_poll is provided, also posts a follow-up poll story slide.

    Strategy (in order):
      1. Fuzzy title match against the 5 most recent Reels (>=60% word overlap).
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
                    return _share_reel_to_story(cl, post, thumbnail_path, story_poll=story_poll, first_comment=first_comment)

            # --- Strategy 2: Recency fallback after 10 min ---
            if elapsed >= FALLBACK_AFTER_SECONDS and reels and not fallback_used:
                fallback_used = True
                # Pick the most recently posted reel (first in list = newest)
                newest = reels[0]
                print(
                    f"[Story] ⚠️ No title match after {int(elapsed)}s. "
                    f"Falling back to most recent Reel pk={newest.pk} (posted: {newest.taken_at})"
                )
                return _share_reel_to_story(cl, newest, thumbnail_path, story_poll=story_poll, first_comment=first_comment)

        except Exception as e:
            print(f"[Story] Error checking feed: {e}")

        print("[Story] Reel not found yet. Sleeping 45 seconds...")
        time.sleep(45)

    print(f"[Story] Timeout reached ({max_wait_seconds}s). Reel was not detected. Skipping Story.")
    return False
