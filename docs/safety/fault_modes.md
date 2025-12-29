# Rover Safety & Fault Mode Analysis

## Document Information
- **Version**: 1.0
- **Status**: Active
- **Last Updated**: 2025-12-29

## Safety Philosophy

The rover is designed with **defense in depth**: multiple independent layers ensure safe behavior even when components fail.

### Safety Hierarchy
1. **dsPIC Hardware** (Innermost): Direct control of motor outputs, cannot be bypassed
2. **dsPIC Firmware**: Watchdogs, ramps, fault detection
3. **Pi Hardware Gateway**: Command rate limiting, freshness checks
4. **Pi Application Layer**: Emergency stop UI, mission abort logic
5. **User Oversight**: Physical emergency stop (future), power disconnect

---

## Failure Modes and Effects Analysis (FMEA)

### Communication Failures

| Failure Mode | Detection | Response | Recovery |
|--------------|-----------|----------|----------|
| **Pi software crash** | dsPIC watchdog timeout (200ms) | Motors ramp to stop, outputs disabled | Pi reboot, send DriveCmd with ENABLE_REQUEST |
| **UART cable disconnect** | dsPIC watchdog timeout | Motors ramp to stop | Reconnect cable, re-enable |
| **UART noise/corruption** | CRC failures | Invalid frames discarded | Parser resyncs on next valid SOF |
| **dsPIC firmware hang** | Pi: no telemetry received | Pi detects timeout, shows fault in UI | Power cycle dsPIC |
| **Pi → dsPIC one-way failure** | dsPIC watchdog | Motors stop | Debug TX path, check wiring |
| **dsPIC → Pi one-way failure** | Pi: no telemetry | UI shows "link down" | Debug RX path, check wiring |

### Power Failures

| Failure Mode | Detection | Response | Recovery |
|--------------|-----------|----------|----------|
| **Battery depleted** | `bus_mv` telemetry below threshold | Pi initiates shutdown, dsPIC UNDERVOLTAGE fault | Recharge battery |
| **Battery disconnect during operation** | Immediate power loss | Motors stop (no power) | Reconnect battery |
| **Pi brownout** | Pi crashes/reboots | dsPIC watchdog stops motors | Pi reboots, re-enables |
| **dsPIC brownout** | dsPIC resets | Outputs disabled on boot | dsPIC recovers, awaits enable |
| **Motor driver fault** | Fault pin or I2C feedback | dsPIC sets DRIVER_FAULT flag | Identify and fix driver issue |
| **Overvoltage (charging mishap)** | `bus_mv` above threshold | dsPIC sets OVERVOLTAGE fault, disables outputs | Disconnect charger |

### Motor/Mechanical Failures

| Failure Mode | Detection | Response | Recovery |
|--------------|-----------|----------|----------|
| **Motor stall** | [Phase 2] Encoder velocity low despite command | Set overcurrent fault if detected | Reduce load or fix obstruction |
| **Wheel slip** | [Phase 2] Odometry inconsistency | Navigation degraded | Switch to marker-based localization |
| **Motor wire disconnect** | One wheel not responding | Detectable via encoders (Phase 2) | Check wiring |
| **Stuck rover** | [Phase 4] No odometry progress | Autonomy abort, request teleoperation | User intervention |

### Sensor Failures

| Failure Mode | Detection | Response | Recovery |
|--------------|-----------|----------|----------|
| **Camera failure** | No frames from Picamera2 | Video service logs error | Check ribbon cable, reboot |
| **Encoder failure** | [Phase 2] No ticks despite motor drive | Telemetry shows zero velocity | Fall back to open-loop control |
| **IMU failure** | [Future] I2C timeout or bad data | Disable IMU fusion | Fall back to wheel odometry only |

### Software Failures

| Failure Mode | Detection | Response | Recovery |
|--------------|-----------|----------|----------|
| **Python exception in service** | Process crash or systemd restart | Motors stop (no commands to dsPIC) | Systemd auto-restart, log traceback |
| **Message bus deadlock** | Watchdog in each service | Service timeout, restart | Restart affected services |
| **WebSocket disconnect** | Browser connection lost | UI shows disconnected; no new commands sent | User refreshes browser |
| **Filesystem full** | Write failures | Stop logging, continue operation | Free space or reboot |
| **Memory exhaustion** | OOM killer | Process killed, motors stop | Systemd restart, investigate leak |

---

## Safe State Definitions

### dsPIC Safe State
- **Motor outputs**: Disabled (PWM = 0%, direction pins = LOW)
- **Fault flags**: Appropriate flags set (WATCHDOG_TIMEOUT, etc.)
- **Telemetry**: Continues to transmit (if possible)
- **Watchdog**: Active and monitoring

### Pi Safe State
- **Commands**: Stop sending DriveCmd
- **UI**: Display fault status
- **Logs**: Record event for post-mortem
- **Autonomy**: Abort active missions

---

## Watchdog Specifications

### dsPIC Command Watchdog
- **Timeout**: 200 ms (configurable, but must be > 4× command period)
- **Trigger**: No valid DriveCmd received within timeout window
- **Action**:
  1. Set `WATCHDOG_TIMEOUT` fault flag
  2. Ramp motors to zero over 100 ms
  3. Disable motor outputs
  4. Continue sending telemetry with fault flag set
- **Clear**: Automatic on next valid DriveCmd with `ENABLE_REQUEST`

### Pi Telemetry Watchdog
- **Timeout**: 500 ms (no telemetry frames received)
- **Action**:
  1. Stop sending DriveCmd
  2. Update UI to show "dsPIC link lost"
  3. Log event
- **Clear**: Automatic on next valid telemetry frame

---

## Emergency Stop Behavior

### E-Stop Activation
- **Trigger**:
  - UI "STOP" button pressed
  - DriveCmd with `ESTOP` flag set
  - StopCmd message
  - [Future] Physical E-stop button pressed
- **dsPIC Response**:
  1. Immediately set `ESTOP_ACTIVE` fault flag
  2. Ramp motors to zero over 50 ms (faster than watchdog timeout)
  3. Disable outputs
  4. Ignore subsequent DriveCmd speed values while ESTOP flag is set
- **Pi Response**:
  1. Send DriveCmd with `ESTOP` flag
  2. Update UI to show "E-STOP ACTIVE"
  3. Log event

### E-Stop Clear
- **Condition**: User explicitly re-enables drive
- **Procedure**:
  1. Pi sends DriveCmd with `ESTOP` flag cleared and `ENABLE_REQUEST` set
  2. dsPIC clears `ESTOP_ACTIVE` fault if no other faults present
  3. System returns to ENABLED state

---

## Fault Latching and Clearing

### Latched Faults (Require Explicit Clear)
- `DRIVER_FAULT`: Motor driver hardware error
- `OVERVOLTAGE`: Bus voltage too high
- `UNDERVOLTAGE`: Bus voltage too low (below safe operating threshold)
- `OVERCURRENT`: Sustained overcurrent condition

**Clear Procedure**:
1. Identify and resolve root cause
2. Power cycle dsPIC OR send DriveCmd with `ENABLE_REQUEST` after condition resolved
3. dsPIC checks fault conditions before clearing flag

### Non-Latched Faults (Auto-Clear When Condition Resolves)
- `WATCHDOG_TIMEOUT`: Clears on next valid DriveCmd
- `ESTOP_ACTIVE`: Clears when ESTOP flag de-asserted and ENABLE_REQUEST sent

---

## Ramping and Acceleration Limits

### Purpose
- Prevent sudden current spikes
- Reduce mechanical stress on drivetrain
- Improve control stability
- Provide time for watchdog/estop to activate

### dsPIC Ramping
- **Location**: Authoritative ramping in dsPIC firmware
- **Max Acceleration**: Configurable, default ±50%/sec (0% → 100% in 2 seconds)
- **Override**: E-stop ignores ramp and stops faster (±200%/sec)

### Pi-Side Slewing (Optional)
- **Purpose**: Smoother user input response, reduce command jitter
- **Limit**: Mild (e.g., ±200%/sec), dsPIC ramp is authoritative

---

## Boot Behavior

### dsPIC Power-On
1. Initialize peripherals (UART, timers, PWM)
2. **Disable motor outputs** (safe default)
3. Set state = BOOT
4. Begin sending telemetry with fault flags = 0 (no faults, but not enabled)
5. Await first valid DriveCmd with `ENABLE_REQUEST` flag

### Pi Power-On
1. Systemd brings up services in order
2. Hardware gateway establishes UART connection
3. Detects dsPIC is alive (receives telemetry)
4. Waits for user input or autonomy request before sending DriveCmd
5. First DriveCmd includes `ENABLE_REQUEST` flag

### Recovery from Power Cycle
- User must explicitly enable drive (button or command)
- Prevents rover from moving unexpectedly after power restored

---

## Testing Requirements

### Functional Safety Tests

| Test | Procedure | Expected Result | Frequency |
|------|-----------|-----------------|-----------|
| **Watchdog timeout** | Stop Pi software | Motors stop within 200ms | Every build |
| **E-stop UI** | Press stop button during motion | Motors stop within 100ms | Every build |
| **Cable disconnect** | Unplug UART while driving | Motors stop within 200ms | Phase 1 validation |
| **Pi crash simulation** | `kill -9` on hardware_gateway | Motors stop within 200ms | Phase 1 validation |
| **Low battery** | Simulate low voltage | System shuts down gracefully | Phase 1 validation |
| **dsPIC reset** | Reset dsPIC during motion | Outputs stay disabled until re-enabled | Phase 1 validation |
| **CRC corruption** | Inject bit errors | Invalid frames discarded, system continues | Protocol validation |
| **Sustained fault** | Create latched fault | System stays faulted until cleared | Phase 1 validation |

### Stress Tests
- **Command burst**: Send 1000 commands rapidly → system stable
- **Telemetry flood**: Saturate UART with telemetry → Pi keeps up
- **Rapid enable/disable**: Toggle enable 10× per second → no crashes

---

## User-Facing Safety Features

### UI Indicators
- **Large STOP button**: Always visible, one-click stop
- **Connection status**: Green = connected, Red = fault, Yellow = degraded
- **Fault display**: Show active fault flags with human-readable names
- **Battery level**: Visual indicator and percentage
- **E-stop indicator**: Bright red when active

### Deadman Switch (Optional, Phase 1.5)
- **Behavior**: User must hold a key/button to drive
- **Implementation**: DriveCmd only sent while button held
- **Release**: Immediate stop command sent

---

## Future Enhancements

1. **Redundant E-stop**: Physical button wired directly to dsPIC GPIO
2. **Current Sensing**: Real-time overcurrent detection
3. **Temperature Monitoring**: Thermal shutdown for motor driver
4. **Accelerometer**: Detect tip-over or collision
5. **Geofence**: Software boundary for autonomous mode
6. **Limp Mode**: Reduced speed operation under degraded conditions

---

## Compliance and Standards

While this is a hobbyist project, design follows principles from:
- **ISO 13849**: Safety of machinery (PLr = B, Category B)
- **IEC 61508**: Functional safety of electrical systems
- **FMEA Best Practices**: Failure mode analysis

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-29 | Rover Team | Initial safety analysis |


