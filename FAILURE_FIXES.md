# ReelForge-AI: Auto Story Upload & Feedback Loop Failure Analysis & Fixes

## Executive Summary

The pipeline has **two main failure points**:
1. **Auto Story Upload** fails due to Instagram session authentication issues
2. **Feedback Loop** fails due to analytics fetch timeouts and concurrent file writes

This document provides detailed root causes and fixes.

---

## Problem 1: Auto Story Upload Failing

### ⚠️ CRITICAL: Instagram Blocks Session ID Logins

**Severity:** 🔴 CRITICAL  
**Location:** `pipeline/insta_handler.py` (`get_insta_client()`)

**Problem:**
Instagram has **blocked session ID-only logins** as a security measure. A single sessionid cookie is insufficient for authentication. This was the root cause of all story upload failures.

**What doesn't work:**
- `INSTA_SESSION_ID` (single session cookie) — **BLOCKED BY INSTAGRAM**
- Password login on GitHub Actions — frequently blocked due to IP reputation

**What DOES work:**
- **Full session file** (insta_session.json) — contains complete auth context

**Solution:**

The session file must be regenerated on your local machine and stored as a GitHub Secret:

```bash
# Step 1: Run on your LOCAL machine (not GitHub Actions)
python generate_session.py

# Step 2: Copy the output JSON
# Step 3: Go to GitHub repo → Settings → Secrets and variables → Actions
# Step 4: Create secret named: INSTA_SESSION
# Step 5: Paste the JSON output as the secret value
```

The workflow already writes this to insta_session.json:
```yaml
- name: Write Instagram session file
  if: env.INSTA_SESSION != ''
  run: echo "$INSTA_SESSION" > insta_session.json
```

**Session Expiration:**
- Session files expire after **~30 days** of inactivity
- You must regenerate every 30 days using `python generate_session.py`
- Set a calendar reminder to regenerate monthly

**Updated Fix:**
```python
def get_insta_client():
    """Logs into Instagram and returns the client using session persistence.

    IMPORTANT: Instagram blocks session ID-only logins as a security measure.
    The ONLY reliable method on GitHub Actions is the full session file.

    Login priority:
      1. insta_session.json  — full session file from INSTA_SESSION secret.
                               Only reliable method that works on GitHub Actions.
      2. Password login      — fallback; often blocked on cloud IPs by Instagram.
    """

#### 1B. user_id Lookup Rate Limiting
**Severity:** 🔴 CRITICAL  
**Location:** `pipeline/insta_handler.py:282-290`

**Problem:**
```python
user_id = cl.user_id  # Often None after session load!
if not user_id:
    user_id = cl.user_id_from_username(username)  # ← This hits rate limit (429 error)
```

When `cl.user_id` is None (common after session load), the fallback calls Instagram's public API which is heavily rate-limited on GitHub Actions IPs.

**Fix:**
```python
# In pipeline/insta_handler.py, replace lines 282-290:

def _get_safe_user_id(cl, username, max_retries=3):
    """Get user_id with retry logic for rate limiting."""
    user_id = cl.user_id
    if user_id:
        return user_id
    
    # Fallback with exponential backoff
    for attempt in range(max_retries):
        try:
            print(f"[Story] Falling back to username lookup (attempt {attempt+1}/{max_retries})...")
            user_id = cl.user_id_from_username(username)
            if user_id:
                return user_id
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    print(f"[Story] Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
            else:
                raise
    
    raise Exception(f"Could not get user_id for {username} after {max_retries} attempts")

# Usage in wait_and_share_reel_to_story():
user_id = _get_safe_user_id(cl, username)
```

#### 1C. Poll Story Posting Crashes Entire Story Upload
**Severity:** 🟠 HIGH  
**Location:** `pipeline/insta_handler.py:200-210` (`post_poll_story()`)

**Problem:**
If poll story posting fails, the entire story flow is considered failed:
```python
# In _share_reel_to_story() lines 241-244:
if story_poll:
    import time
    time.sleep(3)
    post_poll_story(cl, thumbnail_path, story_poll)  # ← If this throws, story posting marked as failed
```

Also, poll options are limited to 20 chars but code doesn't enforce:
```python
opt1 = story_poll.get("option_1", "Haan 🔥").strip()[:20]  # Line 156 — truncates but doesn't warn
```

**Fix:**
```python
# In _share_reel_to_story(), wrap poll posting in try-catch:

def _share_reel_to_story(cl, post, thumbnail_path, story_poll=None):
    """Attempt to share a reel post to story. Returns True on success.
    If story_poll is provided, also posts a follow-up poll story slide.
    """
    try:
        try:
            if thumbnail_path and os.path.exists(thumbnail_path):
                cl.media_share_to_story(post.pk, background=thumbnail_path)
            else:
                cl.media_share_to_story(post.pk)
        except Exception as bg_exc:
            print(f"[Story] media_share_to_story with background failed: {bg_exc}. Retrying without background...")
            cl.media_share_to_story(post.pk)
        print("[Story] Successfully posted Story promotion! 🚀")

        # Post poll slide immediately after the reel share card
        if story_poll:
            import time
            time.sleep(3)
            try:
                post_poll_story(cl, thumbnail_path, story_poll)
            except Exception as poll_err:
                # Don't fail the entire story posting if poll fails
                print(f"[Poll] ⚠️ Poll story posting failed (non-fatal): {poll_err}")
                print("[Poll] Main reel story was posted successfully. Poll story skipped.")

        return True
    except Exception as story_exc:
        print(f"[Story] Failed sharing to story: {story_exc}")
        return False
```

#### 1D. Story Reel Wait Timeout (25 minutes)
**Severity:** 🟡 MEDIUM  
**Location:** `pipeline/insta_handler.py:251-360` (`wait_and_share_reel_to_story()`)

**Problem:**
Function waits up to 25 minutes for reel to appear. If it doesn't, silently returns False:
- Make.com webhook may queue the upload
- Reel processing takes time
- But no logging of what went wrong

**Fix:**
Add more detailed logging and adjustable timeout:

```python
# In wait_and_share_reel_to_story(), change function signature:
def wait_and_share_reel_to_story(
    cl, username, expected_title, thumbnail_path, 
    story_poll=None, 
    max_wait_seconds=1500,  # Keep default
    fallback_after_seconds=900  # ← Make configurable
):
    """
    Args:
        fallback_after_seconds: Time before switching to recency fallback (default 15 min)
            Set to 0 to skip fuzzy match and go straight to recency
    """
    # ... existing code ...
    FALLBACK_AFTER_SECONDS = fallback_after_seconds  # ← Use parameter
    
    # Also add this after timeout:
    print(f"[Story] ❌ Timeout reached ({max_wait_seconds}s). Reel was not detected.")
    print(f"[Story] Possible causes:")
    print(f"  1. Make.com webhook failed or is still processing")
    print(f"  2. Title doesn't match (expected: '{expected_title}')")
    print(f"  3. Instagram API is rate-limited (429 errors)")
    print(f"  4. Session expired during wait")
```

---

## Problem 2: Feedback Loop Failing

### Root Causes

#### 2A. Concurrent JSONL File Writes Cause Corruption
**Severity:** 🔴 CRITICAL  
**Location:** `pipeline/feedback_loop.py:38-50` (`append_analytics_snapshot()`)

**Problem:**
Multiple GitHub Actions runs may write to the same `.jsonl` files simultaneously:
```python
# Line 47-49: No file locking!
with open(HISTORY_FILE, "a", encoding="utf-8") as f:
    f.write(json.dumps(snapshot, ensure_ascii=True) + "\n")
```

If two runs append simultaneously, lines may interleave or corrupt.

**Fix:**
```python
# In pipeline/feedback_loop.py, add file locking:

import fcntl  # Linux/Mac
import os

def _append_to_jsonl_safe(file_path, data_dict):
    """Safely append to JSONL with file locking."""
    _ensure_data_dir()
    
    try:
        # On Windows, use os.rename() atomic operation as workaround
        if os.name == 'nt':  # Windows
            # Write to temp file first
            temp_path = file_path + ".tmp"
            with open(temp_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data_dict, ensure_ascii=True) + "\n")
            # Atomic rename on Windows
            try:
                os.remove(file_path)  # In case it doesn't support atomic replacement
            except:
                pass
            os.rename(temp_path, file_path)
        else:  # Unix/Linux/Mac
            with open(file_path, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(data_dict, ensure_ascii=True) + "\n")
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        print(f"[Feedback] Warning: Could not write to {file_path}: {e}")

# Replace all append_analytics_snapshot() body:
def append_analytics_snapshot(domain, analytics_data):
    """Persist one analytics snapshot — only saves real list data, never error strings."""
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
```

#### 2B. Analytics Fetch Timeouts
**Severity:** 🔴 CRITICAL  
**Location:** `pipeline/insta_handler.py:96-110` (`get_performance_data()`)

**Problem:**
`cl.user_medias()` may hang indefinitely on slow GitHub Actions runners:
```python
# Line 103: No timeout!
recent_posts = cl.user_medias(user_id, amount=20)
```

If this times out, entire feedback loop fails.

**Fix:**
```python
# In pipeline/insta_handler.py, add timeout handling:

import signal
import threading

def _get_medias_with_timeout(cl, user_id, amount=20, timeout_seconds=30):
    """Fetch medias with timeout."""
    result = [None]  # Use list to allow modification in inner function
    exception = [None]
    
    def fetch():
        try:
            result[0] = cl.user_medias(user_id, amount=amount)
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=fetch, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        raise TimeoutError(f"user_medias() exceeded {timeout_seconds}s timeout")
    
    if exception[0]:
        raise exception[0]
    
    return result[0]

# In get_performance_data(), replace cl.user_medias() call:
try:
    recent_posts = _get_medias_with_timeout(cl, user_id, amount=20, timeout_seconds=30)
except TimeoutError as e:
    print(f"[Analytics] Timeout fetching medias: {e}")
    print("[Analytics] Will skip live analytics this run and use saved history.")
    return None
```

#### 2C. Invalid Analytics Data Crashes Feedback Summarization
**Severity:** 🟡 MEDIUM  
**Location:** `pipeline/feedback_loop.py:75-150`

**Problem:**
If analytics data has missing/malformed fields, summarize_feedback() crashes:
```python
# Line 100: No null check!
views = item.get("views") or 0
likes = item.get("likes") or 0
```

If `item.get()` returns unexpected type, calculations fail.

**Fix:**
```python
# In pipeline/feedback_loop.py, add validation in summarize_feedback():

def summarize_feedback(limit=30):
    """Build a compact summary..."""
    rows = _read_history(limit=limit)
    if not rows:
        rows = []

    posts = []
    for row in rows:
        analytics = row.get("analytics")
        if isinstance(analytics, list):
            for item in analytics:
                try:
                    # Validate data types
                    views = int(item.get("views") or 0)
                    likes = int(item.get("likes") or 0)
                    comments = int(item.get("comments") or 0)
                    caption = str(item.get("topic_snippet") or "").strip()
                    
                    if views < 0 or likes < 0:  # Sanity check
                        continue
                    
                    like_rate = round((likes / views * 100), 1) if views > 0 else 0.0
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
    
    # Rest of function...
```

---

## Problem 3: GitHub Actions Workflow Issues

### Root Causes

#### 3A. Cache May Not Restore Properly
**Severity:** 🟡 MEDIUM  
**Location:** `.github/workflows/auto-reels.yml:32-39`

**Problem:**
If cache key doesn't match, data files aren't restored:
```yaml
restore-keys: |
  reelforge-data-${{ github.ref_name }}-
```

This key includes `github.run_id` which is unique per run, so cache never hits on second run.

**Fix:**
```yaml
# In .github/workflows/auto-reels.yml, change cache key:

- name: Restore feedback history cache
  uses: actions/cache/restore@v4
  with:
    path: |
      data/insta_analytics_history.jsonl
      data/pexels_used_ids.json
      data/used_topics.jsonl
      data/reel_outcomes.jsonl
      data/voice_index.txt
      data/pending_posts.jsonl
    key: reelforge-data-${{ github.ref_name }}  # ← Remove run_id for stable key
    restore-keys: |
      reelforge-data-

- name: Save feedback history cache
  if: always()
  uses: actions/cache/save@v4
  with:
    path: |
      data/insta_analytics_history.jsonl
      data/pexels_used_ids.json
      data/used_topics.jsonl
      data/reel_outcomes.jsonl
      data/voice_index.txt
      data/pending_posts.jsonl
    key: reelforge-data-${{ github.ref_name }}  # ← Same key for consistent saves
```

#### 3B. No Error Handling for Failed Uploads
**Severity:** 🟡 MEDIUM  
**Location:** `.github/workflows/auto-reels.yml:77`

**Problem:**
If `auto_scheduler.py` fails, GitHub Actions reports failure but doesn't capture error details.

**Fix:**
```yaml
- name: Generate and post one reel
  run: |
    python auto_scheduler.py --mode batch --count 1 2>&1 | tee -a run_logs.txt
  continue-on-error: false  # ← Explicit: fail on error
  
- name: Upload logs on failure
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: run-logs-failure
    path: run_logs.txt
    retention-days: 7
```

---

## Implementation Order

1. **Immediate (Today):**
   - ✅ Fix 1A: Add session validation
   - ✅ Fix 1B: Add user_id retry logic
   - ✅ Fix 1C: Wrap poll story in try-catch
   - ✅ Fix 2A: Add file locking to JSONL writes
   - ✅ Fix 2B: Add timeout to analytics fetch
   - ✅ Fix 3A: Fix GitHub Actions cache key

2. **Short-term (This week):**
   - ✅ Fix 1D: Better timeout logging
   - ✅ Fix 2C: Add data validation in feedback summarization
   - ✅ Fix 3B: Add error logging to workflow

3. **Long-term (Nice to have):**
   - Add monitoring/alerting dashboard
   - Implement retry queues for failed uploads
   - Add analytics to track failure rates by type

---

## Testing Checklist

After implementing fixes:
- [ ] Run `python auto_scheduler.py --mode batch --count 1` locally
- [ ] Verify story posts within 30 seconds
- [ ] Verify poll story appears after reel story
- [ ] Run second batch and verify cache works
- [ ] Trigger GitHub Actions workflow and check logs
- [ ] Let workflow run for 3-5 cycles to test feedback loop

