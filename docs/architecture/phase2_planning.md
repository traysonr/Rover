# Phase 2 Planning: Closed-Loop Control & Encoders

## Document Information
- **Version**: 1.0
- **Phase**: Phase 2 - Encoder Integration & PID Speed Control
- **Last Updated**: 2025-12-29
- **Prerequisites**: Phase 1 complete and validated

## Overview

Phase 2 extends the Phase 1 system with closed-loop motor control:
- **Motor encoders**: Quadrature encoders for wheel odometry
- **PID speed control**: Maintain commanded velocities
- **Odometry**: Track robot pose using wheel encoder data
- **State estimation**: Fuse encoder data for localization

**Goal**: Command "drive at 0.3 m/s" and rover maintains that speed across different terrains (carpet vs tile).

---

## Architecture Changes

### dsPIC Firmware Extensions

```
┌─────────────────────────────────────────────────────┐
│             dsPIC33CK64MC105 Firmware                │
│  ┌────────────────────────────────────────────────┐ │
│  │         UART Command Handler (Phase 1)         │ │
│  │  Receives: DriveCmd (now velocity targets)     │ │
│  └──────────────┬─────────────────────────────────┘ │
│                 │                                    │
│  ┌──────────────▼──────────────┐  ┌──────────────┐ │
│  │   PID Speed Controllers     │  │  Watchdog    │ │
│  │  (Left + Right, separate)   │  │  (Phase 1)   │ │
│  └──────────────┬──────────────┘  └──────────────┘ │
│                 │                                    │
│  ┌──────────────▼──────────────┐  ┌──────────────┐ │
│  │   Encoder Input Capture     │  │  Ramping     │ │
│  │ (Quadrature, timer-based)   │  │  (Phase 1)   │ │
│  └──────────────┬──────────────┘  └──────────────┘ │
│                 │                                    │
│  ┌──────────────▼──────────────┐                    │
│  │    PWM + Motor Outputs      │  (Phase 1)        │
│  └─────────────────────────────┘                    │
│                                                      │
│  ┌─────────────────────────────────────────────────┐│
│  │  Telemetry Tx (Enhanced)                        ││
│  │  - PWM values                                   ││
│  │  - Encoder ticks (cumulative)                   ││
│  │  - Velocity (ticks/sec)                         ││
│  │  - PID error terms (optional)                   ││
│  └─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

### Raspberry Pi Extensions

```
┌─────────────────────────────────────────────────────┐
│                 Raspberry Pi 4                       │
│  ┌────────────────────────────────────────────────┐ │
│  │         Teleop Service (Modified)              │ │
│  │  Input → velocity targets (m/s) instead of PWM │ │
│  └──────────────┬─────────────────────────────────┘ │
│                 │                                    │
│  ┌──────────────▼──────────────┐                    │
│  │   Hardware Gateway          │  (Phase 1)        │
│  │  - Send velocity DriveCmd   │                    │
│  │  - Receive EncoderData      │  ← NEW            │
│  └──────────────┬──────────────┘                    │
│                 │                                    │
│  ┌──────────────▼──────────────┐                    │
│  │    State Estimator (NEW)    │                    │
│  │  - Integrate encoder ticks  │                    │
│  │  - Compute (x, y, θ) pose   │                    │
│  │  - Publish Odometry         │                    │
│  └─────────────────────────────┘                    │
│                                                      │
│  ┌─────────────────────────────────────────────────┐│
│  │  UI (Enhanced)                                  ││
│  │  - Display velocity (m/s)                       ││
│  │  - Show odometry (x, y, θ)                      ││
│  │  - Plot speed vs target                         ││
│  └─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

---

## Protocol Extensions

### Updated DriveCmd Payload

**Option 1: Velocity Mode (Recommended)**

Add a "control mode" flag to DriveCmd:

```c
// Extended DriveCmd payload (8 bytes)
typedef struct __attribute__((packed)) {
    int16_t left_target;        // Target (Q15 speed OR velocity)
    int16_t right_target;       // Target (Q15 speed OR velocity)
    uint16_t flags;             // Control flags
    uint16_t control_mode;      // NEW: 0=open-loop, 1=velocity PID
} DriveCmdPayload_t;
```

**Flags** (existing):
- Bit 0: `ESTOP`
- Bit 1: `ENABLE_REQUEST`

**Control Mode**:
- `0`: Open-loop (Phase 1 behavior, direct PWM via Q15)
- `1`: Velocity PID (target is velocity in ticks/sec, scaled)

**Backward Compatibility**: If `control_mode == 0`, behaves exactly as Phase 1.

---

### New EncoderData Message

Already defined in Phase 1 protocol spec as message type `0x11`:

```c
// EncoderData payload (16 bytes)
typedef struct __attribute__((packed)) {
    int32_t left_ticks;       // Cumulative ticks since boot
    int32_t right_ticks;      // Cumulative ticks since boot
    int16_t left_vel;         // Velocity (ticks/sec, scaled)
    int16_t right_vel;        // Velocity (ticks/sec, scaled)
    uint32_t timestamp;       // dsPIC millisecond timestamp
} EncoderDataPayload_t;
```

**Transmission Rate**: 50 Hz (same as command rate for tight coupling)

---

### Updated Telemetry

Extend existing Telemetry payload (backward compatible):

```c
// Enhanced Telemetry payload (16 bytes)
typedef struct __attribute__((packed)) {
    int16_t left_pwm;         // Current PWM (Phase 1)
    int16_t right_pwm;        // Current PWM (Phase 1)
    uint16_t bus_mv;          // Bus voltage (Phase 1)
    uint16_t fault_flags;     // Fault flags (Phase 1)
    uint16_t age_ms;          // Command age (Phase 1)
    
    // NEW Phase 2 fields:
    int16_t left_error;       // PID error (target - actual), ticks/sec
    int16_t right_error;      // PID error
    uint16_t control_mode;    // Active control mode
} TelemetryPayload_Phase2_t;
```

**Backward Compatibility**: First 10 bytes identical to Phase 1. Pi can detect payload length and parse accordingly.

---

## Encoder Hardware & Interfacing

### Encoder Selection

**Recommended**: Motors with integrated quadrature encoders
- **Resolution**: 500-2000 PPR (pulses per revolution)
- **Output**: Quadrature (A/B channels)
- **Voltage**: 3.3V or 5V (with level shifter if needed)

### dsPIC Encoder Interface

**Option 1: QEI Module (Quadrature Encoder Interface)**
- dsPIC33CK has hardware QEI module (QEI1, QEI2)
- Automatically counts edges on A/B channels
- Direction detection in hardware
- Minimal CPU overhead

**Option 2: Input Capture + Timer**
- Use input capture for rising/falling edges
- Software state machine for direction
- More flexible but higher CPU

**Recommendation**: Use QEI module (easiest and most robust).

### Pin Assignments

Add to `config.h`:
```c
// Left encoder (QEI1)
#define ENCODER_LEFT_A_PIN    _RB8
#define ENCODER_LEFT_B_PIN    _RB9

// Right encoder (QEI2)
#define ENCODER_RIGHT_A_PIN   _RB10
#define ENCODER_RIGHT_B_PIN   _RB11
```

---

## PID Speed Control

### PID Algorithm

Each motor has an independent PID controller:

```c
typedef struct {
    float kp;           // Proportional gain
    float ki;           // Integral gain
    float kd;           // Derivative gain
    
    float setpoint;     // Target velocity (ticks/sec)
    float error;        // Current error
    float error_sum;    // Integral term
    float error_prev;   // Previous error (for derivative)
    
    float output;       // PWM output (-10000 to +10000)
} PIDController_t;
```

**Update Rate**: 100 Hz (every 10 ms)
- Too fast: noisy velocity measurements
- Too slow: sluggish response

**PID Computation** (discrete form):
```c
void pid_update(PIDController_t *pid, float measured_velocity, float dt) {
    // Error
    pid->error = pid->setpoint - measured_velocity;
    
    // Integral (with anti-windup)
    pid->error_sum += pid->error * dt;
    if (pid->error_sum > INTEGRAL_MAX) pid->error_sum = INTEGRAL_MAX;
    if (pid->error_sum < -INTEGRAL_MAX) pid->error_sum = -INTEGRAL_MAX;
    
    // Derivative
    float error_rate = (pid->error - pid->error_prev) / dt;
    pid->error_prev = pid->error;
    
    // Output
    pid->output = (pid->kp * pid->error) +
                  (pid->ki * pid->error_sum) +
                  (pid->kd * error_rate);
    
    // Clamp output
    if (pid->output > PWM_RESOLUTION) pid->output = PWM_RESOLUTION;
    if (pid->output < -PWM_RESOLUTION) pid->output = -PWM_RESOLUTION;
}
```

### Tuning Procedure

**1. Start with P-only (ki=0, kd=0)**:
- Set kp = 1.0, test step response
- Increase kp until oscillation starts
- Back off to 50% of oscillation point

**2. Add Integral**:
- Set ki = 0.1 * kp
- Reduce steady-state error
- Watch for windup (integral grows unbounded)

**3. Add Derivative**:
- Set kd = 0.01 * kp
- Smooth overshoot
- May amplify noise, use carefully

**4. Fine-tune**:
- Test on different surfaces (carpet, tile, concrete)
- Test with different loads
- Tune for smooth response without oscillation

**Tuning Tool** (Pi-side):
- Web UI with real-time plots (target vs actual velocity)
- Adjust PID gains via API
- Save tuned values to config

---

## Velocity Measurement

### Encoder Velocity Calculation

**Method 1: Tick Counting (Low Speed)**
- Count ticks over fixed time window (e.g., 100 ms)
- Velocity = ticks / dt
- Good for low speeds, quantized at high speeds

**Method 2: Period Measurement (High Speed)**
- Measure time between ticks
- Velocity = 1 / period
- Good for high speeds, noisy at low speeds

**Method 3: Hybrid**
- Use tick counting at low speed
- Use period measurement at high speed
- Switch threshold: ~10 ticks/sec

**Recommendation for Phase 2**: Start with tick counting (simpler).

### Low-Pass Filter

Raw velocity is noisy. Apply simple exponential filter:
```c
float filtered_velocity = alpha * raw_velocity + (1 - alpha) * filtered_velocity_prev;
```
- `alpha = 0.2` for 100 Hz update → ~5 Hz cutoff

---

## State Estimator (Odometry)

### Differential Drive Kinematics

Given:
- `L`: wheelbase (distance between left/right wheels)
- `r`: wheel radius
- `ticks_per_rev`: encoder resolution
- `Δticks_left`, `Δticks_right`: tick increments

Compute:
```python
# Convert ticks to distance
distance_per_tick = (2 * pi * r) / ticks_per_rev
d_left = delta_ticks_left * distance_per_tick
d_right = delta_ticks_right * distance_per_tick

# Center distance and rotation
d_center = (d_left + d_right) / 2
d_theta = (d_right - d_left) / L

# Update pose (x, y, theta)
x += d_center * cos(theta + d_theta / 2)
y += d_center * sin(theta + d_theta / 2)
theta += d_theta
```

### Odometry Message

Define new message type on Pi:

```python
class Odometry(BaseModel):
    """Robot pose from wheel odometry"""
    x: float  # meters
    y: float  # meters
    theta: float  # radians
    v_linear: float  # m/s (forward velocity)
    v_angular: float  # rad/s (turn rate)
    timestamp: datetime
```

**Published to**: `odometry` topic on message bus

---

## Configuration Extensions

### `config.h` (dsPIC)

Add Phase 2 parameters:

```c
// Encoder configuration
#define ENCODER_LEFT_PPR    1024    // Pulses per revolution
#define ENCODER_RIGHT_PPR   1024

// PID control
#define PID_UPDATE_FREQ_HZ  100     // 100 Hz PID loop
#define PID_Kp              1.0f
#define PID_Ki              0.1f
#define PID_Kd              0.01f
#define PID_INTEGRAL_MAX    5000    // Anti-windup limit

// Velocity scaling
#define VELOCITY_SCALE      10      // Velocity reported as ticks/sec / 10
```

### `rover_config.yaml` (Pi)

Add Phase 2 section:

```yaml
encoders:
  enabled: true
  ticks_per_rev: 1024
  wheel_radius_m: 0.075  # 7.5 cm radius wheels
  wheelbase_m: 0.35      # 35 cm between wheels

pid_tuning:
  kp: 1.0
  ki: 0.1
  kd: 0.01
  
state_estimator:
  enabled: true
  publish_rate_hz: 50
```

---

## Implementation Checklist

### dsPIC Firmware

- [ ] **Enable QEI modules** (QEI1, QEI2)
- [ ] **Configure encoder input pins**
- [ ] **Implement encoder tick reading** (read POS1CNT, POS2CNT registers)
- [ ] **Implement velocity calculation** (tick counting with filter)
- [ ] **Add PID controller struct and update function**
- [ ] **Integrate PID into 100 Hz loop** (separate from 1 kHz control loop)
- [ ] **Add control mode handling** (open-loop vs closed-loop)
- [ ] **Implement EncoderData transmission** (50 Hz)
- [ ] **Extend Telemetry with PID error terms**
- [ ] **Test encoder direction** (forward = positive ticks)

### Raspberry Pi

- [ ] **Extend DriveCmd encoder** to support control mode
- [ ] **Add EncoderData parser** in protocol.py
- [ ] **Create state_estimator service**:
  - Subscribe to `encoder_data` topic
  - Compute odometry
  - Publish `odometry` topic
- [ ] **Modify teleop to output velocity** (m/s) instead of normalized speed
- [ ] **Add velocity conversion** (m/s → ticks/sec in hardware gateway)
- [ ] **Extend UI**:
  - Display velocity (m/s)
  - Display odometry (x, y, θ)
  - Plot velocity vs target (real-time chart)
- [ ] **Add PID tuning page** (optional, can be CLI tool)

### Calibration

- [ ] **Measure wheel radius** accurately (roll wheel on floor, measure distance)
- [ ] **Measure wheelbase** (center-to-center of wheels)
- [ ] **Verify encoder tick counts** (rotate wheel 1 revolution, count ticks)
- [ ] **Test encoder direction** (positive forward, negative backward for both wheels)
- [ ] **Tune PID gains** (start with P-only, follow tuning procedure)
- [ ] **Validate odometry** (drive in square, measure error)

---

## Testing & Validation

### Test 1: Encoder Reading

**Objective**: Verify encoders are read correctly

**Procedure**:
1. Lift wheels off ground
2. Manually rotate left wheel forward 1 revolution
3. Check EncoderData telemetry
4. **Expected**: `left_ticks` increases by ~1024 (for 1024 PPR)
5. Rotate backward
6. **Expected**: `left_ticks` decreases
7. Repeat for right wheel

**Success**: Encoder counts match expected values and directions.

---

### Test 2: PID Step Response

**Objective**: Validate PID control

**Procedure**:
1. Wheels off ground
2. Command 0.3 m/s velocity
3. Observe telemetry velocity vs target
4. Plot on UI
5. **Expected**:
   - Velocity ramps up to target
   - Settles within 10% of target
   - Minimal overshoot
   - No sustained oscillation

**Success**: Smooth response, target achieved within 1-2 seconds.

---

### Test 3: Straight Line Drive

**Objective**: Verify differential control maintains straight path

**Procedure**:
1. Place rover on floor
2. Command equal velocity for both wheels (0.3 m/s)
3. Drive 3 meters forward
4. Measure deviation from straight line
5. **Expected**: < 10 cm lateral error

**Success**: Rover drives reasonably straight (some deviation is normal without yaw feedback).

---

### Test 4: Odometry Validation

**Objective**: Check odometry accuracy

**Procedure**:
1. Place rover at origin (0, 0, 0°)
2. Drive in 1m × 1m square:
   - Forward 1m
   - Turn left 90°
   - Forward 1m
   - Turn left 90°
   - Forward 1m
   - Turn left 90°
   - Forward 1m
3. Measure final odometry position
4. **Expected**: Close to (0, 0, 0°)

**Success**: Position error < 10 cm, angle error < 10°.

**Note**: Odometry drift is expected (no absolute position correction yet). Phase 3 will add marker-based localization.

---

### Test 5: Different Surfaces

**Objective**: Verify PID compensates for load changes

**Procedure**:
1. Command 0.3 m/s velocity
2. Drive on carpet
3. Note velocity achieved (should be ~0.3 m/s)
4. Drive on tile
5. Note velocity achieved (should still be ~0.3 m/s)

**Success**: Velocity maintained across surfaces (within 10%).

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Encoder noise** | Velocity oscillates, PID unstable | Low-pass filter, test shielded cables |
| **Wheel slip** | Odometry diverges | Detect slip (high error), warn in UI |
| **PID instability** | Motors oscillate or run away | Conservative tuning, output limits, watchdog still active |
| **Tick overflow** | int32 ticks wrap after ~2 million revs | Track cumulative ticks carefully, handle wrap in Pi |
| **Calibration errors** | Odometry drifts faster | Careful measurement, validation tests |
| **CPU load** | dsPIC can't keep up with 100 Hz PID + 1 kHz control | Profile code, optimize if needed, reduce PID rate if necessary |

---

## Backward Compatibility

Phase 2 design maintains **full backward compatibility** with Phase 1:

1. **Control Mode 0**: If `control_mode == 0`, dsPIC behaves exactly as Phase 1 (open-loop PWM control)
2. **Telemetry Length**: Phase 1 Pi code can parse Phase 2 telemetry (first 10 bytes unchanged)
3. **Optional Encoder Messages**: Pi ignores EncoderData if state estimator not enabled
4. **Config Flag**: `encoders.enabled: false` in config disables all Phase 2 features

**Migration Path**:
- Flash Phase 2 firmware to dsPIC
- Leave Pi config with `encoders.enabled: false`
- System works exactly as Phase 1
- Enable encoders when ready

---

## Phase 3 Preview

After Phase 2 validated, Phase 3 adds:
- **Perception**: Object detection, marker recognition
- **Sensor Fusion**: IMU + encoders (Extended Kalman Filter)
- **Marker-based Localization**: AprilTag / ArUco for absolute position correction
- **Planning**: Simple path planning with obstacle avoidance

Phase 2 odometry provides the foundation for Phase 3 navigation.

---

## References

- **PID Tuning**: "PID Without a PhD" by Tim Wescott
- **Odometry**: "Introduction to Autonomous Mobile Robots" (Siegwart & Nourbakhsh)
- **dsPIC QEI**: dsPIC33CK datasheet, Section 14: Quadrature Encoder Interface
- **Kinematics**: "Mobile Robotics" course notes

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-29 | Rover Team | Initial Phase 2 planning |


