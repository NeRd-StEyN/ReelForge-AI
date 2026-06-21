import os
import urllib.request

def _maybe_download_bg_music(target_path, url):
    if os.path.exists(target_path):
        os.remove(target_path)
    try:
        print(f"Downloading background music to {target_path}...")
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            out_file.write(response.read())
        print("Background music downloaded.")
        return target_path
    except Exception as e:
        print(f"Could not download background music: {e}")
        return None

print("Testing Pixabay Default")
_maybe_download_bg_music("test_default.mp3", "https://cdn.pixabay.com/audio/2024/11/01/audio_1f6b285aea.mp3")

print("Testing Incompetech Horror")
_maybe_download_bg_music("test_horror.mp3", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gathering%20Darkness.mp3")

print("Done.")
