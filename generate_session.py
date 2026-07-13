import os
import json
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

def generate_session():
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    
    print("How would you like to login?")
    print("1. Standard Password Login")
    print("2. Bypass Challenge (using browser sessionid)")
    choice = input("Enter 1 or 2: ").strip()
    
    cl = Client()
    
    if choice == "2":
        print("\n--- BROWSER BYPASS METHOD ---")
        print("1. Go to instagram.com in Chrome and login.")
        print("2. Press F12 -> Application -> Cookies -> https://www.instagram.com")
        print("3. Copy the value of the 'sessionid' cookie.")
        sessionid = input("\nPaste sessionid here: ").strip()
        
        try:
            print(f"Generating full session via browser cookie...")
            cl.login_by_sessionid(sessionid)
            
            session_file = "insta_session.json"
            cl.dump_settings(session_file)
            print(f"\nSUCCESS! Session saved to {session_file}")
            print("\n--- NEXT STEPS ---")
            print("1. Open insta_session.json in a text editor.")
            print("2. Copy ALL of the text inside.")
            print("3. Go to GitHub -> Settings -> Secrets -> Actions")
            print("4. Create a new Repository Secret named: INSTA_SESSION")
            print("5. Paste the text into the Secret value and save.")
            return
        except Exception as e:
            print(f"Failed to generate session from browser cookie: {e}")
            return

    if not username or not password:
        print("Please set INSTA_USERNAME and INSTA_PASSWORD in .env")
        return
        
    print(f"\nLogging in to Instagram as {username} (using your local IP)...")
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
