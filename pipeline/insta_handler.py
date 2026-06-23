import os
from instagrapi import Client

def get_insta_client():
    """Logs into Instagram and returns the client using session persistence."""
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    sessionid_cookie = os.getenv("INSTA_SESSION_ID")
    
    if not username:
        print("Warning: Missing INSTA_USERNAME in .env")
        return None
        
    cl = Client()
    
    try:
        if sessionid_cookie:
            print(f"Bypassing login screen using raw sessionid cookie for {username}...")
            cl.login_by_sessionid(sessionid_cookie)
            return cl
            
        import os.path
        if os.path.exists("insta_session.json"):
            print(f"Loading local Instagram session file for {username}...")
            cl.load_settings("insta_session.json")
            return cl

        print(f"Logging into Instagram via password for {username} (Warning: might be blocked on cloud servers)...")
        cl.login(username, password)
        return cl
    except Exception as e:
        print(f"Instagrapi Login Failed: {e}")
        return None

def get_performance_data(cl):
    """Fetches views and likes for the last 5 reels."""
    if not cl:
        return "No analytics data available (Not logged in)."
        
    try:
        print("Fetching recent reel analytics...")
        user_id = cl.user_id_from_username(os.getenv("INSTA_USERNAME"))
        recent_posts = cl.user_medias(user_id, amount=7)
        
        analytics = []
        for post in recent_posts:
            # Check if it's a video/reel
            if post.media_type == 2 and post.product_type == "clips": 
                analytics.append({
                    "topic_snippet": post.caption_text[:100].replace('\n', ' '), 
                    "views": post.view_count,
                    "likes": post.like_count
                })
        
        if not analytics:
            return "No previous reels found. Start fresh!"
            
        return analytics
    except Exception as e:
        print(f"Could not fetch analytics: {e}")
        return "Error fetching analytics data."

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
