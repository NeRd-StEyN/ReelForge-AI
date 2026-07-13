#!/usr/bin/env python
"""
Auto-Renewal Helper Script for Windows Task Scheduler
Run this script daily - it will check if session needs renewal and attempt it

Usage:
  1. Save this file as auto_renew_session.py in your project root
  2. Open Windows Task Scheduler
  3. Create Basic Task:
     - Name: ReelForge Session Auto-Renewal
     - Trigger: Daily at 2:00 AM
     - Action: Start a program
     - Program: python.exe
     - Arguments: C:\Users\43ner\Desktop\ReelForge-AI\auto_renew_session.py
     - Check "Run whether user is logged in or not"
  4. Done! It will auto-check and renew every day
"""

import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent
SESSION_FILE = PROJECT_ROOT / "insta_session.json"
LOG_FILE = PROJECT_ROOT / "auto_renew_log.txt"

def log_message(message, level="INFO"):
    """Log message to both console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    
    print(log_entry)
    
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"Could not write to log file: {e}")

def get_session_age():
    """Get session age in days"""
    if not SESSION_FILE.exists():
        return None
    
    try:
        with open(SESSION_FILE, 'r') as f:
            data = json.load(f)
        
        last_login = data.get("last_login")
        if not last_login:
            return None
        
        # Parse ISO format timestamp
        created_time = datetime.fromisoformat(last_login.replace('Z', '+00:00'))
        age = datetime.now(created_time.tzinfo) - created_time
        return age.days
        
    except Exception as e:
        log_message(f"Error reading session age: {e}", "ERROR")
        return None

def check_session_validity():
    """Check if session needs renewal"""
    if not SESSION_FILE.exists():
        log_message("Session file not found - skipping check", "WARN")
        return False
    
    age = get_session_age()
    
    if age is None:
        log_message("Could not determine session age", "WARN")
        return False
    
    log_message(f"Session age: {age} days", "INFO")
    
    if age >= 28:  # Renew at 28 days (before 30 day expiry)
        log_message(f"⚠️  Session is {age} days old - renewal needed!", "WARN")
        return True
    elif age >= 24:
        log_message(f"Session is {age} days old - getting close to expiry (30 days)", "INFO")
    else:
        log_message(f"Session is {age} days old - still fresh", "INFO")
    
    return False

def attempt_password_renewal():
    """Attempt to renew session using password login"""
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    
    if not username or not password:
        log_message("INSTA_USERNAME or INSTA_PASSWORD not found in environment", "ERROR")
        log_message("Set these as environment variables or in .env file to enable auto-renewal", "INFO")
        return False
    
    try:
        from instagrapi import Client
        
        log_message(f"Attempting password login for @{username}...", "INFO")
        cl = Client()
        cl.login(username, password)
        
        user_id = cl.user_id
        if user_id:
            cl.dump_settings(str(SESSION_FILE))
            log_message(f"✅ Session renewed successfully!", "INFO")
            log_message(f"   Authenticated as User ID: {user_id}", "INFO")
            log_message(f"   Session saved to {SESSION_FILE}", "INFO")
            return True
        else:
            log_message("Login succeeded but user_id not found", "ERROR")
            return False
            
    except Exception as e:
        log_message(f"Password login failed: {e}", "WARN")
        log_message("Note: Instagram blocks password login on some cloud environments", "INFO")
        return False

def send_renewal_alert():
    """Generate renewal instructions for manual process"""
    alert_file = PROJECT_ROOT / "RENEWAL_ALERT.txt"
    
    instructions = f"""
⚠️  MANUAL SESSION RENEWAL REQUIRED
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Your Instagram session is about to expire (28+ days old).

MANUAL RENEWAL STEPS (5 minutes):
1. Open PowerShell and run:
   python generate_session.py

2. Choose Option 2: Browser Bypass Method

3. Login to instagram.com in Chrome

4. Extract sessionid from DevTools:
   - Press F12
   - Application → Cookies
   - Find "sessionid" cookie
   - Copy its value

5. Paste into the script when prompted

6. Verify:
   python verify_session.py
   Should show: ✅ Fresh

7. Update GitHub Secret:
   - Go to GitHub Settings → Secrets and variables → Actions
   - Update INSTA_SESSION with new JSON contents

Or, to enable automatic renewal:
1. Set environment variables:
   INSTA_USERNAME = your Instagram username
   INSTA_PASSWORD = your Instagram password

2. This script will auto-renew next month

Questions? See: DEPLOYMENT_READY.md
"""
    
    try:
        with open(alert_file, 'w') as f:
            f.write(instructions)
        log_message(f"Renewal alert saved to {alert_file}", "INFO")
    except Exception as e:
        log_message(f"Could not write alert file: {e}", "ERROR")

def main():
    """Main renewal check"""
    log_message("=" * 70, "INFO")
    log_message("Session Auto-Renewal Check", "INFO")
    log_message("=" * 70, "INFO")
    
    # Check if renewal is needed
    if not check_session_validity():
        log_message("No renewal needed at this time", "INFO")
        log_message("=" * 70, "INFO")
        return 0
    
    # Attempt password renewal
    log_message("Attempting automatic renewal...", "INFO")
    if attempt_password_renewal():
        log_message("✅ Auto-renewal succeeded!", "INFO")
        log_message("=" * 70, "INFO")
        return 0
    
    # Password renewal failed - send alert
    log_message("❌ Auto-renewal failed - sending manual renewal alert", "ERROR")
    log_message("User will see RENEWAL_ALERT.txt with manual steps", "INFO")
    send_renewal_alert()
    
    log_message("=" * 70, "INFO")
    return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        log_message(f"FATAL ERROR: {e}", "CRITICAL")
        sys.exit(1)
