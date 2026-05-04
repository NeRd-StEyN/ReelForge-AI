import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from main import main as run_pipeline
from pipeline.feedback_loop import append_analytics_snapshot, summarize_feedback
from pipeline.insta_handler import get_insta_client, get_performance_data
from pipeline.script_gen import generate_topic_from_domain


load_dotenv()


def _env_flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _get_domain():
    return (os.getenv("CONTENT_DOMAIN") or "girl psychology and dating secrets").strip()


def _default_times_for_count(count):
    presets = {
        1: ["12:00"],
        2: ["10:00", "19:00"],
        3: ["09:00", "14:00", "20:00"],
    }
    return presets.get(count, ["09:00", "13:00", "17:00", "21:00"][:count])


def _read_schedule_times(reels_per_day):
    raw = (os.getenv("REEL_SCHEDULE_TIMES") or "").strip()
    if not raw:
        return _default_times_for_count(reels_per_day)

    times = [t.strip() for t in raw.split(",") if t.strip()]
    if len(times) < reels_per_day:
        defaults = _default_times_for_count(reels_per_day)
        for t in defaults:
            if t not in times:
                times.append(t)
            if len(times) == reels_per_day:
                break

    return times[:reels_per_day]


def create_and_post_one_reel():
    domain = _get_domain()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Starting automated reel cycle for domain: {domain}")

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
    )
    print(f"Selected topic: {topic}")

    run_pipeline(topic)
    print("Automated reel cycle finished.")


def run_scheduler_loop():
    reels_per_day = int(os.getenv("REELS_PER_DAY", "2"))
    times_to_run = _read_schedule_times(reels_per_day)

    print(f"Scheduler configured for {reels_per_day} reels/day")
    print(f"Posting times: {times_to_run}")

    run_now = (os.getenv("RUN_FIRST_REEL_NOW", "true").strip().lower() == "true")
    if run_now:
        create_and_post_one_reel()

    last_run_by_time = {}
    print("Scheduler running. Press Ctrl+C to stop.")
    while True:
        now = datetime.now()
        now_hhmm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")

        for run_time in times_to_run:
            already_ran_today = last_run_by_time.get(run_time) == today
            if now_hhmm == run_time and not already_ran_today:
                create_and_post_one_reel()
                last_run_by_time[run_time] = today

        time.sleep(20)


def run_immediate_batch(count):
    print(f"Running immediate batch: {count} reels")
    for idx in range(1, count + 1):
        print(f"\n--- Reel {idx}/{count} ---")
        create_and_post_one_reel()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automate domain-focused Reel creation/posting with feedback loop."
    )
    parser.add_argument(
        "--mode",
        choices=["scheduler", "batch"],
        default="scheduler",
        help="scheduler: run daily at scheduled times, batch: run N reels immediately",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=2,
        help="How many reels to run immediately in batch mode",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.mode == "batch":
        run_immediate_batch(max(1, args.count))
    else:
        run_scheduler_loop()
