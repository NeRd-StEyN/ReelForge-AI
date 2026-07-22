"""
post_story.py
-------------
Posts an Instagram Story with an interactive Poll sticker directly using your session.

Usage:
  python post_story.py
  python post_story.py --question "Is this psychology fact relatable?" --opt1 "Yes 🔥" --opt2 "No 🤔"
  python post_story.py --image assets/images/my_cover.jpg --question "Did you know this?"
"""
import sys
import os
import argparse

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from pipeline.insta_handler import get_insta_client, post_poll_story

def main():
    parser = argparse.ArgumentParser(description="Post an Instagram Story with optional interactive Poll.")
    parser.add_argument("--image", type=str, default=None, help="Path to image file for Story background")
    parser.add_argument("--question", type=str, default="Ye psychological fact relatable lagta hai?", help="Poll question text")
    parser.add_argument("--opt1", type=str, default="Haan 🔥", help="Poll Option 1")
    parser.add_argument("--opt2", type=str, default="Nahi 🤔", help="Poll Option 2")

    args = parser.parse_args()

    print("=" * 60)
    print("ReelForge -- Instagram Story Poster")
    print("=" * 60)

    print("\n[Step 1] Authenticating with Instagram...")
    cl = get_insta_client()
    if not cl:
        print("[FAIL] Could not get Instagram client. Check insta_session.json or .env")
        sys.exit(1)

    story_poll = {
        "question": args.question,
        "option_1": args.opt1,
        "option_2": args.opt2,
    }

    print(f"\n[Step 2] Posting Story slide with Poll:")
    print(f"  Question : {args.question}")
    print(f"  Option 1 : {args.opt1}")
    print(f"  Option 2 : {args.opt2}")
    if args.image:
        print(f"  Image    : {args.image}")

    success = post_poll_story(cl, args.image, story_poll)
    if success:
        print("\n[OK] Story posted successfully to Instagram!")
    else:
        print("\n[FAIL] Could not post Story.")

if __name__ == "__main__":
    main()
