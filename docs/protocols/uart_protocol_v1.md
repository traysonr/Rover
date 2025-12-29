# Rover UART Protocol Specification

## Document Information
- **Version**: 1.0
- **Status**: Active
- **Last Updated**: 2025-12-29
- **Authors**: Rover Team

## Overview

This document specifies the serial communication protocol between the Raspberry Pi 4 (host) and the dsPIC33CK64MC105 microcontroller (device) for the autonomous rover platform.

### Design Goals
1. **Robustness**: Handle noise, partial frames, and byte stream corruption
2. **Safety**: Explicit timeouts, watchdogs, and fault signaling
3. **Simplicity**: Easy to implement and debug on embedded systems
4. **Extensibility**: Version byte allows future protocol evolution
5. **Efficiency**: Minimal overhead while maintaining reliability

### Communication Parameters
- **Physical Layer**: UART, 115200 baud, 8N1 (8 data bits, no parity, 1 stop bit)
- **Direction**: Bidirectional
- **Wiring**: Pi GPIO14 (TXD) → dsPIC RX, Pi GPIO15 (RXD) ← dsPIC TX
- **Ground**: Common ground required between Pi and dsPIC

---

## Protocol Version 1 (Binary Framed)

### Frame Structure

All messages follow this binary frame format:

```
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────────┬──────────┐
│ SOF[0]  │ SOF[1]  │ Version │ MsgType │   Seq   │   Len   │   Payload   │  CRC16   │
│  0xAA   │  0x55   │  (u8)   │  (u8)   │  (u8)   │  (u8)   │  (Len bytes)│  (u16)   │
├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────────┼──────────┤
│ Byte 0  │ Byte 1  │ Byte 2  │ Byte 3  │ Byte 4  │ Byte 5  │  Bytes 6..N │ N+1, N+2 │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────────┴──────────┘
```

### Field Descriptions

| Field | Size | Description |
|-------|------|-------------|
| **SOF** | 2 bytes | Start-of-frame marker: `0xAA 0x55` (big-endian) |
| **Version** | 1 byte | Protocol version: `0x01` for this specification |
| **MsgType** | 1 byte | Message type identifier (see Message Types below) |
| **Seq** | 1 byte | Sequence number (wraps at 255), incremented by sender |
| **Len** | 1 byte | Payload length in bytes (0-255) |
| **Payload** | 0-255 bytes | Message-specific data (format defined per MsgType) |
| **CRC16** | 2 bytes | CRC-16/CCITT-FALSE (polynomial 0x1021, init 0xFFFF, no XOR out), little-endian |

### CRC Calculation

- **Algorithm**: CRC-16/CCITT-FALSE
- **Polynomial**: 0x1021
- **Initial Value**: 0xFFFF
- **XOR Out**: 0x0000
- **Reflection**: None
- **Byte Order**: Little-endian (LSB first)
- **Coverage**: Version through end of Payload (excludes SOF and CRC itself)

Example C implementation:
```c
uint16_t crc16_ccitt(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x8000)
                crc = (crc << 1) ^ 0x1021;
            else
                crc = crc << 1;
        }
    }
    return crc;
}
```

---

## Message Types (Version 1)

### 0x01: DriveCmd (Pi → dsPIC)

**Purpose**: Command motor speeds for skid-steer drive

**Payload Format** (6 bytes):
```
┌──────────────┬──────────────┬──────────────┐
│  left_q15    │  right_q15   │    flags     │
│   (int16)    │   (int16)    │   (uint16)   │
│  Bytes 0-1   │  Bytes 2-3   │  Bytes 4-5   │
└──────────────┴──────────────┴──────────────┘
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `left_q15` | int16 | -32767 to +32767 | Left motor speed in Q15 format (-1.0 to +1.0) |
| `right_q15` | int16 | -32767 to +32767 | Right motor speed in Q15 format (-1.0 to +1.0) |
| `flags` | uint16 | bit flags | Control flags (see below) |

**Flags Bits**:
- Bit 0: `ESTOP` - Emergency stop (1 = stop immediately, ignore speed values)
- Bit 1: `ENABLE_REQUEST` - Request drive enable (must be set for motion)
- Bit 2: Reserved (set to 0)
- Bit 3: Reserved (set to 0)
- Bit 4-15: Reserved (set to 0)

**Q15 Format**: Fixed-point representation where -32767 maps to -1.0 and +32767 maps to +1.0
- Conversion: `q15 = (int16_t)(speed_float * 32767.0f)`
- Inverse: `speed_float = (float)q15 / 32767.0f`

**Byte Order**: Little-endian (LSB first)

**Example**:
```
Speed left=0.5, right=-0.3, enable=1
left_q15  = 0.5 * 32767 = 16383 = 0x3FFF
right_q15 = -0.3 * 32767 = -9830 = 0xD98A
flags = 0x0002 (enable bit set)

Payload: FF 3F 8A D9 02 00
```

---

### 0x02: StopCmd (Pi → dsPIC)

**Purpose**: Explicit stop command (alternative to ESTOP flag)

**Payload Format**: Empty (0 bytes)

**Behavior**: Equivalent to DriveCmd with ESTOP flag set. dsPIC immediately ramps motors to zero.

---

### 0x10: Telemetry (dsPIC → Pi)

**Purpose**: Periodic status and sensor feedback from dsPIC

**Payload Format** (10 bytes):
```
┌────────────┬────────────┬────────────┬──────────────┬──────────┐
│ left_pwm   │ right_pwm  │  bus_mv    │ fault_flags  │ age_ms   │
│  (int16)   │  (int16)   │  (uint16)  │   (uint16)   │ (uint16) │
│ Bytes 0-1  │ Bytes 2-3  │ Bytes 4-5  │  Bytes 6-7   │ Bytes 8-9│
└────────────┴────────────┴────────────┴──────────────┴──────────┘
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `left_pwm` | int16 | -10000 to +10000 | Left motor PWM duty cycle (scaled to ±100.00%) |
| `right_pwm` | int16 | -10000 to +10000 | Right motor PWM duty cycle (scaled to ±100.00%) |
| `bus_mv` | uint16 | 0-65535 | Bus voltage in millivolts |
| `fault_flags` | uint16 | bit flags | Active fault conditions |
| `age_ms` | uint16 | 0-65535 | Milliseconds since last valid DriveCmd received |

**PWM Scaling**: -10000 = -100.00%, +10000 = +100.00% (allows 0.01% resolution)

**Fault Flags Bits**:
- Bit 0: `WATCHDOG_TIMEOUT` - No valid command received within timeout window
- Bit 1: `ESTOP_ACTIVE` - Emergency stop engaged
- Bit 2: `UNDERVOLTAGE` - Bus voltage below safe threshold
- Bit 3: `OVERVOLTAGE` - Bus voltage above safe threshold
- Bit 4: `DRIVER_FAULT` - Motor driver fault signal detected
- Bit 5: `OVERCURRENT` - Current limit exceeded (if sensing available)
- Bit 6: `THERMAL_WARNING` - Temperature approaching limit
- Bit 7: Reserved
- Bit 8-15: Reserved

**Byte Order**: Little-endian

**Transmission Rate**: 10-20 Hz typical

---

### 0x11: EncoderData (dsPIC → Pi) [Phase 2]

**Purpose**: Wheel encoder feedback for odometry

**Payload Format** (16 bytes):
```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────┐
│ left_ticks   │ right_ticks  │ left_vel     │ right_vel    │timestamp │
│   (int32)    │   (int32)    │   (int16)    │   (int16)    │ (uint32) │
│  Bytes 0-3   │  Bytes 4-7   │  Bytes 8-9   │ Bytes 10-11  │Bytes 12-15│
└──────────────┴──────────────┴──────────────┴──────────────┴──────────┘
```

| Field | Type | Description |
|-------|------|-------------|
| `left_ticks` | int32 | Cumulative encoder ticks (left wheel) since boot |
| `right_ticks` | int32 | Cumulative encoder ticks (right wheel) since boot |
| `left_vel` | int16 | Instantaneous velocity in ticks/sec (scaled, TBD) |
| `right_vel` | int16 | Instantaneous velocity in ticks/sec (scaled, TBD) |
| `timestamp` | uint32 | dsPIC millisecond timestamp |

---

### 0x20: ConfigSet (Pi → dsPIC) [Future]

**Purpose**: Runtime configuration updates

**Payload Format**: TBD (key-value pairs or structured config)

---

### 0x21: ConfigGet (Pi → dsPIC) [Future]

**Purpose**: Request current configuration

---

### 0x22: ConfigResponse (dsPIC → Pi) [Future]

**Purpose**: Response to ConfigGet

---

### 0xFE: Heartbeat (Bidirectional) [Optional]

**Purpose**: Keep-alive and link quality check

**Payload Format** (2 bytes):
```
┌──────────────┬──────────────┐
│  timestamp   │   reserved   │
│   (uint8)    │   (uint8)    │
└──────────────┴──────────────┘
```

---

### 0xFF: ErrorReport (dsPIC → Pi)

**Purpose**: Detailed error/diagnostic information

**Payload Format** (variable):
```
┌──────────────┬──────────────┬─────────────────┐
│  error_code  │  error_data  │  debug_string   │
│   (uint8)    │   (uint8)    │   (N bytes)     │
└──────────────┴──────────────┴─────────────────┘
```

---

## Protocol Behavior

### Timing Requirements

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Command Update Rate (Pi→dsPIC)** | 20-50 Hz | Recommended: 50 Hz for smooth control |
| **Telemetry Rate (dsPIC→Pi)** | 10-20 Hz | Balance between data freshness and bandwidth |
| **Watchdog Timeout (dsPIC)** | 200 ms | Time before dsPIC declares command loss and stops |
| **Command Freshness (Pi)** | 100 ms | Pi should not send stale commands older than this |

### State Machine (dsPIC Perspective)

```
┌──────────────┐
│  BOOT/INIT   │ Outputs disabled, await first valid DriveCmd
└──────┬───────┘
       │ Valid DriveCmd with ENABLE_REQUEST
       ▼
┌──────────────┐
│   ENABLED    │ Outputs active, executing commands
└──┬────────┬──┘
   │        │
   │ Watchdog timeout or ESTOP
   ▼        │
┌──────────────┐
│  FAULTED     │ Outputs disabled, fault flag set
└──────┬───────┘
       │ Fault clear + valid DriveCmd with ENABLE_REQUEST
       ▼
   [Return to ENABLED]
```

### Parser State Machine (Receiver)

Both Pi and dsPIC implement this receive logic:

```
SCANNING_SOF:
  - Read bytes until 0xAA 0x55 found
  - Move to READING_HEADER

READING_HEADER:
  - Read Version, MsgType, Seq, Len (4 bytes)
  - Validate Version == 0x01
  - If invalid, return to SCANNING_SOF
  - Move to READING_PAYLOAD

READING_PAYLOAD:
  - Read Len bytes into payload buffer
  - Move to READING_CRC

READING_CRC:
  - Read 2 bytes (CRC16, little-endian)
  - Compute CRC over header+payload
  - If CRC matches: Process message, return to SCANNING_SOF
  - If CRC fails: Discard frame, increment error counter, return to SCANNING_SOF
```

### Error Handling

**CRC Mismatch**: Discard frame silently, increment diagnostic counter

**Unknown Message Type**: Ignore frame, optionally send ErrorReport (avoid loops)

**Payload Length Mismatch**: If payload length doesn't match expected for MsgType, discard frame

**Timeout (No Messages)**: Receiver should track time since last valid frame for diagnostics

### Resynchronization

- Parser always scans for SOF bytes, allowing automatic resync after corruption
- CRC provides strong validation (Hamming distance ≥4 for short frames)
- No acknowledgment required (trade latency for simplicity)
- Application layer (watchdog) handles link loss

---

## Protocol Version 0 (ASCII Fallback)

For bringup and debugging, a simple ASCII protocol is supported:

### Commands (Pi → dsPIC)

**Drive Command**:
```
D <left> <right>\n
```
- `<left>`, `<right>`: Float values in range [-1.0, 1.0]
- Example: `D 0.5 -0.3\n`

**Stop Command**:
```
S\n
```

**Enable Command**:
```
E\n
```

**Disable Command**:
```
X\n
```

### Responses (dsPIC → Pi)

**Telemetry**:
```
T <left_pwm> <right_pwm> <bus_mv> <fault> <age>\n
```
- Example: `T 5000 -3000 12000 0 45\n`

**Error**:
```
ERR <code> <message>\n
```

### ASCII Protocol Rules

1. All lines terminated with `\n` (LF, 0x0A)
2. Whitespace: Single space between fields
3. Numbers: Decimal ASCII
4. Max line length: 128 characters
5. Invalid lines: Ignored (optional error response)

### Migration Strategy

1. **Phase 0 (Bringup)**: Use ASCII only, easier to debug with terminal
2. **Phase 0.5 (Validation)**: Implement binary protocol, test with golden vectors
3. **Phase 1**: Switch to binary protocol as default
4. **Configuration**: Pi config file specifies protocol version (`uart_protocol: "v0_ascii"` or `"v1_binary"`)
5. **Firmware**: dsPIC auto-detects protocol by looking for SOF bytes vs ASCII characters
6. **Fallback**: If binary frames consistently fail CRC, optionally fall back to ASCII

---

## Implementation Checklist

### dsPIC Firmware

- [ ] UART driver with interrupt-driven RX ring buffer
- [ ] Binary frame parser with CRC validation
- [ ] ASCII fallback parser
- [ ] Message dispatch based on MsgType
- [ ] DriveCmd handler with Q15 conversion
- [ ] Telemetry periodic transmission
- [ ] Watchdog timer tracking command age
- [ ] Fault flag management
- [ ] State machine (BOOT → ENABLED → FAULTED)

### Raspberry Pi

- [ ] Binary frame encoder with CRC
- [ ] Serial port configuration (115200 8N1)
- [ ] DriveCmd transmission at fixed rate
- [ ] Telemetry parser
- [ ] Protocol version selection (config)
- [ ] Command freshness tracking
- [ ] Diagnostic counters (frames sent, received, CRC errors)

### Testing

- [ ] Golden vector tests (known frame ↔ bytes)
- [ ] CRC validation test suite
- [ ] Parser fuzzing (random bytes, truncated frames)
- [ ] Loopback test (Pi TX → RX)
- [ ] End-to-end test (Pi ↔ dsPIC)
- [ ] Timeout behavior validation
- [ ] Fault injection tests

---

## Appendices

### A. Test Vectors

#### DriveCmd Example

**Input**:
- left_speed = 0.5
- right_speed = -0.25
- flags = ENABLE_REQUEST (0x0002)

**Frame Construction**:
```
SOF:      AA 55
Version:  01
MsgType:  01
Seq:      00
Len:      06
Payload:
  left_q15:  16383 = 0x3FFF → FF 3F (LE)
  right_q15: -8192 = 0xE000 → 00 E0 (LE)
  flags:     0x0002 → 02 00 (LE)
  Payload bytes: FF 3F 00 E0 02 00
CRC16: (computed over bytes 2-7: 01 01 00 06 FF 3F 00 E0 02 00)
  = 0xABCD (example) → CD AB (LE)

Complete Frame (hex):
AA 55 01 01 00 06 FF 3F 00 E0 02 00 CD AB
```

### B. Bandwidth Analysis

**Command Rate**: 50 Hz
- Frame overhead: 8 bytes (SOF, header, CRC)
- DriveCmd payload: 6 bytes
- Total per command: 14 bytes
- Command bandwidth: 50 Hz × 14 bytes = 700 bytes/sec = 5600 bps

**Telemetry Rate**: 20 Hz
- Frame overhead: 8 bytes
- Telemetry payload: 10 bytes
- Total per telemetry: 18 bytes
- Telemetry bandwidth: 20 Hz × 18 bytes = 360 bytes/sec = 2880 bps

**Total Bidirectional**: ~8500 bps (well within 115200 baud capacity)

### C. Fault Scenarios

| Scenario | dsPIC Behavior | Pi Detection |
|----------|----------------|--------------|
| Pi crashes | Watchdog timeout (200ms) → motors stop | - |
| dsPIC crashes | No telemetry | `age_ms` in last telemetry grows, then no frames |
| UART RX noise | CRC failures, frame discards | Diagnostic counter |
| UART TX failure | Commands sent but not received | dsPIC stops via watchdog |
| Brownout (Pi) | Pi reboot, dsPIC watchdog stops motors | System restart |
| Brownout (dsPIC) | dsPIC reboot/reset, outputs disabled | Telemetry stops |

### D. Future Extensions

Potential additions for future protocol versions:

- **Message Acknowledgment**: For critical config changes
- **Compression**: For high-rate encoder data
- **Multi-drop**: Address byte for multiple devices
- **Encryption**: Lightweight auth for outdoor/adversarial use
- **Variable PWM Frequency**: Runtime configuration
- **IMU Data**: Accelerometer, gyro integration
- **GPIO Control**: Read/write auxiliary I/O pins

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-29 | Rover Team | Initial specification |


