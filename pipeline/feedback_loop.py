import json
import os
from datetime import datetime


DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "insta_analytics_history.jsonl")
USED_TOPICS_FILE = os.path.join(DATA_DIR, "used_topics.jsonl")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ── Analytics Snapshots ──────────────────────────────────────────────

def append_analytics_snapshot(domain, analytics_data):
    """Persist one analytics snapshot — only saves real list data, never error strings."""
    if not isinstance(analytics_data, list) or not analytics_data:
        print("[Feedback] Skipping snapshot save — no real analytics data to persist.")
        return

    _ensure_data_dir()
    snapshot = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "domain": domain,
        "analytics": analytics_data,
    }

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=True) + "\n")

    print(f"[Feedback] Saved analytics snapshot ({len(analytics_data)} reels) to history.")


def _read_history(limit=30):
    if not os.path.exists(HISTORY_FILE):
        return []

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarize_feedback(limit=30):
    """Build a compact summary of what style/topics are working recently."""
    rows = _read_history(limit=limit)
    if not rows:
        return ""

    posts = []
    for row in rows:
        analytics = row.get("analytics")
        if isinstance(analytics, list):
            for item in analytics:
                views = item.get("views") or 0
                likes = item.get("likes") or 0
                caption = (item.get("topic_snippet") or "").strip()
                score = views + (likes * 8)
                posts.append({
                    "caption": caption,
                    "views": views,
                    "likes": likes,
                    "score": score,
                })

    if not posts:
        return ""

    posts.sort(key=lambda x: x["score"], reverse=True)
    top = posts[:5]
    bottom = posts[-3:] if len(posts) > 5 else []

    avg_views = int(sum(p["views"] for p in posts) / len(posts))
    avg_likes = int(sum(p["likes"] for p in posts) / len(posts))

    lines = [
        f"PERFORMANCE DATA ({len(posts)} reels tracked):",
        f"Average: {avg_views} views, {avg_likes} likes per reel.",
        "",
        "TOP PERFORMING CONTENT (replicate these hooks/angles):",
    ]
    for idx, p in enumerate(top, start=1):
        snippet = p["caption"][:110] if p["caption"] else "(no caption)"
        lines.append(f"  {idx}. \"{snippet}\" → {p['views']} views, {p['likes']} likes")

    if bottom:
        lines.append("")
        lines.append("LOWEST PERFORMING CONTENT (avoid these angles):")
        for p in bottom:
            snippet = p["caption"][:80] if p["caption"] else "(no caption)"
            lines.append(f"  - \"{snippet}\" → {p['views']} views, {p['likes']} likes")

    lines.append("")
    lines.append("Use this data: create a hook similar to the top performers. Avoid the style of the bottom performers.")

    return "\n".join(lines)


# ── Fix 3: Optimal Posting Times ─────────────────────────────────────

def get_optimal_posting_times(fallback_times=None):
    """
    Analyze saved analytics history to find which posting hours get the most views.
    Returns a list of HH:MM strings for the best times to post.
    Falls back to provided default times if not enough data.
    """
    rows = _read_history(limit=60)
    fallback = fallback_times or ["11:30", "19:30"]

    if not rows:
        return fallback

    # Build hour → [view counts] mapping from snapshot timestamps
    hour_views = {}
    for row in rows:
        ts = row.get("timestamp_utc", "")
        analytics = row.get("analytics")
        if not ts or not isinstance(analytics, list):
            continue

        try:
            hour = int(ts[11:13])  # Extract hour from ISO timestamp
        except (ValueError, IndexError):
            continue

        total_views = sum(p.get("views", 0) for p in analytics)
        if hour not in hour_views:
            hour_views[hour] = []
        hour_views[hour].append(total_views)

    if not hour_views:
        return fallback

    # Compute average views per hour and rank
    avg_by_hour = {h: sum(v) / len(v) for h, v in hour_views.items()}
    sorted_hours = sorted(avg_by_hour, key=avg_by_hour.get, reverse=True)

    # Pick top N distinct hours spaced at least 3h apart
    count = len(fallback)
    chosen = []
    for h in sorted_hours:
        if all(abs(h - c) >= 3 for c in chosen):
            chosen.append(h)
        if len(chosen) == count:
            break

    if len(chosen) < count:
        # Fill remaining slots with fallback times
        return fallback

    # Convert to IST-friendly HH:MM strings (round to :00 or :30)
    chosen.sort()
    result = [f"{h:02d}:00" for h in chosen]
    print(f"[Scheduler] Optimal posting times from analytics: {result}")
    return result


# ── Fix 1: Topic Deduplication ────────────────────────────────────────

def load_used_topics(limit=100):
    """Load the most recent N used topics to avoid repetition."""
    if not os.path.exists(USED_TOPICS_FILE):
        return set()

    with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    topics = set()
    for line in lines[-limit:]:
        try:
            topics.add(json.loads(line).get("topic", "").lower().strip())
        except json.JSONDecodeError:
            continue
    return topics


def save_used_topic(topic):
    """Append a newly used topic to the deduplication log."""
    _ensure_data_dir()
    entry = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "topic": topic.strip(),
    }
    with open(USED_TOPICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
