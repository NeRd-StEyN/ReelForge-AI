import json
import os
from datetime import datetime


DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "insta_analytics_history.jsonl")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def append_analytics_snapshot(domain, analytics_data):
    """Persist one analytics snapshot so strategy can improve over time."""
    _ensure_data_dir()

    snapshot = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "domain": domain,
        "analytics": analytics_data,
    }

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=True) + "\n")


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
        return "No historical analytics snapshots yet."

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
        return "Historical snapshots exist but no reel metrics were available."

    posts.sort(key=lambda x: x["score"], reverse=True)
    top = posts[:5]

    avg_views = int(sum(p["views"] for p in posts) / len(posts))
    avg_likes = int(sum(p["likes"] for p in posts) / len(posts))

    lines = [
        f"Recent sample size: {len(posts)} reels",
        f"Average views: {avg_views}",
        f"Average likes: {avg_likes}",
        "Top performing caption snippets:",
    ]

    for idx, p in enumerate(top, start=1):
        snippet = p["caption"][:100] if p["caption"] else "(no caption text)"
        lines.append(
            f"{idx}. {snippet} | views={p['views']} likes={p['likes']} score={p['score']}"
        )

    return "\n".join(lines)
