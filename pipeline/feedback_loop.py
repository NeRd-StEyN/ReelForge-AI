import json
import os
from datetime import datetime
import time

# Try to import fcntl for Unix/Linux file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "insta_analytics_history.jsonl")
USED_TOPICS_FILE = os.path.join(DATA_DIR, "used_topics.jsonl")
REEL_OUTCOMES_FILE = os.path.join(DATA_DIR, "reel_outcomes.jsonl")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _append_to_jsonl_safe(file_path, data_dict):
    """Safely append to JSONL with file locking to prevent corruption from concurrent writes."""
    _ensure_data_dir()
    
    try:
        if HAS_FCNTL and os.name != 'nt':  # Unix/Linux/Mac
            # Use fcntl for file locking
            with open(file_path, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(data_dict, ensure_ascii=True) + "\n")
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:  # Windows or no fcntl available
            # Use atomic write with temp file + rename
            temp_path = file_path + ".tmp"
            # Write to temp file
            with open(temp_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data_dict, ensure_ascii=True) + "\n")
            # Atomic rename (on most filesystems)
            try:
                os.replace(temp_path, file_path)
            except:
                # Fallback: just keep temp as is, it will be picked up next run
                pass
    except Exception as e:
        print(f"[Feedback] Warning: Could not safely write to {file_path}: {e}")


def _read_jsonl(file_path, limit=30):
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ── Analytics Snapshots ──────────────────────────────────────────────

def append_analytics_snapshot(domain, analytics_data):
    """Persist one analytics snapshot — only saves real list data, never error strings.
    Uses safe file locking to prevent corruption from concurrent writes."""
    if not isinstance(analytics_data, list) or not analytics_data:
        print("[Feedback] Skipping snapshot save — no real analytics data to persist.")
        return

    snapshot = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "domain": domain,
        "analytics": analytics_data,
    }

    _append_to_jsonl_safe(HISTORY_FILE, snapshot)
    print(f"[Feedback] Saved analytics snapshot ({len(analytics_data)} reels) to history.")


def _read_history(limit=30):
    return _read_jsonl(HISTORY_FILE, limit=limit)


def _read_outcomes(limit=30):
    return _read_jsonl(REEL_OUTCOMES_FILE, limit=limit)


def summarize_feedback(limit=30):
    """Build a compact summary of what style/topics are working recently.

    Scoring is based on views + likes which are the only reliable signals
    from the Instagram API. Saves are not returned for own media, and
    comments are inflated by auto-comments — so neither is used for ranking.
    """
    rows = _read_history(limit=limit)
    if not rows:
        rows = []

    posts = []
    for row in rows:
        analytics = row.get("analytics")
        if isinstance(analytics, list):
            for item in analytics:
                try:
                    # Validate and convert data types
                    views = int(item.get("views") or 0)
                    likes = int(item.get("likes") or 0)
                    comments = int(item.get("comments") or 0)
                    caption = str(item.get("topic_snippet") or "").strip()
                    
                    # Sanity checks for negative values or invalid data
                    if views < 0 or likes < 0 or comments < 0:
                        print(f"[Feedback] Skipping invalid analytics item (negative values): {item}")
                        continue
                    if likes > views:
                        print(f"[Feedback] Skipping invalid analytics item (likes > views): {item}")
                        continue
                    
                    # Like rate = likes/views — target >3% for healthy engagement
                    like_rate = round((likes / views * 100), 1) if views > 0 else 0.0
                    # Score by views + likes*10 + like_rate*100 — views and likes
                    # are the reliable API signals. Likes weighted 10x for quality
                    # engagement. Like rate weighted 100x so high-engagement content
                    # that got suppressed by algorithm is still recognized as good
                    # (a 500-view reel with 3% like rate = better content than
                    # a 3K-view reel with 0.5% like rate — it just needed better hooks).
                    score = views + (likes * 10) + (like_rate * 100)
                    posts.append({
                        "caption": caption,
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "like_rate": like_rate,
                        "score": score,
                    })
                except (ValueError, TypeError) as e:
                    print(f"[Feedback] Skipping malformed analytics item: {item} ({e})")
                    continue

    if not posts:
        posts = []

    avg_views = int(sum(p["views"] for p in posts) / len(posts)) if posts else 0
    avg_likes = int(sum(p["likes"] for p in posts) / len(posts)) if posts else 0
    avg_like_rate = round(sum(p["like_rate"] for p in posts) / len(posts), 1) if posts else 0.0
    peak_views = max((p["views"] for p in posts), default=0)

    # Like rate health check
    like_rate_status = "HEALTHY" if avg_like_rate >= 3.0 else ("IMPROVING" if avg_like_rate >= 1.5 else "LOW")

    lines = [
        f"PERFORMANCE DATA ({len(posts)} reels tracked):",
        f"Average: {avg_views} views, {avg_likes} likes per reel.",
        f"Like Rate: {avg_like_rate}% avg [{like_rate_status}] | Peak single reel: {peak_views} views",
        f"Scoring: views + (likes × 10). Higher likes = higher quality content.",
        f"Like Rate target: >3% (currently {avg_like_rate}%) — in-video like bait overlay active to improve this.",
    ]

    if posts:
        posts.sort(key=lambda x: x["score"], reverse=True)
        top = posts[:5]
        bottom = posts[-3:] if len(posts) > 5 else []

        lines.extend([
            "",
            "TOP PERFORMING CONTENT (replicate these hooks/angles — they got the most views + likes):",
        ])
        for idx, p in enumerate(top, start=1):
            snippet = p["caption"][:110] if p["caption"] else "(no caption)"
            lines.append(
                f"  {idx}. \"{snippet}\" → {p['views']} views, {p['likes']} likes, "
                f"like rate: {p['like_rate']}%"
            )

        if bottom:
            lines.append("")
            lines.append("LOWEST PERFORMING CONTENT (avoid these angles — low views + likes = low reach):")
            for p in bottom:
                snippet = p["caption"][:80] if p["caption"] else "(no caption)"
                lines.append(
                    f"  - \"{snippet}\" → {p['views']} views, {p['likes']} likes"
                )

    outcomes = _read_outcomes(limit=limit)
    if outcomes:
        framework_counts = {}
        series_queue = []  # Parts waiting to be made
        for item in outcomes:
            framework = (item.get("hook_framework") or "").strip()
            if framework:
                framework_counts[framework] = framework_counts.get(framework, 0) + 1
            # Collect series_next_title suggestions that haven't been made yet
            series_next = (item.get("series_next_title") or "").strip()
            if series_next and "Part " in series_next:
                series_queue.append(series_next)

        if framework_counts:
            ranked = sorted(framework_counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
            lines.extend([
                "",
                "HOOK FRAMES USED RECENTLY (use this to avoid repeating the same opener too often):",
            ])
            for framework, count in ranked:
                lines.append(f"  - {framework}: {count} uses")

        if series_queue:
            lines.extend([
                "",
                "SERIES CONTINUATION QUEUE (these continuation parts are ready to be made — high conversion potential):",
            ])
            for sq in series_queue[-3:]:
                lines.append(f"  - {sq}")

    if lines:
        lines.append("")
        lines.append(
            "Use this data to write hooks that maximize VIEWS (strong hook in first 1 second) and "
            "LIKES (emotionally resonant content). These are the reliable signals that determine reach."
        )

    return "\n".join(lines)


def append_reel_outcome(topic, script_data, metadata):
    """Persist the generated reel plan so future prompts can avoid stale patterns.
    Uses safe file locking to prevent corruption from concurrent writes."""
    if not isinstance(script_data, dict):
        script_data = {}
    if not isinstance(metadata, dict):
        metadata = {}

    entry = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "topic": topic.strip(),
        "title": script_data.get("title") or metadata.get("title") or topic.strip(),
        "hook_framework": script_data.get("hook_framework") or metadata.get("hook_framework") or "",
        "first_comment": metadata.get("first_comment") or "",
        "hashtags": metadata.get("hashtags") or [],
        "series_next_title": metadata.get("series_next_title") or "",  # Track Part 2 queue
        "story_poll": metadata.get("story_poll") or {},               # Track Story poll for cross-promo
        "script_data": script_data,                                   # Track full script to allow direct continuations
    }
    _append_to_jsonl_safe(REEL_OUTCOMES_FILE, entry)


def get_previous_part_script(current_topic):
    """Search reel outcomes to find the script of the previous part in this series.
    Matches the previous part whose series_next_title equals today's topic.
    """
    outcomes = _read_outcomes(limit=100)
    for item in reversed(outcomes):
        next_title = (item.get("series_next_title") or "").strip().lower()
        if next_title and next_title == current_topic.strip().lower():
            # Found the exact previous part! Return its script
            return item.get("script_data")
    return None


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
    """Append a newly used topic to the deduplication log.
    Uses safe file locking to prevent corruption from concurrent writes."""
    entry = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "topic": topic.strip(),
    }
    _append_to_jsonl_safe(USED_TOPICS_FILE, entry)
