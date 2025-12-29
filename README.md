# Autonomous Rover Project

## Overview

A complete software stack for a custom-built autonomous skid-steer rover based on Raspberry Pi 4 and dsPIC33CK64MC105 microcontroller.

**Current Status**: Phase 1 Implementation Complete ✅

### Key Features

- 🎮 **Web-based teleoperation** with low-latency WebRTC video
- 🛡️ **Safety-first design** with watchdog, emergency stop, and fault monitoring
- 🔧 **Robust UART protocol** with CRC validation and framing
- 📊 **Real-time telemetry** and health monitoring
- 🏗️ **Modular architecture** ready for autonomous navigation

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Web Browser                            │
│         Joystick Control + Video + Telemetry Display         │
└───────────────────────┬──────────────────────────────────────┘
                        │ WebSocket + WebRTC
┌───────────────────────▼──────────────────────────────────────┐
│                   Raspberry Pi 4                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  FastAPI Server + WebSocket + Video Streaming          │ │
│  │  ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐│ │
│  │  │ Teleop │ │ Hardware │ │  Video   │ │    Future    ││ │
│  │  │Service │ │ Gateway  │ │ Service  │ │   Services   ││ │
│  │  └────────┘ └──────────┘ └──────────┘ └──────────────┘│ │
│  └──────────────────┬──────────────────────────────────────┘ │
└─────────────────────┼────────────────────────────────────────┘
                      │ UART (115200 baud, binary protocol)
┌─────────────────────▼────────────────────────────────────────┐
│               dsPIC33CK64MC105 Microcontroller                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Real-Time Motor Control (1 kHz)                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │ │
│  │  │ Protocol │ │ Watchdog │ │  Ramping │ │   PWM     │ │ │
│  │  │  Parser  │ │ (200ms)  │ │  Control │ │  Output   │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────┘
                        │ PWM + Direction
┌───────────────────────▼──────────────────────────────────────┐
│            L298N Motor Driver (4x DC Motors)                  │
└───────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
Rover/
├── dsPIC33CK64MC105/          # Microcontroller firmware
│   └── firmware/
│       ├── src/               # C source files
│       ├── include/           # Header files
│       ├── Makefile           # Build system
│       └── README.md          # Firmware documentation
│
├── Raspberry Pi/              # Pi software stack
│   └── pi/
│       ├── apps/              # Service applications
│       │   ├── api_server/    # FastAPI + WebSocket
│       │   ├── hardware_gateway/
│       │   ├── teleop/
│       │   └── video_service/
│       ├── lib/               # Shared libraries
│       │   ├── bus/           # Message bus
│       │   ├── protocol/      # UART protocol
│       │   ├── models/        # Data models
│       │   └── util/          # Utilities
│       ├── ui/                # Web interface
│       ├── config/            # Configuration files
│       ├── scripts/           # Bringup scripts
│       ├── requirements.txt   # Python dependencies
│       └── README.md          # Pi software documentation
│
└── docs/                      # Documentation
    ├── protocols/             # Communication protocols
    ├── safety/                # Safety analysis
    ├── architecture/          # Design documents
    └── bringup/               # Setup guides
```

---

## Quick Start

### Hardware Requirements

- Raspberry Pi 4 (2GB+ RAM recommended)
- dsPIC33CK64MC105 nano board (Microchip)
- L298N dual H-bridge motor driver (or equivalent)
- 4× DC gear motors (12V, with mounting)
- 3S LiPo battery (11.1V nominal)
- Pi Camera Module
- UART connection (Pi GPIO14/15 ↔ dsPIC UART)

### Software Setup

#### 1. dsPIC Firmware

```bash
cd dsPIC33CK64MC105/firmware

# Edit config.h to match your hardware pin assignments
# Build (requires Microchip XC16 compiler)
make

# Program device (requires PICkit or ICD programmer)
make program
```

See [`dsPIC33CK64MC105/firmware/README.md`](dsPIC33CK64MC105/firmware/README.md)

#### 2. Raspberry Pi Software

```bash
cd "Raspberry Pi/pi"

# Install dependencies
sudo apt update
sudo apt install python3-venv python3-picamera2

# Enable UART in raspi-config
sudo raspi-config
# Interface Options → Serial Port
#   Login shell: NO
#   Serial hardware: YES

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Edit configuration
nano config/rover_config.yaml
# Set UART port, voltage thresholds, max speed

# Run bringup script
./scripts/rover_bringup.sh
```

See [`Raspberry Pi/pi/README.md`](Raspberry%20Pi/pi/README.md)

#### 3. Access Web UI

Open browser to: `http://[Pi IP address]:8000`

- Control with joystick or WASD keys
- View live camera feed
- Monitor telemetry (voltage, motor PWM, faults)
- Emergency stop button always available

---

## Phase 1 Features ✅

- [x] Binary UART protocol with CRC validation
- [x] dsPIC firmware: PWM, ramping, watchdog, telemetry
- [x] Pi software: FastAPI, WebSocket, message bus
- [x] Web UI with joystick control
- [x] WebRTC video streaming
- [x] Safety features:
  - Watchdog timeout (200ms)
  - Emergency stop
  - Voltage monitoring
  - Fault reporting
- [x] Comprehensive documentation and checklists

---

## Roadmap

### Phase 2: Closed-Loop Control (Next)

- [ ] Motor encoders (quadrature)
- [ ] PID speed control on dsPIC
- [ ] Wheel odometry
- [ ] State estimator (pose tracking)

See [`docs/architecture/phase2_planning.md`](docs/architecture/phase2_planning.md)

### Phase 3: Perception

- [ ] Object detection (YOLO-nano or TFLite)
- [ ] Fiducial markers (AprilTag/ArUco)
- [ ] Room localization
- [ ] Visual debugging overlay

### Phase 4: Autonomy

- [ ] State machine for missions
- [ ] Exploration behaviors
- [ ] Target finding ("find the cat")
- [ ] Path planning

### Phase 5: Docking & Charging

- [ ] Visual dock detection
- [ ] Alignment controller
- [ ] Charge state machine
- [ ] Self-charging via spring contacts

---

## Documentation

### Essential Reading

- **[Protocol Specification](docs/protocols/uart_protocol_v1.md)**: UART binary protocol details
- **[Safety Analysis](docs/safety/fault_modes.md)**: Fault modes and mitigation strategies
- **[Phase 1 Demo Checklist](docs/bringup/phase1_demo_checklist.md)**: Validation and testing procedures
- **[Phase 2 Planning](docs/architecture/phase2_planning.md)**: Encoder integration plan

### Quick Links

- [dsPIC Firmware README](dsPIC33CK64MC105/firmware/README.md)
- [Pi Software README](Raspberry%20Pi/pi/README.md)
- [Configuration Guide](Raspberry%20Pi/pi/config/rover_config.yaml)

---

## Safety

⚠️ **Always test with wheels off the ground first!**

Built-in safety features:
- **Watchdog**: dsPIC stops motors if no commands received for 200ms
- **E-Stop**: UI emergency stop button
- **Fault Detection**: Voltage monitoring, driver faults
- **Acceleration Limiting**: Smooth ramping prevents current spikes
- **Safe Boot**: Motors disabled until explicitly enabled

See [`docs/safety/fault_modes.md`](docs/safety/fault_modes.md) for complete analysis.

---

## Development

### Adding a New Pi Service

1. Create directory in `apps/`
2. Implement service with `start()` and `stop()` async methods
3. Use message bus for communication
4. Register in `api_server.py`

### Extending the Protocol

1. Add message type in `docs/protocols/uart_protocol_v1.md`
2. Update `protocol.h` (dsPIC) and `lib/protocol/uart_protocol.py` (Pi)
3. Implement encoder/decoder
4. Update parser dispatch

### Running Tests

```bash
# Pi tests
cd "Raspberry Pi/pi"
pytest tests/

# Protocol tests
pytest tests/test_protocol.py -v

# Hardware-in-loop validation
# Follow: docs/bringup/phase1_demo_checklist.md
```

---

## Troubleshooting

### No UART Communication

- Check UART enabled in `raspi-config`
- Verify wiring (TX↔RX, common ground)
- Test with loopback (connect TX to RX)
- Check permissions: `sudo usermod -a -G dialout $USER`

### Motors Don't Respond

- Verify motor driver connections
- Check PWM pin assignments in `config.h`
- Measure PWM output with oscilloscope
- Ensure drive enable flag set in commands

### Video Not Streaming

- Test camera: `libcamera-hello`
- Check Picamera2 installed: `sudo apt install python3-picamera2`
- Review video service logs
- Try from same network first (no TURN server needed)

See troubleshooting guides in each README.

---

## Contributing

This is a personal learning project, but suggestions and improvements are welcome!

**Areas for contribution**:
- Hardware recommendations (motor drivers, encoders)
- Performance optimizations
- Additional safety features
- Documentation improvements

---

## License

MIT License (or specify your license)

---

## Acknowledgments

- **Design principles** inspired by ROS2 and NASA JPL robotics work
- **Safety philosophy** based on ISO 13849 and IEC 61508
- **Protocol design** influenced by MAVLink and similar embedded protocols

---

## Contact

[Your contact information or GitHub profile]

---

**Built with ❤️ for autonomous robotics**

🤖 Happy Rovering!

