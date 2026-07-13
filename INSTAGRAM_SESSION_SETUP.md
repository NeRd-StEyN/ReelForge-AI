# Instagram Session Setup Guide

## ⚠️ CRITICAL: Story Upload Requires Valid Session File

Instagram **blocks session ID-only logins** for security. The pipeline REQUIRES a full session file to authenticate.

---

## How to Generate & Deploy Session File

### Step 1: Generate Session (LOCAL MACHINE ONLY)

Run this command on your **local machine** (not on GitHub):

```bash
python generate_session.py
```

**Expected output:** A large JSON block like:
```json
{
  "settings": {
    "phone_id": "...",
    "device_id": "...",
    "uuid": "...",
    "cookie_jar": {...},
    ...
  }
}
```

### Step 2: Store as GitHub Secret

1. Go to: `https://github.com/YOUR-USERNAME/ReelForge-AI/settings/secrets/actions`
2. Click **"New repository secret"**
3. **Name:** `INSTA_SESSION`
4. **Value:** Paste the entire JSON output from Step 1
5. Click **"Add secret"**

### Step 3: Verify Workflow Uses It

The workflow already has this step:

```yaml
- name: Write Instagram session file
  if: env.INSTA_SESSION != ''
  run: echo "$INSTA_SESSION" > insta_session.json
```

This automatically writes the secret to `insta_session.json` on GitHub Actions runners.

---

## Session Expiration & Renewal

### ⏰ Session Expires After ~30 Days

Instagram invalidates sessions after ~30 days of inactivity. You must regenerate periodically.

### 🔄 Monthly Renewal Process

**Set a calendar reminder for the 1st of each month:**

```bash
# On your local machine
python generate_session.py
# Copy the output JSON
# Update the INSTA_SESSION GitHub Secret with new JSON
```

### How to Tell Session is Expired

Watch for these signs in workflow logs:

```
[Analytics] Session validation failed: ...
[Analytics] ALL LOGIN METHODS FAILED
[Story] Failed to get user ID: ...
[Story] Timeout reached (1500s). Reel was not detected.
```

**Action:** Regenerate and update the secret.

---

## Troubleshooting

### Problem: `generate_session.py` Fails

**Solution:** Ensure you have the required packages:
```bash
pip install -r requirements.txt
python generate_session.py
```

If it still fails, check:
- [ ] Internet connection is stable
- [ ] Instagram username/password are correct
- [ ] Account doesn't have 2FA enabled (disable temporarily)
- [ ] Account isn't in a "suspicious activity" lockout

### Problem: Story Posts Still Fail on GitHub

**Check:**
1. [ ] Secret name is exactly `INSTA_SESSION` (case-sensitive)
2. [ ] JSON is valid and complete (not truncated)
3. [ ] Session hasn't expired (regenerate monthly)
4. [ ] Workflow can access the secret (check workflow logs)

**Debug:** Add this to `.github/workflows/auto-reels.yml`:
```yaml
- name: Verify session file exists
  run: |
    if [ -f insta_session.json ]; then
      echo "✅ Session file exists"
      ls -la insta_session.json
    else
      echo "❌ Session file NOT FOUND"
      echo "INSTA_SESSION secret is: ${{ secrets.INSTA_SESSION != '' && 'SET' || 'NOT SET' }}"
    fi
```

---

## Why This Approach?

| Method | Reliability | Works on GitHub? | Notes |
|--------|------------|------------------|-------|
| Session File (insta_session.json) | ✅ Excellent | ✅ Yes | **ONLY reliable method** |
| Session ID Cookie (INSTA_SESSION_ID) | ❌ Blocked | ❌ No | Instagram blocks this for security |
| Password Login | ⚠️ Rare | ⚠️ Sometimes | Frequently blocked on GitHub IPs |

Instagram made a deliberate decision to block session ID-only authentication. The full session file is the documented, approved way to authenticate for automation tools.

---

## Dashboard Monitoring

Add this to your calendar:

```
📅 1st of every month: Regenerate Instagram session
   1. Run: python generate_session.py
   2. Update GitHub secret: INSTA_SESSION
   3. Verify next workflow run succeeds
```

This ensures:
- ✅ Story uploads work consistently
- ✅ Feedback loop has fresh analytics
- ✅ No surprise failures from expired sessions

