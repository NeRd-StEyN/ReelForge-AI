#!/usr/bin/env python
"""Verify Instagram session file is valid and ready for GitHub Actions."""

import json
import os
import sys
from datetime import datetime
import time

print("=" * 70)
print("INSTAGRAM SESSION VERIFICATION REPORT")
print("=" * 70)

# Check if session file exists
session_file = "insta_session.json"
if not os.path.exists(session_file):
    print(f"\n❌ FAILED: Session file '{session_file}' NOT FOUND")
    sys.exit(1)

# Get file info
file_size = os.path.getsize(session_file)
file_mtime = os.path.getmtime(session_file)
modified_time = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d %H:%M:%S")

print(f"\n✅ Session file found")
print(f"   Location: {os.path.abspath(session_file)}")
print(f"   Size: {file_size} bytes")
print(f"   Modified: {modified_time}")

# Parse JSON
try:
    with open(session_file, 'r') as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f"\n❌ FAILED: Session file is CORRUPTED (invalid JSON)")
    print(f"   Error: {e}")
    sys.exit(1)

print(f"\n✅ Session file is valid JSON")

# Extract device context (instagrapi format)
print("\n📱 Device Context (Device Fingerprint):")

# Check different possible locations for device ID (instagrapi v2 format)
device_id = ""
if "device_settings" in data:
    device_id = data["device_settings"].get("android_device_id", "")
if not device_id and "uuids" in data:
    device_id = data["uuids"].get("android_device_id", "")

phone_id = ""
if "uuids" in data:
    phone_id = data["uuids"].get("phone_id", "")

uuid = ""
if "uuids" in data:
    uuid = data["uuids"].get("uuid", "")

user_agent = data.get("user_agent", "")

checks = {
    "Device ID (android)": device_id,
    "Phone ID": phone_id,
    "UUID": uuid,
    "User Agent": user_agent[:60] + "..." if len(user_agent) > 60 else user_agent,
}

all_present = True
for key, value in checks.items():
    status = "✅" if value else "❌"
    if not value:
        all_present = False
    print(f"   {status} {key}: {value if value else 'MISSING'}")

# Check authentication
print("\n🔐 Authentication Data:")
cookies = data.get("cookies", {})
has_cookies = bool(cookies)
print(f"   {'✅' if has_cookies else '❌'} Cookies: {len(cookies)} items" if has_cookies else "   ❌ Cookies: MISSING")

# Check required fields
print("\n📋 Session Structure:")
required_keys = ["uuids", "device_settings", "cookies", "user_agent"]
structure_ok = True
for key in required_keys:
    status = "✅" if key in data else "❌"
    if key not in data:
        structure_ok = False
    print(f"   {status} {key}")

# Check if session looks fresh
print("\n⏱️  Session Age:")
session_age_seconds = time.time() - file_mtime
session_age_hours = session_age_seconds / 3600
if session_age_hours < 24:
    print(f"   ✅ Fresh (generated {session_age_hours:.1f} hours ago)")
elif session_age_hours < 7*24:
    print(f"   ⚠️  Recent ({session_age_hours:.1f} hours ago)")
    age_ok = True
elif session_age_hours < 30*24:
    print(f"   ⚠️  Getting old ({session_age_hours/24:.0f} days ago - regenerate soon)")
    age_ok = True
else:
    print(f"   ❌ EXPIRED ({session_age_hours/24:.0f} days ago - regenerate NOW)")
    age_ok = False

# Final verdict
print("\n" + "=" * 70)
if all_present and has_cookies and device_id and structure_ok:
    print("✅ VERDICT: Session is VALID and ready for GitHub Actions")
    print("\n📝 Next Steps to Deploy:")
    print("   1. Go to: https://github.com/YOUR-USERNAME/ReelForge-AI")
    print("   2. Click: Settings → Secrets and variables → Actions")
    print("   3. Click: New repository secret")
    print("   4. Name: INSTA_SESSION")
    print("   5. Value: Copy entire contents of insta_session.json")
    print("   6. Click: Add secret")
    print("\n🧪 Test:")
    print("   1. Go to: Actions → Auto Reels")
    print("   2. Click: Run workflow → Run workflow")
    print("   3. Wait ~3 minutes")
    print("   4. Check logs for: ✅ Session validation passed")
    print("\n📅 Important: Regenerate session every ~30 days")
    print("   - Set calendar reminder for 1st of each month")
    print("   - Run: python generate_session.py")
    print("   - Update INSTA_SESSION secret with new JSON")
    print("=" * 70)
    sys.exit(0)
else:
    print("❌ VERDICT: Session has issues")
    print(f"\nIssues found:")
    if not device_id:
        print("   ❌ Device ID missing")
    if not phone_id:
        print("   ❌ Phone ID missing")
    if not has_cookies:
        print("   ❌ Cookies missing")
    if not structure_ok:
        print("   ❌ Session structure incomplete")
    if not age_ok:
        print("   ❌ Session expired or too old")
    
    print("\n🔧 Fix: Regenerate Session")
    print("   1. Run: python generate_session.py")
    print("   2. You'll see two options:")
    print("      Option 1: Standard Password Login")
    print("      Option 2: Bypass Challenge (RECOMMENDED)")
    print("\n📱 For Option 2 (Recommended):")
    print("   1. Login to instagram.com in Chrome browser")
    print("   2. Press F12 (or right-click → Inspect)")
    print("   3. Go to: Application tab → Cookies")
    print("   4. Find cookie named 'sessionid'")
    print("   5. Copy its value (long string)")
    print("   6. Paste into the script when prompted")
    print("\n✅ When successful, you'll see: 'SUCCESS! Session saved'")
    print("   Then rerun: python verify_session.py")
    print("=" * 70)
    sys.exit(1)
