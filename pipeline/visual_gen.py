import requests
import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

def fetch_pexels_video(query, output_path):
    """Fetches a stock video from Pexels based on query."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found. Skipping video fetch.")
        return None
    
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data['total_results'] > 0:
            video_url = data['videos'][0]['video_files'][0]['link']
            # Download the video
            video_data = requests.get(video_url).content
            with open(output_path, 'wb') as f:
                f.write(video_data)
            return output_path
    
    return None

def fetch_pexels_image(query, output_path):
    """Fetches a stock image from Pexels based on query."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found. Skipping image fetch.")
        return None
    
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data['total_results'] > 0:
            image_url = data['photos'][0]['src']['large']
            image_data = requests.get(image_url).content
            with open(output_path, 'wb') as f:
                f.write(image_data)
            return output_path
    return None

def create_placeholder_image(output_path, text="Visual Placeholder"):
    """Creates a simple placeholder image."""
    img = Image.new('RGB', (1080, 1920), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    # Using default font for portability in this snippet
    d.text((400, 960), text, fill=(255, 255, 255))
    img.save(output_path)
    return output_path
