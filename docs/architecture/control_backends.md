# Motor Control Backends

## Overview

The rover software supports **pluggable motor control backends**, allowing you to choose between:
1. **Pi PWM** (`pi_pwm`): Direct GPIO control of L298N for quick bringup
2. **UART** (`uart`): dsPIC microcontroller via UART for robust, real-time control

This architecture allows weekend bringup with the Pi, while preserving the path to production-grade dsPIC control.

## Architecture

```
UI (WebSocket) → API Server → Teleop Service → MotorController (interface)
                                                        ↓
                                        ┌───────────────┴─────────────┐
                                        │                             │
                                  UartMotorController         PiPwmMotorController
                                        │                             │
                                  HardwareGateway                  RPi.GPIO
                                  (UART protocol)                  (L298N PWM)
                                        │                             │
                                      dsPIC                         Motors
                                        │
                                      Motors
```

The `MotorController` interface provides a common API:
- `send_drive_command(cmd)`: Send normalized drive command (-1 to +1)
- `get_status()`: Get current status (enabled, last command time, faults)
- `get_telemetry()`: Get telemetry (if available)
- `get_link_status()`: Get link status (if available)

## Backend Selection

Backends are selected via `rover_config.yaml`:

```yaml
control:
  backend: "pi_pwm"  # or "uart"
```

The API server reads this config on startup and instantiates the appropriate backend.

## Pi PWM Backend (`pi_pwm`)

**Purpose:** Quick bringup and development. Directly drives L298N from Pi GPIO.

**Pros:**
- Simple wiring (Pi → L298N → Motors)
- No firmware required
- Fast iteration
- Good for Phase 1 teleoperation

**Cons:**
- No hardware watchdog (relies on software timers)
- No real-time guarantees (Linux scheduling jitter)
- No motor feedback (no encoders, no current sensing)
- Limited to ~1 kHz PWM frequency (software PWM)

**Implementation:**
- Location: `Raspberry Pi/pi/apps/motor_pi_pwm/pi_pwm_motor_controller.py`
- Uses `RPi.GPIO` for software PWM
- Safety: stale command detection, GPIO cleanup on exit

**Configuration:**
```yaml
control:
  backend: "pi_pwm"
  
  pi_pwm:
    left_in1: 17    # GPIO BCM numbering
    left_in2: 27
    left_ena: 18
    right_in3: 23
    right_in4: 24
    right_enb: 13
    pwm_frequency: 1000  # Hz
    max_command_age_ms: 250
    deadband: 0.05
```

**Wiring:** See [docs/bringup/pi_pwm_l298n_wiring.md](../bringup/pi_pwm_l298n_wiring.md)

## UART Backend (`uart`)

**Purpose:** Production-grade real-time motor control with hardware safety.

**Pros:**
- Hardware watchdog (motors stop if UART fails)
- Real-time execution (deterministic 1ms control loop)
- High-frequency PWM (20 kHz+, less audible, more efficient)
- Motor telemetry (PWM, voltage, faults)
- Future: encoder support, current sensing, PID control

**Cons:**
- Requires dsPIC firmware development
- More complex wiring (Pi ↔ dsPIC ↔ L298N)
- Firmware flashing required

**Implementation:**
- Location: `Raspberry Pi/pi/apps/motor_uart/uart_motor_controller.py`
- Wraps existing `HardwareGateway` (unchanged)
- Uses robust binary UART protocol with CRC

**Configuration:**
```yaml
control:
  backend: "uart"

# UART settings (already defined)
uart:
  port: "/dev/serial0"
  baudrate: 115200
  protocol_version: "v1_binary"

hardware_gateway:
  command_rate_hz: 50
  max_command_age_ms: 250
```

**Protocol:** See [docs/protocols/uart_protocol_v1.md](../protocols/uart_protocol_v1.md)

**dsPIC Firmware:** See [dsPIC33CK64MC105/firmware/README.md](../../dsPIC33CK64MC105/firmware/README.md)

## Switching Backends

### Pi PWM → UART (when dsPIC is ready)

1. **Wire dsPIC:**
   - Pi GPIO 14 (UART TX) → dsPIC RX
   - Pi GPIO 15 (UART RX) → dsPIC TX
   - Common ground
   - dsPIC → L298N (see dsPIC pinout)

2. **Flash dsPIC firmware:**
   ```bash
   cd dsPIC33CK64MC105/firmware
   make flash
   ```

3. **Update config:**
   ```yaml
   control:
     backend: "uart"
   ```

4. **Restart rover:**
   ```bash
   ./scripts/rover_bringup.sh
   ```

5. **Verify UART link:**
   - Check logs: `Opened serial port: /dev/serial0 @ 115200`
   - Check `/api/v1/health`: `frames_sent > 0`, `frames_received > 0`

### UART → Pi PWM (fallback for debugging)

1. **Update config:**
   ```yaml
   control:
     backend: "pi_pwm"
   ```

2. **Restart rover:**
   ```bash
   ./scripts/rover_bringup.sh
   ```

3. **Note:** dsPIC can remain wired but will be inactive (no UART traffic)

## Feature Comparison

| Feature                | Pi PWM Backend | UART Backend |
|------------------------|----------------|--------------|
| Quick bringup          | ✅ Yes         | ❌ No (needs firmware) |
| Hardware watchdog      | ❌ No          | ✅ Yes (200ms timeout) |
| Real-time guarantees   | ❌ No          | ✅ Yes (1ms loop) |
| PWM frequency          | ~1 kHz         | 20+ kHz |
| Motor telemetry        | ❌ No          | ✅ Yes (PWM, voltage, faults) |
| Encoder support        | ❌ No          | ✅ Yes (future) |
| Current sensing        | ❌ No          | ✅ Yes (future) |
| Fault reporting        | ❌ No          | ✅ Yes |
| Configuration reload   | Restart required | Restart required |

## Adding a New Backend

To add a third backend (e.g., CAN bus, I2C motor driver):

1. **Implement `MotorController` interface:**
   ```python
   from lib.motor.motor_controller import MotorController
   
   class MyMotorController(MotorController):
       async def start(self): ...
       async def stop(self): ...
       async def send_drive_command(self, cmd): ...
       def get_status(self): ...
       def get_telemetry(self): ...
       def get_link_status(self): ...
   ```

2. **Add config section:**
   ```yaml
   control:
     backend: "my_backend"
     
     my_backend:
       # Your settings
   ```

3. **Wire into `api_server.py`:**
   ```python
   elif backend == "my_backend":
       app_state.motor_controller = MyMotorController(...)
   ```

## Testing

### Smoke Test (Any Backend)
```bash
# Start server
./scripts/rover_bringup.sh

# In browser: http://<pi-ip>:8000
# Press W, observe motors spin forward
# Close tab, observe motors stop
```

### Backend-Specific Tests

**Pi PWM:**
- `gpio readall` → verify pins are exported
- Multimeter on ENA/ENB → verify PWM duty changes with W/S
- Oscilloscope → measure PWM frequency (~1 kHz)

**UART:**
- Check `/api/v1/health` → `frames_sent > 0`, `frames_received > 0`
- Check logs → no CRC errors
- Disconnect dsPIC → motors stop within 250ms (watchdog)

## Current Status

- **Pi PWM backend:** ✅ Fully implemented and tested
- **UART backend:** ✅ Pi-side complete, dsPIC firmware in development
- **Future backends:** Placeholder for CAN, I2C, etc.

## Design Rationale

### Why Pluggable Backends?

1. **Iterative development:** Drive today with Pi, migrate to dsPIC later
2. **Fault tolerance:** Fallback to Pi PWM if dsPIC fails
3. **Simulation:** Future "dummy" backend for CI/testing
4. **Flexibility:** Easy to add new motor drivers (e.g., VESC, ODrive)

### Why Keep Both?

- **Pi PWM:** Great for rapid prototyping, demos, and new feature testing
- **UART/dsPIC:** Required for production (safety, encoders, high-frequency PWM)

### Lessons Learned

The original plan was dsPIC-only, but:
- Firmware development took longer than expected
- Hardware bring-up revealed pin conflicts
- Weekend demos needed a working rover

The pluggable backend architecture allows parallel work:
- **You:** Iterate on Pi software (UI, vision, navigation)
- **Teammate:** Finish dsPIC firmware
- **Integration:** One config change to switch backends

## See Also

- [Pi PWM Wiring Guide](../bringup/pi_pwm_l298n_wiring.md)
- [UART Protocol Specification](../protocols/uart_protocol_v1.md)
- [dsPIC Firmware README](../../dsPIC33CK64MC105/firmware/README.md)
- [Phase 1 Demo Checklist](../bringup/phase1_demo_checklist.md)

