import json
import os
from datetime import datetime


DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "insta_analytics_history.jsonl")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def append_analytics_snapshot(domain, analytics_data):
    """Persist one analytics snapshot — only saves real list data, never error strings."""
    # Guard: only save when analytics_data is a real non-empty list of post metrics
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
