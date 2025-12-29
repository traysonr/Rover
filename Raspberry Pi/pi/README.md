# Rover Raspberry Pi Software - Phase 1

## Overview

Complete software stack for the autonomous rover's Raspberry Pi 4, implementing:
- **FastAPI + WebSocket** control API
- **WebRTC** video streaming
- **Hardware gateway** for UART communication with dsPIC
- **Teleoperation service** with differential drive
- **Message bus** for inter-service communication
- **Web UI** for remote control

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Web Browser                            │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Joystick  │  │ Video Stream │  │   Telemetry      │   │
│  └──────┬─────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │               │                    │              │
└─────────┼───────────────┼────────────────────┼──────────────┘
          │ WebSocket     │ WebRTC             │
          ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi 4                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               API Server (FastAPI)                     │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐ │ │
│  │  │ WebSocket│  │   REST API   │  │  Static Files   │ │ │
│  │  └─────┬────┘  └──────────────┘  └─────────────────┘ │ │
│  └────────┼───────────────────────────────────────────────┘ │
│           │                                                  │
│  ┌────────▼──────────── Message Bus ──────────────────────┐ │
│  │   (In-Process Pub/Sub with asyncio queues)             │ │
│  └┬────────┬──────────┬────────────┬──────────────────────┘ │
│   │        │          │            │                         │
│  ┌▼──────┐┌▼────────┐┌▼──────────┐┌▼───────────────────────┐│
│  │Teleop ││Video    ││Hardware   ││    Future Services     ││
│  │Service││Service  ││Gateway    ││ (Perception, Missions) ││
│  └───────┘└─────────┘└─────┬─────┘└────────────────────────┘│
│                            │ UART                             │
└────────────────────────────┼──────────────────────────────────┘
                             │
                      ┌──────▼─────────┐
                      │ dsPIC33CK MCU  │
                      │  (Motor Ctrl)  │
                      └────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# System packages
sudo apt update
sudo apt install python3-venv python3-pip python3-picamera2 python3-serial

# Enable UART
sudo raspi-config
# Interface Options → Serial Port
#   - Login shell: NO
#   - Serial hardware: YES
# Reboot

# Create virtual environment
cd ~/Rover/Raspberry\ Pi/pi
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 2. Configure

Edit `config/rover_config.yaml`:
- Set correct UART port (`/dev/serial0` or `/dev/ttyAMA0`)
- Adjust max speed for initial testing (recommend 0.5)
- Set voltage thresholds for your battery

### 3. Run

```bash
./scripts/rover_bringup.sh
```

Access UI at: `http://[Pi IP]:8000`

## Directory Structure

```
pi/
├── apps/                      # Service applications
│   ├── api_server/            # FastAPI + WebSocket server
│   ├── hardware_gateway/      # UART communication with dsPIC
│   ├── teleop/                # Teleoperation input processing
│   ├── video_service/         # WebRTC video streaming
│   ├── perception/            # [Phase 3] Computer vision
│   ├── missions/              # [Phase 4] Autonomous behaviors
│   └── state_estimator/       # [Phase 2] Odometry
├── lib/                       # Shared libraries
│   ├── bus/                   # Message bus (pub/sub)
│   ├── protocol/              # UART protocol codec
│   ├── models/                # Pydantic data models
│   └── util/                  # Logging, config, helpers
├── ui/                        # Web UI (HTML/JS)
├── config/                    # Configuration files (YAML)
├── scripts/                   # Bringup and utility scripts
├── tests/                     # Unit and integration tests
├── docs/                      # Documentation
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Services

### API Server (`apps/api_server/api_server.py`)

Main entry point. Starts all services and provides:
- REST API at `/api/v1/*`
- WebSocket at `/ws`
- Static UI at `/`

**Endpoints**:
- `GET /api/v1/health` - System health status
- `POST /api/v1/teleop` - Send drive command
- `POST /api/v1/stop` - Emergency stop
- `WS /ws` - Real-time control + telemetry

### Hardware Gateway (`apps/hardware_gateway/hardware_gateway.py`)

Manages UART communication with dsPIC:
- Sends DriveCmd at 50 Hz
- Receives Telemetry at 20 Hz
- Enforces command freshness
- Mirrors watchdog timeout behavior

**Can run standalone for testing**:
```bash
python apps/hardware_gateway/hardware_gateway.py
```

### Teleop Service (`apps/teleop/teleop_service.py`)

Converts user input to motor commands:
- Differential drive mapping (throttle + turn → left/right)
- Deadband and scaling
- Software-side slewing

**Can run standalone**:
```bash
python apps/teleop/teleop_service.py
```

### Video Service (`apps/video_service/video_service.py`)

WebRTC video streaming:
- Captures from Pi Camera via Picamera2
- H.264 encoding with hardware acceleration
- WebRTC peer connection management
- Falls back to test pattern if no camera

## Configuration

### Main Config (`config/rover_config.yaml`)

All system parameters in one file:
- UART settings (port, baud, protocol version)
- Command rates and timeouts
- Video resolution and codec
- Safety thresholds
- Service-specific settings

### Protocol Version

Two modes available:
- **Binary (v1)**: Robust framed protocol with CRC (default)
- **ASCII (v0)**: Human-readable for debugging

Set in config: `uart.protocol_version: "v1_binary"` or `"v0_ascii"`

## Message Bus

Lightweight in-process pub/sub using `asyncio.Queue`:

**Topics** (Phase 1):
- `teleop_input` - User input from UI
- `drive_command` - Normalized motor commands
- `telemetry` - dsPIC status feedback

Services publish/subscribe to topics to stay decoupled.

**Example**:
```python
from lib.bus.message_bus import get_message_bus

bus = get_message_bus()

# Subscribe
queue = await bus.subscribe("telemetry")
telemetry = await queue.get()

# Publish
await bus.publish("drive_command", cmd)
```

## Web UI

Simple single-page application (`ui/index.html`):
- Joystick control (mouse drag)
- Keyboard control (WASD / Arrow keys)
- Emergency stop button
- Live video stream (WebRTC)
- Real-time telemetry display
- Connection status indicator

**No build step required** - pure HTML/JS/CSS.

## Logging

Structured logging with `structlog`:
- JSON format (machine-readable)
- Rotating file handler
- Configurable log level
- Logs to `/var/log/rover/` (or configured path)

**Usage**:
```python
from lib.util.logging_config import get_logger

logger = get_logger(__name__)
logger.info("drive_command_sent", left=0.5, right=0.3)
```

## Testing

### Unit Tests

```bash
pytest tests/
```

### Protocol Tests

Test frame encoding/decoding:
```bash
pytest tests/test_protocol.py -v
```

### Integration Test

Run all services and send test commands:
```bash
pytest tests/test_integration.py
```

### Hardware-in-Loop

1. Connect to real dsPIC
2. Run bringup
3. Follow Phase 1 demo checklist: `docs/bringup/phase1_demo_checklist.md`

## Troubleshooting

### UART Issues

**Error**: "Failed to open serial port"

**Fix**:
```bash
# Check UART enabled
sudo raspi-config

# Check permissions
sudo usermod -a -G dialout $USER
# (reboot after this)

# Test port
ls -l /dev/serial* /dev/ttyAMA*
```

### Camera Issues

**Error**: "Picamera2 not available"

**Fix**:
```bash
# Test camera
libcamera-hello

# Install Picamera2
sudo apt install python3-picamera2

# Check camera detected
vcgencmd get_camera
```

### WebRTC Issues

**Symptom**: Video not streaming

**Fix**:
- Check browser console for WebRTC errors
- Ensure STUN server reachable
- Try from same network first (no TURN needed)
- Check video service logs

### High CPU Usage

**Fix**:
- Reduce video framerate in config (15 fps)
- Lower resolution (480p)
- Disable unused services

## Performance

Expected performance on Pi 4:
- **Command latency**: < 50 ms (UI → motors)
- **Telemetry rate**: 20 Hz
- **Video latency**: 200-300 ms (WebRTC)
- **CPU usage**: 30-50% (all services)

## Phase 2 Extensions

Future additions (not yet implemented):
- **Encoders**: Read encoder ticks, publish EncoderData
- **PID Control**: Closed-loop speed control on dsPIC
- **State Estimator**: Wheel odometry, IMU fusion
- **Perception**: Object detection, marker recognition
- **Missions**: Autonomous behaviors, state machines

See `docs/architecture/phase2_planning.md` for details.

## Safety

All safety features active in Phase 1:
- **Watchdog**: dsPIC stops if no commands for 200 ms
- **E-Stop**: UI button forces immediate stop
- **Voltage Monitoring**: Fault on under/overvoltage
- **Ramping**: Smooth acceleration prevents current spikes
- **Fault Reporting**: All faults visible in UI telemetry

**Always test with wheels off ground first!**

## Development

### Adding a New Service

1. Create directory in `apps/`
2. Implement service class with `start()` and `stop()` methods
3. Subscribe/publish to message bus
4. Register in `api_server.py` startup

### Adding a New Message Type

1. Define Pydantic model in `lib/models/messages.py`
2. Add topic name to bus
3. Publishers and subscribers can now use it

### Adding a New API Endpoint

Edit `apps/api_server/api_server.py`:
```python
@app.post("/api/v1/my_endpoint")
async def my_endpoint(req: MyRequest):
    # Handle request
    return {"status": "ok"}
```

## License

MIT License (or your chosen license)

## Support

See full documentation:
- **Protocol Spec**: `docs/protocols/uart_protocol_v1.md`
- **Safety Analysis**: `docs/safety/fault_modes.md`
- **Phase 1 Checklist**: `docs/bringup/phase1_demo_checklist.md`
- **Architecture**: `docs/architecture/`

## Version History

- **v1.0.0** (2025-12-29): Phase 1 implementation
  - Basic teleoperation
  - WebRTC video
  - Safety features (watchdog, E-stop)
  - Web UI

---

**Happy Rovering! 🤖**

