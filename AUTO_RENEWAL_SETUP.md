# 🤖 AUTOMATIC SESSION RENEWAL SETUP

**You never have to manually renew again!** This guide sets up permanent automatic renewal.

---

## 🎯 How It Works

| Component | Function | When It Runs |
|-----------|----------|--------------|
| **GitHub Actions** | Attempts auto-renewal on cloud | 1st of every month at 2:00 AM UTC |
| **Windows Task Scheduler** | Monitors session locally | Every day at 2:00 AM |
| **Alert System** | Notifies if manual action needed | Only when auto-renewal fails |

---

## OPTION 1: Windows Task Scheduler (Recommended for Local Automation) 

### Quick Setup (2 minutes)

1. **Open PowerShell as Administrator** (right-click → Run as administrator)

2. **Navigate to project:**
   ```powershell
   cd "c:\Users\43ner\Desktop\ReelForge-AI"
   ```

3. **Run setup script:**
   ```powershell
   .\setup_auto_renewal.bat
   ```

4. **Choose Option 1: Auto-Renewal** (if you want full automation)
   - Enter your Instagram username
   - Enter your Instagram password
   - Done! ✅

5. **Or Choose Option 2: Daily Check** (if you prefer manual confirmation)
   - Just alerts you when renewal is needed
   - You run `python generate_session.py` when prompted

### How It Works

**Every day at 2:00 AM:**
1. Automatically checks session age
2. If 28+ days old → attempts auto-renewal
3. If successful → stores new session silently
4. If failed → creates `RENEWAL_ALERT.txt` with manual instructions

**Benefits:**
- ✅ Runs silently in background
- ✅ Handles renewal before expiration
- ✅ Only alerts when action needed
- ✅ Logs every run to `auto_renew_log.txt`

### Verify It's Working

```powershell
# Check if task is scheduled:
schtasks /query /tn "ReelForge\Session Auto-Renewal"

# See detailed task info:
tasklist /tn "ReelForge\Session Auto-Renewal" /v
```

### Manual Test

```powershell
# Run the renewal check manually:
python auto_renew_session.py

# Check logs:
Get-Content auto_renew_log.txt -Tail 20
```

---

## OPTION 2: GitHub Actions Monthly Renewal

Automatic renewal **on GitHub** when workflows run.

### Requirements

Add these secrets to GitHub:
1. Go to: **GitHub → Settings → Secrets and variables → Actions**
2. Add two new secrets:
   - `INSTA_USERNAME` = your Instagram username
   - `INSTA_PASSWORD` = your Instagram password

### How It Works

**Every 1st of month at 2:00 AM UTC:**
1. GitHub Actions workflow starts
2. Attempts to login with username/password
3. If successful → saves new session
4. If failed → sends alert with manual instructions
5. New session automatically pushed to GitHub

**Benefits:**
- ✅ Works on any machine (cloud-based)
- ✅ No local setup needed
- ✅ Happens automatically
- ✅ Can be disabled anytime

### Enable GitHub Auto-Renewal

1. Go to GitHub repository
2. Settings → Secrets and variables → Actions
3. Add two secrets:
   ```
   Name: INSTA_USERNAME
   Value: (your Instagram username)
   
   Name: INSTA_PASSWORD
   Value: (your Instagram password)
   ```
4. The workflow is already configured - it will run automatically!

### View GitHub Renewal Logs

```
GitHub → Actions tab → "Monthly Session Renewal"
```

---

## OPTION 3: Combined (Maximum Reliability) ✅ RECOMMENDED

Use **both** local and GitHub automation:

### Setup Steps

1. **Run Windows setup:**
   ```powershell
   .\setup_auto_renewal.bat
   # Choose Option 1 for full auto
   ```

2. **Add GitHub secrets:**
   - `INSTA_USERNAME`
   - `INSTA_PASSWORD`

**Result:**
- ✅ Windows checks daily locally
- ✅ GitHub checks monthly in cloud
- ✅ If one fails, the other catches it
- ✅ Truly "set it and forget it"

---

## What to Do When You See Alerts

### ⚠️ RENEWAL_ALERT.txt Appears

This means auto-renewal failed. Manual steps:

```powershell
# 1. Run generator
python generate_session.py

# 2. Choose Option 2: Browser Bypass

# 3. Login to Instagram in Chrome browser

# 4. Get sessionid from DevTools:
#    - Press F12
#    - Application → Cookies → "sessionid"
#    - Copy value

# 5. Paste into script when prompted

# 6. Verify
python verify_session.py
# Should show: ✅ Fresh

# 7. Update GitHub Secret with new JSON
# Or it will auto-sync if you ran Windows setup
```

**Takes 5 minutes, only needed if auto-renewal fails**

---

## Troubleshooting

### Task Not Running

```powershell
# Check if scheduled:
schtasks /query /tn "ReelForge\Session Auto-Renewal"

# Force immediate run:
schtasks /run /tn "ReelForge\Session Auto-Renewal"

# View last run result:
schtasks /query /tn "ReelForge\Session Auto-Renewal" /v /fo list
```

### Check Logs

```powershell
# Latest log entries:
Get-Content auto_renew_log.txt -Tail 30

# Full log:
notepad auto_renew_log.txt
```

### Remove/Disable Task

```powershell
# Disable (keep it, just pause):
schtasks /change /tn "ReelForge\Session Auto-Renewal" /disable

# Enable again:
schtasks /change /tn "ReelForge\Session Auto-Renewal" /enable

# Delete task:
schtasks /delete /tn "ReelForge\Session Auto-Renewal" /f
```

---

## Timeline: How Sessions Stay Fresh

```
Day 1-24:     ✅ Session perfect, auto-check runs daily
Day 25-27:    ✅ Still good, auto-check logs "getting close"
Day 28:       🔄 Auto-renewal TRIGGERED
              If password login works → ✅ New session saved silently
              If password login fails → ⚠️ RENEWAL_ALERT.txt created
Day 30+:      ❌ Would expire, but already renewed by day 28
```

---

## FAQ

**Q: What if I lose internet on renewal day?**
- A: Task runs every day, so it will catch it on the next day with internet

**Q: Can I disable auto-renewal?**
- A: Yes, run: `schtasks /change /tn "ReelForge\Session Auto-Renewal" /disable`
- Re-enable: `schtasks /change /tn "ReelForge\Session Auto-Renewal" /enable`

**Q: What if my Instagram password changes?**
- A: Update the environment variable or GitHub secret with new password

**Q: Will this consume my Instagram login attempts?**
- A: Only 1 attempt per month (if using password renewal)
- Instagram allows 5 failed attempts per hour, so this is safe

**Q: Can I change renewal time?**
- A: Edit in Task Scheduler or modify `setup_auto_renewal.bat`
- Default: 2:00 AM daily (adjust `/st 02:00` in script)

**Q: What if I want to force renewal now?**
- A: Run: `python auto_renew_session.py`

---

## Summary

| Setup Method | Effort | Automation | Reliability |
|--------------|--------|-----------|-------------|
| Manual | 5 min/month | 0% | 0% |
| GitHub only | 5 min | 50% | Medium |
| Windows only | 2 min setup | 100% | High |
| **Both (Recommended)** | 5 min setup | 100% | Very High |

---

## Next Steps

**Choose your automation:**

1. **Maximum Convenience:** Run `setup_auto_renewal.bat` + add GitHub secrets
2. **GitHub-Only:** Just add `INSTA_USERNAME` and `INSTA_PASSWORD` secrets  
3. **Local-Only:** Run `setup_auto_renewal.bat`
4. **Manual Renewal:** Do nothing - renew monthly when prompted

**Then forget about it!** Your Instagram automation will keep running month after month with zero intervention. 🚀
