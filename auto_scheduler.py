import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from main import main as run_pipeline
from pipeline.feedback_loop import (
    append_analytics_snapshot,
    append_reel_outcome,
    summarize_feedback,
    get_optimal_posting_times,
    load_used_topics,
    save_used_topic,
)
from pipeline.make_handler import retry_pending_posts, fetch_analytics_from_make, check_make_webhook_health
from pipeline.script_gen import generate_topic_from_domain


load_dotenv()


def _env_flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _get_domain():
    return (os.getenv("CONTENT_DOMAIN") or "psychology of attraction, dating secrets, horror, unsolved mysteries, and creepy facts").strip()


def _default_times_for_count(count):
    # Peak IST posting times based on account analytics:
    # 16:00 = proven best slot (Friendzone reels got 2.5K views here)
    # 19:00 = prime evening scroll | 21:00 = backup third slot
    presets = {
        1: ["19:00"],
        2: ["16:00", "19:00"],
        3: ["16:00", "19:00", "21:00"],
    }
    return presets.get(count, ["16:00", "19:00", "21:00", "21:30"][:count])


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


# TTS voice pool — Edge TTS only has 2 Hindi voices available
# Persisted across GitHub Actions runs via data/voice_index.txt
_TTS_VOICES = [
    "hi-IN-MadhurNeural",   # Male — deep, authoritative
    "hi-IN-SwaraNeural",    # Female — warm, engaging
]
_VOICE_INDEX_FILE = os.path.join("data", "voice_index.txt")


def _load_voice_index():
    """Load the current voice rotation index from disk."""
    try:
        if os.path.exists(_VOICE_INDEX_FILE):
            with open(_VOICE_INDEX_FILE, "r") as f:
                return int(f.read().strip())
    except (ValueError, OSError):
        pass
    return 0


def _save_voice_index(index):
    """Persist voice index to disk so rotation survives across runs."""
    try:
        os.makedirs(os.path.dirname(_VOICE_INDEX_FILE), exist_ok=True)
        with open(_VOICE_INDEX_FILE, "w") as f:
            f.write(str(index))
    except OSError:
        pass


def _pick_next_voice():
    """Rotate TTS voice each reel. Persisted to disk — works across GitHub Actions runs."""
    idx = _load_voice_index()
    voice = _TTS_VOICES[idx % len(_TTS_VOICES)]
    _save_voice_index(idx + 1)
    print(f"[Voice] Using TTS voice: {voice} (slot {idx % len(_TTS_VOICES) + 1}/{len(_TTS_VOICES)})")
    return voice



# ---------------------------------------------------------------------------
# Analytics failure tracking — warn when feedback loop has been broken too long
# ---------------------------------------------------------------------------
_ANALYTICS_FAIL_FILE = os.path.join("data", "analytics_fail_count.txt")


def _increment_analytics_fail_counter():
    """Increment consecutive analytics failure count and warn if too many."""
    count = 0
    try:
        if os.path.exists(_ANALYTICS_FAIL_FILE):
            with open(_ANALYTICS_FAIL_FILE, "r") as f:
                count = int(f.read().strip())
    except (ValueError, OSError):
        pass

    count += 1
    try:
        os.makedirs("data", exist_ok=True)
        with open(_ANALYTICS_FAIL_FILE, "w") as f:
            f.write(str(count))
    except OSError:
        pass

    if count >= 3:
        print(f"[Analytics] [WARN] Analytics fetch has failed {count} times in a row!")
        print("[Analytics] Your feedback loop is running on stale data.")
        print("[Analytics] Fix: Set up MAKE_ANALYTICS_WEBHOOK_URL in .env / GitHub Secrets.")
        print("[Analytics] See implementation_plan.md -> Scenario B for setup instructions.")


def _reset_analytics_fail_counter():
    """Reset the consecutive failure counter after a successful fetch."""
    try:
        if os.path.exists(_ANALYTICS_FAIL_FILE):
            os.remove(_ANALYTICS_FAIL_FILE)
    except OSError:
        pass


def _should_fetch_analytics_today() -> bool:
    """Returns True if we haven't fetched analytics today yet."""
    fetch_file = os.path.join("data", "last_analytics_fetch.txt")
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        if os.path.exists(fetch_file):
            with open(fetch_file, "r") as f:
                last_fetch = f.read().strip()
                if last_fetch == today:
                    return False
    except OSError:
        pass
        
    return True


def _mark_analytics_fetched_today():
    """Records that we fetched analytics today."""
    fetch_file = os.path.join("data", "last_analytics_fetch.txt")
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        os.makedirs("data", exist_ok=True)
        with open(fetch_file, "w") as f:
            f.write(today)
    except OSError:
        pass


def create_and_post_one_reel():
    # ✅ Retry any reels that failed to reach Make.com in a previous run
    # before spending time generating a brand-new reel.
    try:
        retried = retry_pending_posts()
        if retried:
            print(f"[Pending] {retried} previously failed reel(s) posted successfully via retry.")
    except Exception as retry_err:
        print(f"[Pending] Retry step failed (non-fatal): {retry_err}")

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            domain = _get_domain()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] Starting automated reel cycle for domain: {domain} (Attempt {attempt}/{max_retries})")

            # Health-check Make.com before spending time generating a reel
            health = check_make_webhook_health()
            if not health["healthy"]:
                print(f"[Health] [WARN] Make.com issue detected: {health['message']}")
                print("[Health] The reel will still be generated and queued, but may fail to post.")
            for k, v in health.get("details", {}).items():
                print(f"[Health] {k}: {v}")

            # Fetch live analytics only if the feature flag is on AND we haven't fetched today
            analytics_data = None
            if _env_flag("ENABLE_INSTAGRAM_ANALYTICS", "true"):
                if _should_fetch_analytics_today():
                    analytics_data = fetch_analytics_from_make()
                else:
                    print("[Analytics] Already fetched analytics today. Skipping to save Make.com credits.")
            else:
                print("Skipping Instagram analytics fetch (ENABLE_INSTAGRAM_ANALYTICS=false).")

            # Only persist real analytics — never save error strings
            if isinstance(analytics_data, list) and analytics_data:
                append_analytics_snapshot(domain, analytics_data)
                _reset_analytics_fail_counter()
                _mark_analytics_fetched_today()
            elif analytics_data is None and not _should_fetch_analytics_today():
                # We skipped fetching because we already fetched today. That's fine, no failure.
                pass
            else:
                _increment_analytics_fail_counter()
                print("[Feedback] No live data to save. Will rely on existing history for feedback.")

            # Build enriched feedback summary from all saved history
            feedback_summary = summarize_feedback(limit=30)
            if feedback_summary:
                print(f"[Feedback] History loaded: {feedback_summary.splitlines()[0]}")
            else:
                print("[Feedback] No history yet — starting fresh.")

            # Fix 1: Load used topics for deduplication
            used_topics = load_used_topics(limit=100)
            print(f"[Dedup] {len(used_topics)} topics in history — will avoid repeats.")

            # Series continuation: if feedback has a queued Part X, prioritize it
            series_topic = None
            if feedback_summary and "SERIES CONTINUATION QUEUE" in feedback_summary:
                import re
                for line in feedback_summary.splitlines():
                    clean_line = line.strip()
                    # Matches "– Part [number]:" format
                    if re.match(r'^-\s*[Pp]art\s*\d+\s*:', clean_line):
                        series_topic = clean_line.lstrip("- ").strip()
                        print(f"[Series] Auto-continuing series: {series_topic}")
                        break

            # Generate topic informed by real feedback + dedup
            # Use series continuation topic if available, otherwise generate fresh
            if series_topic and series_topic.lower() not in (t.lower() for t in used_topics):
                topic = series_topic
                print(f"[Series] Using continuation topic: {topic}")
            else:
                topic = generate_topic_from_domain(
                    domain=domain,
                    analytics_data=analytics_data,
                    feedback_summary=feedback_summary,
                    used_topics=used_topics,
                )
            print(f"Selected topic: {topic}")

            # Fix 4: Pick rotating TTS voice
            voice = _pick_next_voice()

            # Run full pipeline — pass feedback_summary + voice 
            result = run_pipeline(topic, feedback_summary=feedback_summary, tts_voice_override=voice)

            if isinstance(result, dict):
                append_reel_outcome(
                    topic=topic,
                    script_data=result.get("script") or {},
                    metadata=result.get("metadata") or {},
                )

            # Fix 1: Save used topic after successful run
            save_used_topic(topic)
            print(f"[Dedup] Topic saved to history: '{topic}'")

            print("Automated reel cycle finished successfully.")
            return  # Success!

        except Exception as e:
            print(f"\n[ERROR] Pipeline crashed on attempt {attempt}/{max_retries}: {e}")
            import traceback
            traceback.print_exc()

            if attempt < max_retries:
                print("Waiting 60 seconds before retrying from scratch...")
                time.sleep(60)
            else:
                print("[FATAL ERROR] Max retries reached. Pipeline failed permanently.")
                raise e



def run_scheduler_loop():
    reels_per_day = int(os.getenv("REELS_PER_DAY", "2"))

    # Fix 3: Use analytics-optimal times if available, else fall back to .env
    fallback_times = _read_schedule_times(reels_per_day)
    times_to_run = get_optimal_posting_times(fallback_times=fallback_times)
    # Ensure we have exactly reels_per_day slots
    times_to_run = times_to_run[:reels_per_day]
    if len(times_to_run) < reels_per_day:
        times_to_run = fallback_times[:reels_per_day]

    print(f"Scheduler configured for {reels_per_day} reels/day")
    print(f"Posting times: {times_to_run}")


    run_now = _env_flag("RUN_FIRST_REEL_NOW", "false")
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
