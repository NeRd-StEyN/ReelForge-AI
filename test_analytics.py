import os
from dotenv import load_dotenv
from pipeline.insta_handler import get_insta_client, get_performance_data

load_dotenv()

def test_analytics():
    print("Testing Instagram login and analytics fetch...")
    cl = get_insta_client()
    if not cl:
        print("Failed to get client.")
        return
        
    data = get_performance_data(cl)
    print("----- PROOF OF ANALYTICS DATA -----")
    print(str(data).encode('unicode_escape'))
    print("-----------------------------------")

if __name__ == "__main__":
    test_analytics()
