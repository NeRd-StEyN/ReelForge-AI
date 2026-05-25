"""
Test runner for creating a complete multi-scene AI generated video.
Mocks a 2-scene script to test the full pipeline (script -> audio -> AI video -> MoviePy stitching -> output_video.mp4).
"""
import os
import sys
from unittest.mock import patch

# Mock the script generator to only return 2 scenes so the test is quick and doesn't hit HF rate limits
MOCK_SCRIPT = {
    "topic": "Attraction Secrets",
    "hook": "Do you want to know if she likes you?",
    "scenes": [
        {
            "visual_keyword": "beautiful woman smiling mystery eyes",
            "text": "The psychological secret of eye contact will blow your mind. Watch her eyes closely."
        },
        {
            "visual_keyword": "beautiful girl looking away blushing romantic",
            "text": "If she blushes and looks down, she is already attracted to you. Trust the signs."
        }
    ]
}

print("=" * 60)
print("TEST: Full Stitched 30-Second AI Video Pipeline")
print("=" * 60)

# Mock make_webhook so it doesn't upload the draft to Instagram during testing
with patch("pipeline.make_handler.send_to_make_webhook", return_value=True), \
     patch("pipeline.script_gen.generate_script_payload", return_value=MOCK_SCRIPT):
    
    from main import main
    # Run the main pipeline!
    main("attraction secrets")

print("\n" + "=" * 60)
print("Test complete. Check output_video.mp4 for the final result!")
print("=" * 60)
