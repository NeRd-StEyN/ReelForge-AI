import os
import json
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

def generate_session():
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    
    if not username or not password:
        print("Please set INSTA_USERNAME and INSTA_PASSWORD in .env")
        return
        
    cl = Client()
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
    except Exception as e:
        print(f"Login failed: {e}")

if __name__ == "__main__":
    generate_session()
