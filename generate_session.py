import os
import json
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired
from instagrapi.mixins.challenge import ChallengeChoice
from dotenv import load_dotenv

load_dotenv()

def challenge_code_handler(username, choice):
    """
    Handles Instagram verification challenges (SMS/Email code)
    by prompting the user in the terminal.
    """
    print(f"\nVerification required for @{username}!")
    
    if choice == ChallengeChoice.SMS:
        print("Instagram is sending a code via SMS.")
    elif choice == ChallengeChoice.EMAIL:
        print("Instagram is sending a code via EMAIL.")
    else:
        print(f"Instagram is sending a code via: {choice}")
        
    code = input("Enter the verification code you received: ").strip()
    return code

def change_password_handler(username):
    """Fallback handler in case Instagram forces a password change."""
    print(f"\nInstagram is requesting a password change for @{username}!")
    new_password = input("Enter a new password to set: ").strip()
    return new_password

def generate_session():
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    
    if not username or not password:
        print("Please set INSTA_USERNAME and INSTA_PASSWORD in .env")
        return
        
    cl = Client()
    # Register the interactive handlers
    cl.challenge_code_handler = challenge_code_handler
    cl.change_password_handler = change_password_handler
    
    print(f"Logging in to Instagram as {username} (using your local IP)...")
    try:
        cl.login(username, password)
        session_file = "insta_session.json"
        cl.dump_settings(session_file)
        print(f"\nSUCCESS! Session saved to {session_file}")
        print("\n--- NEXT STEPS ---")
        print("1. Open insta_session.json in a text editor.")
        print("2. Copy ALL of the text inside.")
        print("3. Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions")
        print("4. Create a new Repository Secret named: INSTA_SESSION")
        print("5. Paste the text into the Secret value and save.")
        print("\nImportant: DO NOT commit insta_session.json to GitHub!")
    except ChallengeRequired as e:
        print(f"\nChallenge encountered. Trying to resolve using registered handler...")
        try:
            cl.challenge_resolve(cl.last_json)
            # Try logging in again after resolving
            cl.login(username, password)
            session_file = "insta_session.json"
            cl.dump_settings(session_file)
            print(f"\nSUCCESS! Session saved to {session_file} after challenge resolution.")
        except Exception as resolve_err:
            print(f"Failed to resolve challenge: {resolve_err}")
    except Exception as e:
        print(f"Login failed: {e}")

if __name__ == "__main__":
    generate_session()
