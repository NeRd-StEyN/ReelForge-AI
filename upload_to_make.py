import json
from dotenv import load_dotenv

from pipeline.make_handler import send_to_make_webhook

load_dotenv()

def upload_to_make():
    # 1. Read metadata
    with open('video_metadata.json', 'r') as f:
        meta = json.load(f)
    
    title = meta.get('title', 'AI Video')
    desc = meta.get('description', '')
    hashtags = meta.get('hashtags') or meta.get('tags') or []
    text = f"{desc}\n\n{' '.join(hashtags)}".strip()

    print("Sending output_video.mp4 to Make.com webhook...")
    success = send_to_make_webhook('output_video.mp4', title, text)
    print(f"Upload result: {'success' if success else 'failed'}")

if __name__ == "__main__":
    upload_to_make()
