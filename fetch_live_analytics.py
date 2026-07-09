"""
fetch_live_analytics.py
-----------------------
Fetches live Instagram reel analytics RIGHT NOW and saves a fresh snapshot
to insta_analytics_history.jsonl so the feedback loop reflects the latest reel.
Run manually: python fetch_live_analytics.py
"""
import sys
import os

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from pipeline.insta_handler import get_insta_client
from pipeline.feedback_loop import append_analytics_snapshot, summarize_feedback

print("=" * 60)
print("ReelForge -- Live Analytics Fetch")
print("=" * 60)

print("\n[Step 1] Logging into Instagram...")
cl = get_insta_client()
if not cl:
    print("ERROR: Could not get Instagram client. Check insta_session.json or .env")
    sys.exit(1)
print("[Step 1] Login OK")

username = os.getenv("INSTA_USERNAME", "")
print("\n[Step 2] Fetching last 12 posts for @" + username + "...")
try:
    # Use the authenticated session's own user_id — avoids the rate-limited
    # public web_profile_info endpoint that causes 429 errors
    user_id = cl.user_id
    if not user_id:
        raise ValueError("Session has no user_id — session may be expired. Re-run generate_session.py")
    print("[Step 2] Using session user_id: " + str(user_id))
    recent_posts = cl.user_medias(user_id, amount=12)
except Exception as e:
    print("ERROR fetching media list: " + str(e))
    sys.exit(1)

reels = []
for post in recent_posts:
    if post.media_type == 2 and post.product_type == "clips":
        views = (
            getattr(post, "play_count", None)
            or getattr(post, "view_count", None)
            or getattr(post, "video_view_count", None)
            or 0
        )
        reels.append({
            "topic_snippet": (post.caption_text or "")[:120].replace("\n", " ").strip(),
            "views": views,
            "likes": post.like_count or 0,
            "comments": post.comment_count or 0,
            "saves": getattr(post, "saved_count", None) or 0,
            "_taken_at": str(post.taken_at),
        })

print("[Step 2] Found " + str(len(reels)) + " reels")

if not reels:
    print("No reels found on account. Exiting.")
    sys.exit(0)

print("\n[Step 3] Reel list (newest first):")
print("-" * 60)
for i, r in enumerate(reels, 1):
    snippet = r["topic_snippet"].encode("ascii", "replace").decode("ascii")
    print("  #" + str(i) + " | " + r["_taken_at"])
    print("      views=" + str(r["views"]) + "  likes=" + str(r["likes"]) + "  comments=" + str(r["comments"]) + "  saves=" + str(r["saves"]))
    print("      Caption: " + snippet[:90])
print("-" * 60)

print("\n[Step 4] Saving fresh snapshot to insta_analytics_history.jsonl...")
domain = os.getenv("CONTENT_DOMAIN", "psychology of attraction")
save_reels = [{k: v for k, v in r.items() if k != "_taken_at"} for r in reels]
append_analytics_snapshot(domain, save_reels)

print("\n[Step 5] Updated feedback summary:")
print("=" * 60)
summary = summarize_feedback(limit=30)
print(summary.encode("ascii", "replace").decode("ascii"))
print("=" * 60)
print("\nDone. insta_analytics_history.jsonl is now up to date.")
