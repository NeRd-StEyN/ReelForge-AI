# 🔧 IMMEDIATE FIX: Story Upload & Feedback Loop

## Root Cause

**Instagram blocks session ID-only logins.** The pipeline needs a full session file stored as GitHub Secret `INSTA_SESSION`.

---

## ✅ What You Need to Do RIGHT NOW

### Step 1: Generate Fresh Session (5 minutes)

On your **local machine**, run:

```bash
cd c:\Users\43ner\Desktop\ReelForge-AI
python generate_session.py
```

**Expected:** Large JSON output in console

### Step 2: Copy the JSON

Select all output from `{` to `}` and copy to clipboard

### Step 3: Update GitHub Secret (2 minutes)

1. Go to: `https://github.com/YOUR-USERNAME/ReelForge-AI/settings/secrets/actions`
2. Find secret: `INSTA_SESSION`
3. Click **"Update"**
4. Paste the JSON
5. Click **"Update secret"**

**If secret doesn't exist:**
1. Click **"New repository secret"**
2. Name: `INSTA_SESSION`
3. Value: Paste JSON
4. Click **"Add secret"**

### Step 4: Verify Setup (1 minute)

Check workflow can access it:

In `.github/workflows/auto-reels.yml`, the secret is used here:

```yaml
- name: Write Instagram session file
  if: env.INSTA_SESSION != ''
  run: echo "$INSTA_SESSION" > insta_session.json
```

---

## Testing

After updating the secret:

1. Go to GitHub repo → **Actions** tab
2. Click **Auto Reels** workflow
3. Click **"Run workflow"** → **"Run workflow"** again
4. Wait 2-3 minutes
5. Check logs for:
   - ✅ `[Analytics] ✅ Session validation passed`
   - ✅ `[Story] Successfully posted Story promotion! 🚀`

If you see these, story upload is **FIXED**.

---

## Future: Monthly Renewal

**Set reminder for 1st of each month:**

```bash
python generate_session.py
# Update INSTA_SESSION secret with new JSON
```

Session files expire after ~30 days. Regenerate to keep automation working.

---

## Code Changes Made

All 7 fixes are now in place:

| Fix | Status | File |
|-----|--------|------|
| Session validation | ✅ | `pipeline/insta_handler.py` |
| Rate limit retry | ✅ | `pipeline/insta_handler.py` |
| Poll story isolation | ✅ | `pipeline/insta_handler.py` |
| File locking | ✅ | `pipeline/feedback_loop.py` |
| Cache key | ✅ | `.github/workflows/auto-reels.yml` |
| Analytics timeout | ✅ | `pipeline/insta_handler.py` |
| Data validation | ✅ | `pipeline/feedback_loop.py` |

---

## Questions?

- **Session not working after update?** Check it hasn't expired (~30 days max)
- **Workflow still times out?** Logs will show which step failed
- **Story posts but poll doesn't?** Poll failures are non-fatal (reel posted)

