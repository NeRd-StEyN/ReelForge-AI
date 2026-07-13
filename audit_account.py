import json
from instagrapi import Client

def audit_account():
    print("Loading session...")
    cl = Client()
    try:
        cl.load_settings("insta_session.json")
        cl.get_timeline_feed()  # Verify session
        print("Successfully logged in.")
    except Exception as e:
        print(f"Failed to log in using session: {e}")
        return

    user_id = cl.user_id
    user_info = cl.user_info(user_id)
    
    print(f"\n--- Account Overview ---")
    print(f"Username: {user_info.username}")
    print(f"Full Name: {user_info.full_name}")
    print(f"Followers: {user_info.follower_count}")
    print(f"Following: {user_info.following_count}")
    print(f"Total Media: {user_info.media_count}")
    
    print(f"\n--- Fetching recent reels ---")
    medias = cl.user_medias(user_id, amount=20)
    reels = [m for m in medias if m.media_type == 2] # 2 = video/reel
    
    total_views = 0
    total_likes = 0
    total_comments = 0
    
    print(f"Found {len(reels)} recent reels out of {len(medias)} fetched posts.")
    for i, m in enumerate(reels[:10]):
        views = getattr(m, 'view_count', 0) or getattr(m, 'play_count', 0)
        likes = m.like_count
        comments = m.comment_count
        title = m.caption_text.split('\n')[0] if m.caption_text else "No caption"
        print(f"{i+1}. Views: {views} | Likes: {likes} | Comments: {comments} | Title: {title[:40]}...")
        total_views += views
        total_likes += likes
        total_comments += comments
        
    if reels:
        avg_views = total_views / len(reels[:10])
        avg_likes = total_likes / len(reels[:10])
        print(f"\n--- Averages for last {len(reels[:10])} reels ---")
        print(f"Avg Views: {avg_views}")
        print(f"Avg Likes: {avg_likes}")
        if avg_views > 0:
            print(f"Like-to-View Ratio: {(avg_likes/avg_views)*100:.2f}%")

if __name__ == "__main__":
    audit_account()
