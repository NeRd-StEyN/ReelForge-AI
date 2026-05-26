"""Track used topics to avoid repetition across runs."""
import os
import json
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TOPIC_LOG = os.path.join(DATA_DIR, "used_topics.json")


def _load():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(TOPIC_LOG):
        with open(TOPIC_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save(entries):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOPIC_LOG, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def save_topic(topic, content_type="horror_reel"):
    entries = _load()
    entries.append({
        "topic": topic,
        "content_type": content_type,
        "timestamp": datetime.now().isoformat(),
    })
    # Keep last 200 entries
    _save(entries[-200:])


def get_recent_topics(limit=50):
    return [e["topic"] for e in _load()[-limit:]]


def is_duplicate(topic):
    """Check if topic is too similar to a recent one (simple substring match)."""
    topic_lower = topic.strip().lower()
    for past in get_recent_topics(60):
        past_lower = past.strip().lower()
        # Exact or near-exact match
        if topic_lower == past_lower:
            return True
        # Check if 80%+ of words overlap
        t_words = set(topic_lower.split())
        p_words = set(past_lower.split())
        if len(t_words) > 2 and len(p_words) > 2:
            overlap = len(t_words & p_words) / max(len(t_words), len(p_words))
            if overlap >= 0.8:
                return True
    return False
