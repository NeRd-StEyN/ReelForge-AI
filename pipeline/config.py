import os

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
VIDEO_DIR = os.path.join(ASSETS_DIR, "video")
IMAGE_DIR = os.path.join(ASSETS_DIR, "images")

def setup_directories():
    """Creates necessary directories for assets."""
    for directory in [AUDIO_DIR, VIDEO_DIR, IMAGE_DIR]:
        os.makedirs(directory, exist_ok=True)
