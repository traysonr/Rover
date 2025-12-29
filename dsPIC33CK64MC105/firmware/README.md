# dsPIC33CK64MC105 Rover Firmware

## Overview

Phase 1 firmware for the autonomous rover platform. Provides:
- Binary/ASCII UART protocol
- Motor PWM control with acceleration ramping
- Command watchdog (200ms timeout)
- Telemetry transmission (20 Hz)
- Fault detection and safe shutdown

## Directory Structure

```
firmware/
├── include/          # Header files
│   ├── config.h      # Configuration parameters
│   ├── protocol.h    # UART protocol definitions
│   ├── motor_control.h
│   ├── watchdog.h
│   └── telemetry.h
├── src/              # Implementation files
│   ├── main.c        # Main control loop
│   ├── protocol.c    # Protocol parser/encoder
│   ├── motor_control.c
│   ├── watchdog.c
│   └── telemetry.c
├── docs/             # Documentation
├── tests/            # Unit tests (host-based if possible)
├── Makefile          # Build system
└── README.md         # This file
```

## Building

### Prerequisites

- Microchip XC16 compiler (v2.00 or later)
- MPLAB X IDE (optional, for GUI development)
- Programmer: PICkit 4, ICD 4, or compatible

### Build Commands

```bash
# Build firmware
make

# Clean build artifacts
make clean

# Rebuild from scratch
make rebuild

# Program device (requires programmer)
make program
```

### Build Output

- `bin/rover_firmware.elf` - ELF executable (for debugging)
- `bin/rover_firmware.hex` - Intel HEX format (for programming)

## Hardware Configuration

### Pin Assignments

**IMPORTANT**: Update `config.h` to match your hardware before building!

Default pin assignments (example):
- **Left Motor**:
  - PWM: RB0
  - DIR1: RB1
  - DIR2: RB2
- **Right Motor**:
  - PWM: RB3
  - DIR1: RB4
  - DIR2: RB5
- **Status LED**: RB6
- **Fault LED**: RB7
- **UART**:
  - TX: RP (remappable, check datasheet)
  - RX: RP (remappable, check datasheet)

### PWM Configuration

- **Frequency**: 20 kHz (suitable for L298N)
- **Resolution**: ±10000 = ±100.00%
- Adjust `PWM_FREQUENCY_HZ` in `config.h` for different motor drivers

### UART Configuration

- **Baud**: 115200
- **Format**: 8N1
- **Flow Control**: None
- Connected to Raspberry Pi GPIO14/15

## Configuration

Edit `include/config.h` to adjust:

### Safety Parameters
- `WATCHDOG_TIMEOUT_MS`: Command timeout (default 200ms)
- `NORMAL_RAMP_TIME_MS`: Acceleration ramp time (default 2000ms)
- `ESTOP_RAMP_TIME_MS`: E-stop deceleration time (default 50ms)

### Voltage Thresholds
- `VOLTAGE_MIN_MV`: Undervoltage threshold (default 9000mV)
- `VOLTAGE_MAX_MV`: Overvoltage threshold (default 13000mV)

### Timing
- `TIMER_FREQ_HZ`: Control loop frequency (fixed at 1000 Hz)
- `TELEMETRY_RATE_HZ`: Telemetry transmission rate (default 20 Hz)

## Protocol

See `docs/protocols/uart_protocol_v1.md` for complete protocol specification.

### Quick Reference

**Binary Protocol** (default):
- SOF: `0xAA 0x55`
- CRC-16/CCITT-FALSE for validation
- DriveCmd (0x01): Set motor speeds
- Telemetry (0x10): Status feedback

**ASCII Protocol** (fallback for debugging):
- Drive: `D <left> <right>\n` (e.g., `D 0.5 -0.3\n`)
- Stop: `S\n`
- Enable: `E\n`

## Operation

### Boot Sequence

1. Initialize hardware (clock, timers, PWM, UART)
2. Enter `STATE_BOOT` with motors disabled
3. Begin sending telemetry
4. Await first DriveCmd with `ENABLE_REQUEST` flag

### Normal Operation

- Control loop runs at 1 kHz (Timer1 interrupt)
- Processes UART commands (interrupt-driven)
- Updates motor ramping
- Checks for faults
- Sends telemetry at 20 Hz

### Fault Handling

If any fault occurs:
1. Motors ramp to zero
2. Outputs disabled
3. Fault flags set in telemetry
4. Await fault clear + enable request

### Watchdog Behavior

- Timeout: 200ms without valid command
- Action: Set `FAULT_WATCHDOG_TIMEOUT`, ramp to stop, disable outputs
- Clear: Automatic on next valid command

## Testing

### Unit Tests (Host-Based)

Protocol parser can be tested on host PC:

```bash
gcc -I include -o test_protocol src/protocol.c tests/test_protocol.c
./test_protocol
```

### Hardware Tests

1. **UART Loopback**: Connect TX → RX, verify echo
2. **PWM Output**: Scope PWM pins, verify frequency/duty cycle
3. **Watchdog**: Stop sending commands, verify timeout and stop
4. **Ramping**: Step command, verify smooth acceleration

## Debugging

### LED Indicators

- **Status LED**: Blinks at 1 Hz when running
- **Fault LED**: Solid when fault active

### UART Diagnostics

Parser statistics available in `ProtocolParser_t`:
- `frames_received`: Total valid frames
- `crc_errors`: CRC validation failures
- `version_errors`: Protocol version mismatches

### Common Issues

**Motors don't move**:
- Check `ENABLE_REQUEST` flag is set
- Verify no faults active (check telemetry)
- Confirm PWM frequency matches motor driver

**UART errors**:
- Verify baud rate matches Pi (115200)
- Check common ground connection
- Test with ASCII protocol first (easier to debug)

**Watchdog timeout**:
- Pi must send commands at ≥5 Hz (recommended 50 Hz)
- Check UART cable connection

## Phase 2 Extensions (Future)

- Encoder input capture
- PID speed control
- Closed-loop velocity feedback
- Encoder telemetry (message type 0x11)

## References

- dsPIC33CK64MC105 Datasheet
- XC16 Compiler User Guide
- `docs/protocols/uart_protocol_v1.md`
- `docs/safety/fault_modes.md`

## License

MIT License (or specify your license)

## Version History

- v1.0.0 (2025-12-29): Initial Phase 1 implementation

