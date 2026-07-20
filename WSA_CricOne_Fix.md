# Windows Subsystem for Android (WSA) Video Black Screen Fix
**App:** CricOne (and similar live streaming apps)
**Symptoms:** Video stream goes completely black at random intervals (sometimes instantly, sometimes after 5, 10, or 15 minutes), but the background audio from the live match continues to play perfectly.

## Root Causes Identified from ADB Logs
We extracted logs from the WSA emulator (`adb logcat`) exactly when the black screen occurred and found two distinct issues:

1. **Screen Timeout (`reason=timeout`)**
   Because you are just watching a video and not actively clicking inside the WSA environment, the virtual Android device assumed you were idle and turned its display off to save battery after 10 minutes. 

2. **Intel GPU Shader Crash (`skia : Shader compilation error`)**
   When the app tried to load an ad overlay (from `CAS.AI`) over the video stream, it attempted to compile a graphics shader using the laptop's dedicated Intel UHD Graphics. The Intel driver failed to compile the shader, causing the visual UI layer (Skia) to crash completely and the Widevine DRM video surface to detach, leaving only the audio running.

---

## The Fixes Applied

### Fix 1: Stop the Android Screen from Sleeping
We used ADB to permanently change the hidden Android display timeout setting to 24 hours (86,400,000 ms).
**Command:**
`adb shell settings put system screen_off_timeout 86400000`

### Fix 2: Bypass the Intel Graphics Driver Crash (Crucial Fix)
To prevent the visual layer from crashing when it hits an incompatible shader, we forced WSA to use software rendering.
**Steps:**
1. Open the **Windows Subsystem for Android Settings** app from the Windows Start menu.
2. Go to **Advanced settings** (or **System**).
3. Change **Subsystem resources** from "As needed" to **Continuous**.
4. Under **Graphics preference**, click the circle for **Specific GPU**, then click the dropdown menu underneath it and select **Microsoft Basic Render Driver**.
5. Click **Turn off** in the WSA settings to completely shut down the subsystem so the new driver takes effect.

## Note for Future Troubleshooting
If this issue ever returns, provide these logs and the fixes above to the AI so it immediately has the correct context without needing to hunt for the bugs again!
