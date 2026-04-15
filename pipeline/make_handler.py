import os
import requests

def send_to_make_webhook(video_path, caption):
    """Sends the finalized MP4 and caption to a Make.com Webhook using Multipart Form Data."""
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    
    if not webhook_url:
        print("Upload skipped: MAKE_WEBHOOK_URL not found in .env")
        return False
        
    try:
        print(f"Uploading Video and Caption to Make.com Webhook...")
        # Send the video file binary and the text caption securely
        with open(video_path, 'rb') as f:
            files = {
                'file': ('output_video.mp4', f, 'video/mp4')
            }
            data = {
                'caption': caption
            }
            
            response = requests.post(webhook_url, files=files, data=data)
            
            if response.status_code == 200:
                print("Success! Reel securely payloaded to Make.com.")
                return True
            else:
                print(f"Make.com Webhook failed with status code {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"Failed to post to Make.com: {e}")
        return False
