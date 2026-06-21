import os
import urllib.request
url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mesmerize.mp3"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        print("Success, status code:", response.getcode())
except Exception as e:
    print("Error:", e)
