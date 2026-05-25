"""
Quick test: multimodalart/wan2-1-fast (Image-to-Video).
Uses submit() for proper async handling.
"""
from gradio_client import Client, handle_file
from PIL import Image, ImageDraw
import shutil
import os

OUTPUT = "test_ai_video.mp4"

print("=" * 50)
print("TEST: wan2-1-fast (Image-to-Video)")  
print("=" * 50)

# Create a placeholder image
placeholder_path = "test_placeholder.jpg"
img = Image.new("RGB", (512, 896), color=(25, 15, 40))
draw = ImageDraw.Draw(img)
for i in range(20):
    y = i * 45
    r = min(255, 100 + i * 8)
    g = min(255, 50 + i * 5)
    b = min(255, 80 + i * 6)
    draw.rectangle([0, y, 512, y + 45], fill=(r, g, b))
img.save(placeholder_path, quality=95)
print(f"Created placeholder image: {placeholder_path}")

try:
    print("\nConnecting to multimodalart/wan2-1-fast...")
    client = Client("multimodalart/wan2-1-fast", verbose=True)
    print("Connected!")

    print("Submitting video generation...")
    print("(This will take 1-5 minutes depending on queue)")
    
    # Use submit() for async - handles long generation times better
    job = client.submit(
        input_image=handle_file(placeholder_path),
        prompt="A beautiful woman dancing gracefully, cinematic golden hour lighting, smooth motion, aesthetic",
        height=896,
        width=512,
        negative_prompt="static, blurred, watermark, ugly, cartoon, anime, distorted",
        duration_seconds=2.0,
        guidance_scale=1.0,
        steps=4,
        seed=-1,
        randomize_seed=True,
        api_name="/generate_video"
    )

    # Wait up to 10 minutes
    result = job.result(timeout=600)
    print(f"\nResult received!")

    video_info = result[0]
    if video_info and isinstance(video_info, dict) and video_info.get("video"):
        src = video_info["video"]
        shutil.copy(src, OUTPUT)
        size_kb = os.path.getsize(OUTPUT) / 1024
        print(f"\nSUCCESS! AI video saved to: {os.path.abspath(OUTPUT)}")
        print(f"File size: {size_kb:.1f} KB")
    else:
        print(f"Unexpected result format: {result}")

except Exception as e:
    print(f"\nFailed: {e}")
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(placeholder_path):
        os.remove(placeholder_path)

print("\n" + "=" * 50)
print("Test complete.")
