# Testing: Stale Command Fix

## Changes Made

### 1. **Configurable Stale Command Threshold**
- Added `max_command_age_ms` parameter to `HardwareGateway` constructor
- Reads from `rover_config.yaml` → `hardware_gateway.max_command_age_ms`
- **Default changed from 100ms → 250ms** for more forgiving initial testing

### 2. **Throttled Warning Messages**
- Stale command warnings now limited to **once every 2 seconds**
- Prevents log spam while still alerting you to the issue

### 3. **Safer Stop Behavior**
- **OLD**: Stale command → sends `estop=True` → may latch fault on dsPIC
- **NEW**: Stale command → sends normal STOP (0,0) with `enable_request=True, estop=False`
- This allows the system to resume immediately when fresh commands arrive

### 4. **Link Status in UI**
- Added "Frames Sent" and "Frames Received" to telemetry panel
- Updates in real-time so you can see UART activity without checking `/api/v1/health`
- Helps diagnose communication issues

---

## How to Test

### Step 1: Deploy Changes to Pi

```bash
# On your dev machine (commit and push)
git add .
git commit -m "Fix stale command handling and add link status to UI"
git push

# On the Pi (pull and restart)
cd ~/rover/Rover
git pull
cd "Raspberry Pi/pi"
source venv/bin/activate
./scripts/rover_bringup.sh
```

### Step 2: Open UI and Observe Baseline

1. Open browser to `http://192.168.0.21:8000`
2. Wait for video to connect
3. **Expected behavior (no interaction)**:
   - Video should stream
   - "Frames Sent" should increment every second (50/sec = 50 frames/sec)
   - "Frames Received" should stay at 0 (no dsPIC connected)
   - **Stale warnings should appear in logs**, but **only once every 2 seconds** (not spamming)

### Step 3: Test Keyboard Control

1. **Hold down W key** (forward throttle)
2. **Watch the Pi logs**:
   - Stale warnings should **stop or become less frequent**
   - This proves fresh commands are arriving
3. **Release W**
4. **Logs should show**:
   - One stale warning ~250ms after you released
   - Then one more every 2 seconds (throttled)

### Step 4: Test Joystick Control

1. **Click and drag the joystick**
2. **Hold it in a position** for a few seconds
3. **Expected**:
   - While dragging: no stale warnings (or rare)
   - After releasing: stale warnings resume (throttled to every 2s)

### Step 5: Check Link Status in UI

1. **Look at the telemetry panel**:
   - "Frames Sent" should continuously increment
   - "Frames Received" should be 0 (expected without dsPIC)
2. **This proves**:
   - The gateway is sending commands over UART at 50 Hz
   - The receiver is listening, but not getting replies

---

## What "Good" Looks Like

### ✅ **Stale warnings are throttled**
- You see **"Stale command (age=0.XXXs > 0.250s), sending stop"** at most once every 2 seconds
- Not spamming hundreds of times per second

### ✅ **Warnings stop when you actively drive**
- Hold W or drag joystick → warnings pause
- Release → warnings resume after 250ms

### ✅ **Link status visible in UI**
- "Frames Sent" increments continuously (proves UART TX is working)
- "Frames Received" is 0 (expected until dsPIC responds)

### ✅ **No E-STOP latching**
- When you resume driving after stale warnings, the rover should respond immediately
- (You can't fully test this until dsPIC is connected, but the code now sends `estop=False`)

---

## What "Bad" Looks Like (and How to Fix)

### ❌ **Warnings still spam every cycle**
**Diagnosis**: Warning throttle isn't working  
**Fix**: Check that `self._last_stale_warn_time` is being updated (look at code)

### ❌ **Warnings continue even while holding W**
**Diagnosis**: UI isn't sending control messages, or they're not reaching the gateway  
**Fix**:
1. Open browser DevTools → Network tab → WebSocket
2. Check if `teleop` messages are being sent every 50ms
3. If not, the issue is in the UI JavaScript

### ❌ **"Frames Sent" stays at 0**
**Diagnosis**: UART isn't opening or sending  
**Fix**:
1. Check logs for `"Opened serial port: /dev/serial0 @ 115200"`
2. If missing, check permissions: `ls -l /dev/serial0`
3. You should see: `crw-rw---- 1 root dialout ...`
4. Add user to group: `sudo usermod -a -G dialout rover`

### ❌ **Video doesn't stream**
**Diagnosis**: Unrelated to this fix, but check:
1. Camera detected: `rpicam-hello`
2. Picamera2 available in venv: `python -c "from picamera2 import Picamera2"`
3. Browser console for WebRTC errors

---

## Next Steps After Testing

If all tests pass:
1. **Document the baseline**: "Pi-side teleoperation works without dsPIC"
2. **Test with dsPIC loopback**: Connect UART, write minimal firmware echo
3. **Verify telemetry parsing**: See "Frames Received" increment in UI
4. **Move to motor bringup**: Connect motors, verify PWM output

---

## Configuration Tuning

If 250ms is still too aggressive (or too lenient):

**Edit**: `Raspberry Pi/pi/config/rover_config.yaml`

```yaml
hardware_gateway:
  command_rate_hz: 50
  max_command_age_ms: 500  # More forgiving (500ms)
```

**Restart** the server to apply.

**Recommendation**:
- **Development/bringup**: 250-500ms (forgiving)
- **Production driving**: 100-150ms (responsive)
- **Autonomous nav**: 50-100ms (tight loop)

---

## Summary

You now have:
1. **Less spam** in logs (throttled warnings)
2. **Safer stop behavior** (no accidental E-STOP latching)
3. **Better visibility** (link status in UI)
4. **Tunable threshold** (via config file)

**Test it, observe the logs, and confirm the stale warnings are now manageable!**

