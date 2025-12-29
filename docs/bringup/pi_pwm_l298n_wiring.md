# Pi PWM + L298N Wiring Guide

## Overview
This guide covers wiring the Raspberry Pi directly to the L298N motor driver for quick bringup. This bypasses the dsPIC and allows you to drive the rover today using Pi GPIO PWM.

## Hardware Requirements
- Raspberry Pi 4 (or 3B+)
- L298N motor driver module
- 2x DC gear motors
- Battery pack (9-12V recommended)
- Jumper wires (male-to-female for Pi GPIO)

## L298N Overview
The L298N is an H-bridge motor driver that can control 2 DC motors independently.

### L298N Pinout
**Power:**
- `12V`: Motor power input (connect to battery +)
- `GND`: Ground (common ground with Pi and battery)
- `5V`: 5V output (can power Pi if jumper is installed, but not recommended for motor loads)

**Motor A (Left):**
- `OUT1`, `OUT2`: Left motor terminals
- `ENA`: Enable/PWM for left motor (speed control)
- `IN1`, `IN2`: Direction control for left motor

**Motor B (Right):**
- `OUT3`, `OUT4`: Right motor terminals
- `ENB`: Enable/PWM for right motor (speed control)
- `IN3`, `IN4`: Direction control for right motor

### L298N Logic
- **Forward**: `IN1=HIGH`, `IN2=LOW`, `ENA=PWM`
- **Reverse**: `IN1=LOW`, `IN2=HIGH`, `ENA=PWM`
- **Stop/Brake**: `IN1=LOW`, `IN2=LOW`, `ENA=0%`

## Wiring Diagram

### Raspberry Pi → L298N Connections

| Pi GPIO (BCM) | L298N Pin | Function |
|---------------|-----------|----------|
| GPIO 17       | IN1       | Left motor direction 1 |
| GPIO 27       | IN2       | Left motor direction 2 |
| GPIO 18       | ENA       | Left motor PWM (speed) |
| GPIO 23       | IN3       | Right motor direction 1 |
| GPIO 24       | IN4       | Right motor direction 2 |
| GPIO 13       | ENB       | Right motor PWM (speed) |
| GND           | GND       | Common ground |

**Note:** GPIO 14/15 (UART) are reserved for future dsPIC use.

### Power Connections
1. **Battery → L298N:**
   - Battery `+` → L298N `12V`
   - Battery `-` → L298N `GND`

2. **L298N → Motors:**
   - `OUT1`, `OUT2` → Left motor
   - `OUT3`, `OUT4` → Right motor

3. **Common Ground:**
   - Connect Pi `GND` to L298N `GND` (critical for signal integrity)

### Important Notes
- **Common ground is essential**: Pi and L298N must share a common ground
- **Do NOT connect battery + to Pi**: The Pi should be powered separately via USB-C
- **L298N 5V jumper**: Remove the 5V regulator jumper if you're powering the Pi separately
- **Motor polarity**: If a motor spins backward, swap its two wires

## Physical Pin Reference

Raspberry Pi 4 GPIO header (looking at board from above, USB ports at bottom):

```
3.3V    [ 1] [ 2]  5V
GPIO 2  [ 3] [ 4]  5V
GPIO 3  [ 5] [ 6]  GND  ← Connect to L298N GND
GPIO 4  [ 7] [ 8]  GPIO 14 (UART TX) - Reserved
GND     [ 9] [10]  GPIO 15 (UART RX) - Reserved
GPIO 17 [11] [12]  GPIO 18  ← ENA (Left PWM)
GPIO 27 [13] [14]  GND
GPIO 22 [15] [16]  GPIO 23  ← IN3 (Right dir 1)
3.3V    [17] [18]  GPIO 24  ← IN4 (Right dir 2)
GPIO 10 [19] [20]  GND
GPIO 9  [21] [22]  GPIO 25
GPIO 11 [23] [24]  GPIO 8
GND     [25] [26]  GPIO 7
...
GPIO 13 [33] [34]  GND      ← ENB (Right PWM)
...
```

Key pins for L298N:
- **Pin 11 (GPIO 17)** → IN1
- **Pin 13 (GPIO 27)** → IN2
- **Pin 12 (GPIO 18)** → ENA
- **Pin 16 (GPIO 23)** → IN3
- **Pin 18 (GPIO 24)** → IN4
- **Pin 33 (GPIO 13)** → ENB
- **Pin 6 or 9 (GND)** → L298N GND

## Configuration

The pin mapping is defined in `Raspberry Pi/pi/config/rover_config.yaml`:

```yaml
control:
  backend: "pi_pwm"  # Use Pi GPIO PWM backend
  
  pi_pwm:
    left_in1: 17
    left_in2: 27
    left_ena: 18
    right_in3: 23
    right_in4: 24
    right_enb: 13
    pwm_frequency: 1000  # 1 kHz PWM
    max_command_age_ms: 250
    deadband: 0.05
```

## Bringup Checklist

### 1. Physical Wiring
- [ ] Battery connected to L298N `12V` and `GND`
- [ ] L298N `OUT1/OUT2` connected to left motor
- [ ] L298N `OUT3/OUT4` connected to right motor
- [ ] Pi GPIO pins connected to L298N per table above
- [ ] **Common ground: Pi GND → L298N GND**
- [ ] Pi powered separately via USB-C (not from L298N 5V)
- [ ] Motors NOT on ground yet (wheels lifted for safety)

### 2. Software Setup
- [ ] `rover_config.yaml`: `control.backend: "pi_pwm"`
- [ ] Code deployed on Pi: `git pull`
- [ ] Virtual environment active: `source venv/bin/activate`
- [ ] Dependencies installed: `pip install -r requirements.txt`

### 3. First Power-On (Motors Disabled)
```bash
cd ~/rover/Rover/"Raspberry Pi"/pi
source venv/bin/activate
./scripts/rover_bringup.sh
```

**Expected logs:**
```
INFO - Initializing motor controller backend: pi_pwm
INFO - Pi PWM motor controller started: L=(IN1:17, IN2:27, ENA:18), R=(IN3:23, IN4:24, ENB:13) @ 1000Hz
INFO - All services started successfully
```

### 4. Initial Test (Motors Off Ground)
- [ ] Open UI: `http://<pi-ip>:8000`
- [ ] Video stream loads
- [ ] Press **W** (forward throttle)
- [ ] Observe: left motor spins forward, right motor spins forward
- [ ] Press **S** (reverse)
- [ ] Observe: both motors reverse
- [ ] Press **A** / **D** (turn)
- [ ] Observe: differential drive (one motor faster/slower)
- [ ] Close UI tab
- [ ] Observe: motors stop within ~250ms (stale command safety)

### 5. Direction Check
If a motor spins the wrong way:
- **Option 1 (hardware)**: Swap the motor's two wires
- **Option 2 (software)**: Swap `INx` pins in config (e.g., swap `left_in1` and `left_in2`)

### 6. Ground Test
Once directions are correct:
- [ ] Place rover on ground (clear area)
- [ ] Re-run bringup
- [ ] Test forward/reverse/turn at low speeds
- [ ] Confirm emergency stop works (close tab or press E-STOP button)

## Safety Features

The Pi PWM backend includes:
1. **Motors disabled on startup**: No motion until first valid command
2. **Stale command detection**: Stops motors if no fresh command within 250ms
3. **WebSocket disconnect stop**: Stops motors when UI tab closes
4. **Ctrl+C cleanup**: GPIO cleanup and STOP on process exit
5. **Input deadband**: Filters out noise/drift (5% by default)

## Troubleshooting

### Motors don't spin
- Check battery voltage (should be 9-12V)
- Verify L298N power LED is on
- Check common ground (Pi GND ↔ L298N GND)
- Check jumper wires are firmly connected
- Run `gpio readall` to verify pin states

### Motors spin weakly
- Low battery voltage
- L298N heat sink getting hot (needs cooling or lower PWM frequency)
- PWM frequency too high (try 500 Hz instead of 1000 Hz)

### Motors spin opposite directions
- Swap motor wires or swap `INx` pins in config

### GPIO permission errors
```bash
sudo usermod -a -G gpio rover
# Log out and back in
```

### "RPi.GPIO not available" warning
- **On Pi**: `sudo apt install python3-rpi.gpio`
- **If using venv**: Ensure venv has `--system-site-packages` or install via pip

## Next Steps

Once the Pi PWM backend is working:
1. **Tune parameters**: Adjust deadband, max speed, slew rate in `rover_config.yaml`
2. **Add encoders** (Phase 2): Closed-loop speed control
3. **Re-enable dsPIC**: See [docs/architecture/control_backends.md](../architecture/control_backends.md)

## See Also
- [Control Backends Documentation](../architecture/control_backends.md) - How to switch back to UART/dsPIC
- [Phase 1 Demo Checklist](phase1_demo_checklist.md) - Full test procedures

