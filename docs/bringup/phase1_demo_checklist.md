# Phase 1 Demo & Validation Checklist

## Document Information
- **Version**: 1.0
- **Phase**: Phase 1 - Manual Drive
- **Last Updated**: 2025-12-29

## Overview

This checklist ensures a repeatable Phase 1 demo and validates all safety features before proceeding to Phase 2.

---

## Pre-Demo Setup Checklist

### Hardware Setup

- [ ] **Battery charged** and voltage measured (should be 11-12.6V for 3S LiPo)
- [ ] **dsPIC nano board** connected to power and UART
- [ ] **UART wiring** verified:
  - Pi GPIO14 (TX) → dsPIC RX
  - Pi GPIO15 (RX) → dsPIC TX
  - Common ground connected
- [ ] **Motor driver (L298N)** connected:
  - Power input from battery
  - Control signals from dsPIC
  - Motor outputs connected to motors
- [ ] **Motors** mounted securely on chassis
- [ ] **Emergency stop method** available (power disconnect or physical access)
- [ ] **Pi Camera** connected and recognized (`libcamera-hello` test)

### Software Setup

- [ ] **Pi OS updated**: `sudo apt update && sudo apt upgrade`
- [ ] **UART enabled** in raspi-config (disable login shell, enable hardware)
- [ ] **Dependencies installed**:
  ```bash
  sudo apt install python3-picamera2 python3-serial python3-yaml
  ```
- [ ] **Python venv created** and requirements installed:
  ```bash
  cd ~/Rover/Raspberry\ Pi/pi
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- [ ] **Configuration file** edited (`config/rover_config.yaml`):
  - UART port set correctly (`/dev/serial0` or `/dev/ttyAMA0`)
  - Max speed set conservatively (e.g., 0.5 for first test)
  - Voltage thresholds match your battery

### Firmware Setup

- [ ] **dsPIC firmware** compiled (see `dsPIC33CK64MC105/firmware/README.md`)
- [ ] **Pin assignments** in `config.h` match your hardware
- [ ] **Firmware programmed** to dsPIC
- [ ] **Status LED** blinking at 1 Hz (indicates running)

---

## Phase 1 Demo Procedure

### Step 1: Basic Communication Test

**Objective**: Verify UART link between Pi and dsPIC

1. [ ] Place rover on blocks (wheels off ground)
2. [ ] Power on dsPIC (should see status LED)
3. [ ] SSH into Pi
4. [ ] Run hardware gateway standalone:
   ```bash
   cd ~/Rover/Raspberry\ Pi/pi
   source venv/bin/activate
   python apps/hardware_gateway/hardware_gateway.py
   ```
5. [ ] **Expected output**:
   - "Opened serial port" message
   - Telemetry frames received (20 Hz)
   - No CRC errors
   - `age_ms` should show watchdog timeout (200ms+) since no commands sent
6. [ ] Press Ctrl+C to stop

**Success Criteria**:
- UART communication established
- Telemetry received with expected values
- No serial errors

---

### Step 2: Full System Bringup

**Objective**: Start all services and access web UI

1. [ ] Run bringup script:
   ```bash
   cd ~/Rover/Raspberry\ Pi/pi
   ./scripts/rover_bringup.sh
   ```
2. [ ] **Expected output**:
   - All services start without errors
   - "Access UI at: http://[Pi IP]:8000" shown
3. [ ] Open web browser on laptop/phone
4. [ ] Navigate to `http://[Pi IP]:8000`
5. [ ] **Expected UI**:
   - Connection indicator turns green
   - Video stream shows live camera feed (or test pattern)
   - Telemetry updates at ~20 Hz
   - Status shows "Connected"

**Success Criteria**:
- Web UI loads successfully
- WebSocket connection established
- Video streaming works
- Telemetry displayed

---

### Step 3: Basic Drive Test (Wheels Off Ground)

**Objective**: Verify motor control without rover movement

1. [ ] Rover still on blocks (wheels free)
2. [ ] **Click joystick** in UI or press **W** key
3. [ ] **Observe**:
   - Motors should spin forward (both wheels)
   - Telemetry shows PWM increasing smoothly (ramping)
   - Speed ramps up over ~2 seconds (normal ramp rate)
4. [ ] **Release control** (center joystick or release key)
5. [ ] **Observe**:
   - Motors ramp down to zero
   - Telemetry PWM returns to 0
6. [ ] **Test turning**:
   - Move joystick left → left motor slower, right faster
   - Move joystick right → opposite
7. [ ] **Test reverse**:
   - Move joystick down or press S key
   - Motors spin backward

**Success Criteria**:
- Motors respond to commands
- Ramping is smooth (no sudden jerks)
- All directions work (forward, reverse, left, right)
- Motors stop when control released

---

### Step 4: Ground Drive Test

**Objective**: Drive rover on the floor

1. [ ] Place rover on floor in clear area (at least 3m × 3m)
2. [ ] **Slowly** move joystick forward
3. [ ] Rover should move forward smoothly
4. [ ] Drive in a circle (forward + turn)
5. [ ] Drive backward
6. [ ] Stop rover in center of area

**Success Criteria**:
- Rover responds predictably to controls
- No unexpected behaviors
- Smooth acceleration/deceleration

---

## Safety Validation Tests

### Test 1: Emergency Stop Button

**Objective**: Verify emergency stop functionality

**Procedure**:
1. [ ] Start rover moving forward
2. [ ] Click **"EMERGENCY STOP"** button in UI
3. [ ] **Expected**:
   - Motors stop within 100 ms
   - Fault indicator turns red
   - Status shows "Faulted"
   - Telemetry shows ESTOP fault flag
4. [ ] Clear E-stop by sending new command (move joystick)
5. [ ] Rover should resume normal operation

**Success Criteria**: ✅ PASS / ❌ FAIL
- [ ] Motors stopped quickly (< 100 ms)
- [ ] Fault indicated in UI
- [ ] System recovers after clear

---

### Test 2: Wi-Fi Disconnect (Watchdog Timeout)

**Objective**: Verify dsPIC watchdog stops rover when Pi connection lost

**Procedure**:
1. [ ] Start rover moving forward at ~50% speed
2. [ ] **Disable Wi-Fi** on Pi:
   ```bash
   sudo ifconfig wlan0 down
   ```
   OR unplug Ethernet
3. [ ] **Expected**:
   - Within 200 ms, motors stop (dsPIC watchdog)
   - Rover comes to a halt
4. [ ] Re-enable Wi-Fi:
   ```bash
   sudo ifconfig wlan0 up
   ```
5. [ ] Reconnect UI and verify control restored

**Success Criteria**: ✅ PASS / ❌ FAIL
- [ ] Motors stopped within 200 ms
- [ ] dsPIC watchdog functioned correctly
- [ ] System recovered when connection restored

---

### Test 3: Software Process Crash

**Objective**: Verify dsPIC stops rover if Pi software crashes

**Procedure**:
1. [ ] Start rover moving forward
2. [ ] SSH into Pi
3. [ ] **Kill hardware gateway process**:
   ```bash
   pkill -9 -f hardware_gateway
   ```
4. [ ] **Expected**:
   - Motors stop within 200 ms
   - dsPIC enters watchdog timeout state
5. [ ] Restart system with bringup script
6. [ ] Verify control restored

**Success Criteria**: ✅ PASS / ❌ FAIL
- [ ] Motors stopped automatically
- [ ] No runaway behavior
- [ ] System recoverable

---

### Test 4: Low Battery (Brownout Simulation)

**Objective**: Verify undervoltage protection

**Procedure**:
1. [ ] Edit `config.h` on dsPIC to set `VOLTAGE_MIN_MV` above current voltage
2. [ ] Recompile and reprogram firmware
3. [ ] Start rover
4. [ ] **Expected**:
   - UNDERVOLTAGE fault flag set in telemetry
   - Motors disabled
   - UI shows fault condition
5. [ ] Restore correct `VOLTAGE_MIN_MV` value

**Success Criteria**: ✅ PASS / ❌ FAIL
- [ ] Undervoltage detected
- [ ] Motors disabled
- [ ] Fault reported to UI

**Alternative** (if safe): Run motors until battery voltage drops naturally below threshold.

---

### Test 5: UART Cable Disconnect

**Objective**: Verify rover stops when communication cable fails

**Procedure**:
1. [ ] Start rover moving forward
2. [ ] **Unplug UART cable** between Pi and dsPIC (either end)
3. [ ] **Expected**:
   - Motors stop within 200 ms (watchdog)
   - UI shows "link lost" or timeout
4. [ ] Reconnect cable
5. [ ] System should recover

**Success Criteria**: ✅ PASS / ❌ FAIL
- [ ] Rover stopped safely
- [ ] Watchdog timeout triggered
- [ ] Recovery after reconnection

---

### Test 6: Rapid Enable/Disable

**Objective**: Verify state machine handles rapid transitions

**Procedure**:
1. [ ] Rapidly click E-stop button 10 times in a row (on/off)
2. [ ] **Expected**:
   - No crashes
   - No unexpected motor behavior
   - System remains responsive
3. [ ] Send normal drive command
4. [ ] Rover should operate normally

**Success Criteria**: ✅ PASS / ❌ FAIL
- [ ] No crashes or hangs
- [ ] System stable after rapid toggling

---

## Performance Validation

### Telemetry Latency

1. [ ] Observe telemetry age in UI (`age_ms`)
2. [ ] **Expected**: Age should be 0-50 ms (depending on command rate)
3. [ ] If age consistently > 100 ms, investigate command rate or performance

**Measured age**: __________ ms

---

### Video Latency

1. [ ] Wave hand in front of camera
2. [ ] Observe latency in UI video stream
3. [ ] **Expected**: < 300 ms for WebRTC

**Subjective latency**: __________ ms

---

### Command Response

1. [ ] Press W key, measure time until motors visibly spin
2. [ ] **Expected**: < 100 ms from key press to motor response

**Measured latency**: __________ ms

---

## Logging & Recording

### Enable Logging

1. [ ] Verify logs written to `/var/log/rover/` (or configured path)
2. [ ] Logs should include:
   - [ ] Startup events
   - [ ] All drive commands sent
   - [ ] All telemetry received
   - [ ] Fault events
   - [ ] Errors and warnings

### Black Box Recording (Optional)

If implementing "last 30 seconds" recording:
1. [ ] Trigger a fault condition
2. [ ] Stop system
3. [ ] Verify last 30 seconds of telemetry captured in log
4. [ ] Review log for post-mortem analysis

---

## Known Issues / Notes

| Issue | Severity | Workaround | Ticket |
|-------|----------|------------|--------|
|       |          |            |        |

---

## Demo Sign-Off

**Demo Date**: __________________

**Performed By**: __________________

**Hardware Configuration**:
- Battery: ________ V
- Motor Driver: ________
- dsPIC Firmware Version: ________
- Pi Software Version: ________

### Overall Results

| Test | Result | Notes |
|------|--------|-------|
| Basic Communication | ☐ PASS ☐ FAIL | |
| Full System Bringup | ☐ PASS ☐ FAIL | |
| Basic Drive Test | ☐ PASS ☐ FAIL | |
| Ground Drive Test | ☐ PASS ☐ FAIL | |
| Emergency Stop | ☐ PASS ☐ FAIL | |
| Watchdog Timeout | ☐ PASS ☐ FAIL | |
| Process Crash | ☐ PASS ☐ FAIL | |
| Brownout Protection | ☐ PASS ☐ FAIL | |
| UART Disconnect | ☐ PASS ☐ FAIL | |
| Rapid Enable/Disable | ☐ PASS ☐ FAIL | |

### Phase 1 Validation

- [ ] **All safety tests passed**
- [ ] **Performance meets requirements**
- [ ] **System is stable and repeatable**
- [ ] **Ready to proceed to Phase 2** (encoder integration)

**Signature**: __________________  **Date**: __________________

---

## Troubleshooting Guide

### Issue: No UART communication

**Symptoms**: "Failed to open serial port" error

**Solutions**:
1. Check UART enabled: `sudo raspi-config` → Interface Options → Serial Port
   - Login shell: NO
   - Serial hardware: YES
2. Verify port: `ls /dev/serial* /dev/ttyAMA*`
3. Check permissions: `sudo usermod -a -G dialout $USER` (then reboot)
4. Test loopback: Connect TX to RX, echo test

---

### Issue: CRC errors in telemetry

**Symptoms**: Parser reports CRC errors in logs

**Solutions**:
1. Check common ground connection
2. Reduce baud rate (try 57600)
3. Add pull-up resistors on UART lines
4. Check for electrical noise sources

---

### Issue: Motors don't respond

**Symptoms**: Telemetry received, but motors don't spin

**Solutions**:
1. Check motor driver connections (PWM + direction pins)
2. Verify motor driver enabled (check enable pin if present)
3. Measure PWM output with oscilloscope
4. Check dsPIC `motor_apply_outputs()` for hardware-specific issues

---

### Issue: Watchdog timeout even when sending commands

**Symptoms**: Constant WATCHDOG_TIMEOUT fault

**Solutions**:
1. Check command rate: Should be 20-50 Hz
2. Verify protocol version matches (binary vs ASCII)
3. Check for frame encoding errors
4. Increase watchdog timeout (e.g., 500 ms) for debugging

---

### Issue: Video not streaming

**Symptoms**: "Waiting for video..." in UI

**Solutions**:
1. Test camera: `libcamera-hello`
2. Check Picamera2 installed: `python3 -c "from picamera2 import Picamera2"`
3. Review video service logs for errors
4. Try dummy mode to isolate camera vs WebRTC issue

---

### Issue: High CPU usage on Pi

**Symptoms**: Pi sluggish, high temperature

**Solutions**:
1. Reduce video framerate (config: 15 fps)
2. Lower video resolution (480p)
3. Disable unused services
4. Check for Python package conflicts (reinstall in fresh venv)

---

## Next Steps (Phase 2)

After Phase 1 validation passes:
1. Order/install motor encoders
2. Implement encoder reading on dsPIC
3. Extend telemetry to include encoder data
4. Implement PID speed control
5. Add state estimator (odometry) on Pi

Refer to: `docs/architecture/phase2_planning.md`

