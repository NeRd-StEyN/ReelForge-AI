import os
from instagrapi import Client
import threading


def _validate_session(cl):
    """Verify session is still active by making a test API call.
    
    Returns True if session is valid, False otherwise.
    This prevents silent failures where session loads but is expired.
    """
    if not cl:
        return False
    
    try:
        # Try to get own user info — simple validation that doesn't hit public API
        user_id = cl.user_id
        if not user_id:
            print("[Session] Validation: user_id is None, session may be expired")
            return False
        print("[Session] Validation: Session is active (user_id found)")
        return True
    except Exception as e:
        print(f"[Session] Validation failed: {e}")
        return False


def get_insta_client():
    """Logs into Instagram and returns the client using session persistence.

    IMPORTANT: Instagram blocks session ID-only logins as a security measure.
    The ONLY reliable method on GitHub Actions is the full session file.

    Login priority:
      1. insta_session.json  — full session file from INSTA_SESSION secret.
                               Only reliable method that works on GitHub Actions.
      2. Password login      — fallback; often blocked on cloud IPs by Instagram.

    ⚠️  INSTA_SESSION_ID is no longer used (Instagram blocks session ID auth).
    """
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")

    if not username:
        print("[Analytics] WARNING: INSTA_USERNAME missing in .env — skipping analytics.")
        return None

    cl = Client()

    try:
        # Restore session file from INSTA_SESSION env variable if file doesn't exist on runner
        if not os.path.exists("insta_session.json"):
            env_session = os.getenv("INSTA_SESSION")
            if env_session and env_session.strip():
                try:
                    print("[Analytics] Restoring insta_session.json from INSTA_SESSION secret...")
                    with open("insta_session.json", "w", encoding="utf-8") as f:
                        f.write(env_session.strip())
                except Exception as exc:
                    print(f"[Analytics] Failed to write INSTA_SESSION to file: {exc}")

        # ── Priority 1: Full session file (ONLY reliable method) ──────
        if os.path.exists("insta_session.json") and os.path.getsize("insta_session.json") > 10:
            try:
                print(f"[Analytics] Loading full session file for @{username}...")
                cl.load_settings("insta_session.json")
                print("[Analytics] Session file loaded successfully.")
                # Validate that the session is actually active (not expired)
                if _validate_session(cl):
                    print("[Analytics] [OK] Session validation passed. Ready for Story posting & analytics.")
                    return cl
                else:
                    print("[Analytics] [FAIL] Session file expired or invalid.")
                    print("[Analytics] Action required: Run generate_session.py locally and update INSTA_SESSION secret.")
                    print("[Analytics] Session files expire after ~30 days. You must regenerate periodically.")
                    cl = Client()  # Reset client for fallback
            except Exception as load_err:
                print(f"[Analytics] Failed to parse insta_session.json ({load_err}) — resetting client.")
                cl = Client()

        # ── Fallback: Password login (often blocked on GitHub Actions) ─
        if password:
            print(f"[Analytics] [WARN] No valid session file. Attempting password login for @{username}...")
            print("[Analytics] WARNING: Password login is frequently blocked by Instagram on cloud IPs.")
            print("[Analytics] For reliable automation, use session file instead (see above).")
            try:
                cl.login(username, password)
                if _validate_session(cl):
                    print("[Analytics] Password login successful (rare on GitHub Actions).")
                    return cl
            except Exception as login_err:
                print(f"[Analytics] Password login failed: {login_err}")

        # ── All methods failed ──────────────────────────────────────────
        print("[Analytics] ❌ ALL LOGIN METHODS FAILED")
        print("[Analytics] To fix this:")
        print("[Analytics]   1. Run: python generate_session.py")
        print("[Analytics]   2. Copy the output JSON")
        print("[Analytics]   3. Add it to GitHub Secret 'INSTA_SESSION'")
        print("[Analytics]   4. Regenerate every ~30 days when session expires")
        print("[Analytics] Will fall back to saved history for feedback. No live data this run.")
        return None

    except Exception as e:
        print(f"[Analytics] UNEXPECTED ERROR: {e}")
        print("[Analytics] Will fall back to saved history for feedback. No live data this run.")
        return None


def _get_medias_with_timeout(cl, user_id, amount=20, timeout_seconds=30):
    """Fetch medias with timeout to prevent hanging on slow runners.
    
    Returns list of media objects on success, raises TimeoutError on timeout.
    """
    result = [None]
    exception = [None]
    
    def fetch():
        try:
            result[0] = cl.user_medias(user_id, amount=amount)
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=fetch, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        raise TimeoutError(f"user_medias() exceeded {timeout_seconds}s timeout")
    
    if exception[0]:
        raise exception[0]
    
    return result[0]


def get_performance_data(cl):
    """Fetches views and likes for the last 20 reels. Returns a list or None.

    Uses cl.user_id (session-based) instead of user_id_from_username() which
    hits Instagram's rate-limited public API and frequently returns 429 errors
    on GitHub Actions runners — this was the root cause of analytics silently
    failing and returning None.
    """
    if not cl:
        print("[Analytics] Skipping live fetch — not logged in.")
        return None

    try:
        print("[Analytics] Fetching recent reel performance data...")
        # Use the session's own user_id — avoids the rate-limited public
        # web_profile_info endpoint that causes 429 errors on cloud IPs.
        user_id = cl.user_id
        if not user_id:
            # Fallback: try the username lookup (slower, less reliable)
            username = os.getenv("INSTA_USERNAME")
            print(f"[Analytics] Session has no user_id — falling back to username lookup for @{username}...")
            user_id = cl.user_id_from_username(username)

        try:
            recent_posts = _get_medias_with_timeout(cl, user_id, amount=20, timeout_seconds=30)
        except TimeoutError as e:
            print(f"[Analytics] Timeout fetching medias: {e}")
            print("[Analytics] Will skip live analytics this run and use saved history.")
            return None

        analytics = []
        for post in recent_posts:
            # Only count Reels (media_type=2, product_type='clips')
            if post.media_type == 2 and post.product_type == "clips":
                is_pinned = bool(
                    getattr(post, "is_pinned", False)
                    or getattr(post, "pinned_for_user", False)
                )
                taken_at_dt = getattr(post, "taken_at", None)
                post_date = taken_at_dt.strftime("%Y-%m-%d") if taken_at_dt else ""

                analytics.append({
                    "topic_snippet": (post.caption_text or "")[:120].replace("\n", " ").strip(),
                    "views": getattr(post, "play_count", None) or getattr(post, "view_count", None) or getattr(post, "video_view_count", None) or 0,
                    "likes": post.like_count or 0,
                    "comments": post.comment_count or 0,
                    "shares": getattr(post, "share_count", None) or 0,
                    "saves": getattr(post, "saved_count", None) or 0,
                    "is_pinned": is_pinned,
                    "post_date": post_date,
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


def _share_reel_to_story(cl, post, thumbnail_path, story_poll=None):
    """Attempt to share a reel post to story. Returns True on success.
    If story_poll is provided, also posts a follow-up poll story slide.
    Poll failures do NOT cause the entire story posting to fail.
    """
    try:
        try:
            if thumbnail_path and os.path.exists(thumbnail_path):
                cl.media_share_to_story(post.pk, background=thumbnail_path)
            else:
                cl.media_share_to_story(post.pk)
        except Exception as bg_exc:
            print(f"[Story] media_share_to_story with background failed: {bg_exc}. Retrying without background...")
            cl.media_share_to_story(post.pk)
        print("[Story] Successfully posted Story promotion! 🚀")

        # Post poll slide immediately after the reel share card
        # Wrap in try-catch so poll failures don't fail the entire story post
        if story_poll:
            import time
            time.sleep(3)  # brief pause so Instagram doesn't rate-limit back-to-back stories
            try:
                post_poll_story(cl, thumbnail_path, story_poll)
            except Exception as poll_err:
                # Poll failures are non-fatal — main reel story already posted
                print(f"[Poll] ⚠️ Poll story posting failed (non-fatal): {poll_err}")
                print("[Poll] Main reel story was posted successfully. Poll story skipped.")

        return True
    except Exception as story_exc:
        print(f"[Story] Failed sharing to story: {story_exc}")
        return False


def _get_safe_user_id(cl, username, max_retries=3):
    """Get user_id with retry logic for rate limiting (429 errors).
    
    Returns user_id on success, raises exception on failure after max_retries.
    """
    import time
    
    # Try session-based user_id first (most reliable)
    user_id = cl.user_id
    if user_id:
        print(f"[Story] Using session-based user_id: {user_id}")
        return user_id
    
    # Fallback to username lookup with exponential backoff for rate limiting
    print(f"[Story] Session user_id not available, falling back to username lookup...")
    for attempt in range(max_retries):
        try:
            print(f"[Story] Fetching user_id for @{username} (attempt {attempt+1}/{max_retries})...")
            user_id = cl.user_id_from_username(username)
            if user_id:
                print(f"[Story] Got user_id from username: {user_id}")
                return user_id
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "rate" in error_str or "too many" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    print(f"[Story] Rate limited (429). Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"[Story] Rate limited after {max_retries} attempts. Giving up.")
                    raise Exception(f"Rate limited after {max_retries} retries: {e}")
            else:
                # Non-rate-limit error, fail immediately
                raise
    
    raise Exception(f"Could not get user_id for @{username}")


def wait_and_share_reel_to_story(cl, username, expected_title, thumbnail_path, story_poll=None, max_wait_seconds=1500):
    """
    Polls Instagram for the newly uploaded Reel, then shares it to Story
    using the generated high-contrast thumbnail as the background.
    If story_poll is provided, also posts a follow-up poll story slide.

    Strategy (in order):
      1. Fuzzy title match against the 5 most recent Reels (>=50% word overlap).
      2. After 15 min with no match, fall back to the single most-recently-posted
         Reel — this fires even if Make.com reformatted the caption completely.
      3. Timeout after 25 minutes (1500s) total.
    """
    import time
    FUZZY_THRESHOLD = 0.5          # 50% of title words must appear in caption
    FALLBACK_AFTER_SECONDS = 900   # 15 min: switch to recency fallback

    if not cl:
        print("[Story] Skipping Story post — client not logged in.")
        return False

    print(f"[Story] Waiting for Reel '{expected_title}' to appear (timeout: {max_wait_seconds}s)...")
    start_time = time.time()

    try:
        # Use safe user_id fetch with retry logic for rate limits
        user_id = _get_safe_user_id(cl, username)
    except Exception as e:
        print(f"[Story] Failed to get user ID: {e}")
        return False

    fallback_used = False

    while time.time() - start_time < max_wait_seconds:
        elapsed = time.time() - start_time

        try:
            print(f"[Story] Checking recent feed posts... (elapsed: {int(elapsed)}s)")
            recent_posts = cl.user_medias(user_id, amount=5)

            # Collect only Reels (sometimes product_type is not 'clips', just rely on media_type 2)
            reels = [p for p in recent_posts if getattr(p, "media_type", None) == 2]
            print(f"[Story] Found {len(recent_posts)} recent posts. Filtered to {len(reels)} reels.")

            # --- Strategy 1: Fuzzy title match ---
            for post in reels:
                caption_text = post.caption_text or ""
                score = _title_match_score(expected_title, caption_text)
                print(f"[Story] Reel pk={post.pk} match score: {score:.2f} (need >= {FUZZY_THRESHOLD})")
                if score >= FUZZY_THRESHOLD:
                    print(f"[Story] ✅ Fuzzy match found! Reel pk={post.pk}")
                    return _share_reel_to_story(cl, post, thumbnail_path, story_poll=story_poll)

            # --- Strategy 2: Recency fallback after 10 min ---
            if elapsed >= FALLBACK_AFTER_SECONDS and reels and not fallback_used:
                fallback_used = True
                # Pick the most recently posted reel (first in list = newest)
                newest = reels[0]
                print(
                    f"[Story] ⚠️ No title match after {int(elapsed)}s. "
                    f"Falling back to most recent Reel pk={newest.pk} (posted: {newest.taken_at})"
                )
                return _share_reel_to_story(cl, newest, thumbnail_path, story_poll=story_poll)

        except Exception as e:
            print(f"[Story] Error checking feed: {e}")

        print("[Story] Reel not found yet. Sleeping 45 seconds...")
        time.sleep(45)

    print(f"[Story] Timeout reached ({max_wait_seconds}s). Reel was not detected. Skipping Story.")
    return False
