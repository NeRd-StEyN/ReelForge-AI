import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from main import main as run_pipeline
from pipeline.feedback_loop import append_analytics_snapshot, summarize_feedback
from pipeline.insta_handler import get_insta_client, get_performance_data
from pipeline.script_gen import generate_topic_from_domain
from pipeline.topic_tracker import is_duplicate


load_dotenv()


def _env_flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _get_domain():
    return (os.getenv("CONTENT_DOMAIN") or "mysterious horror ghost girl stories and paranormal encounters").strip()


# --- Content rotation: 2 horror reels + 1 girl facts reel per day ---

def _default_schedule():
    """Default: 3 posts/day — 2 horror reels + 1 bold girl facts reel."""
    return [
        {"time": "10:00", "content_type": "horror_reel"},
        {"time": "14:00", "content_type": "girl_facts"},
        {"time": "20:00", "content_type": "horror_reel"},
    ]


def _read_schedule():
    """Read schedule from env or return defaults.
    
    REEL_SCHEDULE_TIMES format: "HH:MM:type,HH:MM:type,..."
    where type is 'story', 'horror', 'reel', or 'girl'.
    If type is omitted, defaults to 'horror_reel'.
    
    Examples:
    - "10:00:horror,14:00:girl,20:00:horror"
    - "10:00:story,14:00:reel,20:00:girl"
    """
    raw = (os.getenv("REEL_SCHEDULE_TIMES") or "").strip()
    if not raw:
        return _default_schedule()

    schedule = []
    type_map = {
        "story": "horror_story",
        "horror_story": "horror_story",
        "horror": "horror_reel",
        "horror_reel": "horror_reel",
        "reel": "horror_reel",
        "girl": "girl_facts",
        "girl_facts": "girl_facts",
        "girls": "girl_facts",
        "bold": "girl_facts",
    }

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) >= 3:
            # Format: HH:MM:type
            time_str = f"{parts[0]}:{parts[1]}"
            ctype = parts[2].strip().lower()
            content_type = type_map.get(ctype, "horror_reel")
        else:
            # Format: HH:MM (default to horror_reel)
            time_str = entry
            content_type = "horror_reel"
        schedule.append({"time": time_str, "content_type": content_type})

    if not schedule:
        return _default_schedule()
    return schedule


def create_and_post_one_reel(content_type="horror_reel"):
    domain = _get_domain()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    type_labels = {
        "horror_reel": "HORROR REEL 👻",
        "horror_story": "HORROR STORY 😱",
        "girl_facts": "GIRL FACTS 🔥",
    }
    type_label = type_labels.get(content_type, content_type.upper())
    print(f"[{now}] Starting automated {type_label} cycle for domain: {domain}")

    analytics_data = "Instagram analytics disabled by config."
    if _env_flag("ENABLE_INSTAGRAM_ANALYTICS", "false"):
        cl = get_insta_client()
        analytics_data = get_performance_data(cl)
    else:
        print("Skipping Instagram analytics login (ENABLE_INSTAGRAM_ANALYTICS=false).")

    append_analytics_snapshot(domain, analytics_data)
    feedback_summary = summarize_feedback(limit=30)

    topic = generate_topic_from_domain(
        domain=domain,
        analytics_data=analytics_data,
        feedback_summary=feedback_summary,
        content_type=content_type,
    )

    # Topic deduplication: retry up to 5 times if duplicate
    for retry in range(5):
        if not is_duplicate(topic):
            break
        print(f"Topic '{topic}' is a duplicate, regenerating... ({retry+1}/5)")
        topic = generate_topic_from_domain(
            domain=domain,
            analytics_data=analytics_data,
            feedback_summary=feedback_summary,
            content_type=content_type,
        )

    print(f"Selected topic ({type_label}): {topic}")

    run_pipeline(topic, content_type=content_type)
    print(f"Automated {type_label} cycle finished.")


def run_scheduler_loop():
    schedule = _read_schedule()

    print(f"Scheduler configured for {len(schedule)} posts/day")
    type_icons = {"horror_reel": "👻 HORROR REEL", "horror_story": "😱 HORROR STORY", "girl_facts": "🔥 GIRL FACTS"}
    for slot in schedule:
        label = type_icons.get(slot["content_type"], slot["content_type"])
        print(f"  {slot['time']} -> {label}")

    run_now = (os.getenv("RUN_FIRST_REEL_NOW", "true").strip().lower() == "true")
    if run_now:
        # Run the first scheduled content type immediately
        first_type = schedule[0]["content_type"] if schedule else "horror_reel"
        create_and_post_one_reel(content_type=first_type)

    last_run_by_time = {}
    print("Scheduler running. Press Ctrl+C to stop.")
    while True:
        now = datetime.now()
        now_hhmm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")

        for slot in schedule:
            run_time = slot["time"]
            content_type = slot["content_type"]
            already_ran_today = last_run_by_time.get(run_time) == today
            if now_hhmm == run_time and not already_ran_today:
                create_and_post_one_reel(content_type=content_type)
                last_run_by_time[run_time] = today

        time.sleep(20)


def run_immediate_batch(count):
    """Run batch: follows the schedule pattern (horror, girl, horror, repeat)."""
    schedule = _read_schedule()
    print(f"Running immediate batch: {count} posts")
    for idx in range(count):
        slot = schedule[idx % len(schedule)]
        content_type = slot["content_type"]
        type_labels = {"horror_reel": "HORROR REEL", "horror_story": "HORROR STORY", "girl_facts": "GIRL FACTS"}
        label = type_labels.get(content_type, content_type)
        print(f"\n--- Post {idx+1}/{count} ({label}) ---")
        create_and_post_one_reel(content_type=content_type)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automate mixed horror + girl facts Reel creation/posting with feedback loop."
    )
    parser.add_argument(
        "--mode",
        choices=["scheduler", "batch"],
        default="scheduler",
        help="scheduler: run daily at scheduled times, batch: run N posts immediately",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="How many posts to run immediately in batch mode (default: 3 = 2 horror + 1 girl facts)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.mode == "batch":
        run_immediate_batch(max(1, args.count))
    else:
        run_scheduler_loop()
