try:
    import google.generativeai
    print("✅ google-generativeai installed")
except ImportError:
    print("❌ google-generativeai NOT installed")

try:
    import edge_tts
    print("✅ edge-tts installed")
except ImportError:
    print("❌ edge-tts NOT installed")

try:
    import moviepy
    print(f"✅ moviepy installed (version {moviepy.__version__})")
except ImportError:
    print("❌ moviepy NOT installed")

try:
    import requests
    print("✅ requests installed")
except ImportError:
    print("❌ requests NOT installed")

try:
    from dotenv import load_dotenv
    print("✅ python-dotenv installed")
except ImportError:
    print("❌ python-dotenv NOT installed")
