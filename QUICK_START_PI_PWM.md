# Quick Start: Pi PWM Motor Control

## What Changed?

Your rover now has **two motor control backends**:
1. **Pi PWM** (NEW): Direct GPIO control of L298N - **USE THIS FOR WEEKEND BRINGUP**
2. **UART** (existing): dsPIC via UART - **Use this later when firmware is ready**

All dsPIC/UART code is preserved and unchanged. You can switch between them with one config line.

## Weekend Bringup Steps

### 1. Wire the L298N (15 minutes)

See detailed guide: `docs/bringup/pi_pwm_l298n_wiring.md`

**Quick reference:**
```
Pi GPIO 17 → L298N IN1    (Left direction 1)
Pi GPIO 27 → L298N IN2    (Left direction 2)
Pi GPIO 18 → L298N ENA    (Left PWM speed)
Pi GPIO 23 → L298N IN3    (Right direction 1)
Pi GPIO 24 → L298N IN4    (Right direction 2)
Pi GPIO 13 → L298N ENB    (Right PWM speed)
Pi GND     → L298N GND    (CRITICAL: Common ground!)

Battery+ → L298N 12V
Battery- → L298N GND
L298N OUT1/OUT2 → Left motor
L298N OUT3/OUT4 → Right motor
```

### 2. Deploy Code to Pi

```bash
# On your dev machine
git add .
git commit -m "Add Pi PWM motor backend"
git push

# On the Pi
cd ~/rover/Rover
git pull
```

### 3. Verify Configuration

```bash
cd "Raspberry Pi"/pi
cat config/rover_config.yaml | grep "backend:"
```

Should show: `backend: "pi_pwm"`

(If not, the default is already set correctly in the updated config)

### 4. Start the Rover

```bash
cd ~/rover/Rover/"Raspberry Pi"/pi
source venv/bin/activate
./scripts/rover_bringup.sh
```

**Expected log output:**
```
INFO - Initializing motor controller backend: pi_pwm
INFO - Pi PWM motor controller started: L=(IN1:17, IN2:27, ENA:18), R=(IN3:23, IN4:24, ENB:13) @ 1000Hz
INFO - All services started successfully
```

### 5. Test (Motors Off Ground First!)

1. Open browser: `http://192.168.0.21:8000`
2. Video should load
3. Press **W** → both motors spin forward
4. Press **S** → both motors reverse
5. Press **A/D** → differential drive (turning)
6. Close browser tab → motors stop immediately

### 6. Fix Motor Directions (if needed)

If a motor spins backward:
- **Quick fix**: Swap the motor's two wires
- **Config fix**: Swap `INx` pins in `rover_config.yaml`

### 7. Ground Test

Once directions are correct, place rover on ground and drive!

## Switching Back to UART (When dsPIC is Ready)

```bash
# Edit config
nano config/rover_config.yaml

# Change this line:
#   backend: "pi_pwm"
# To:
#   backend: "uart"

# Restart
./scripts/rover_bringup.sh
```

That's it! One config line switches backends.

## Documentation

- **Wiring guide**: `docs/bringup/pi_pwm_l298n_wiring.md`
- **Architecture**: `docs/architecture/control_backends.md`
- **Implementation summary**: `docs/bringup/PI_PWM_IMPLEMENTATION_SUMMARY.md`

## Troubleshooting

### "ImportError: No module named 'RPi.GPIO'"
```bash
sudo apt install python3-rpi.gpio
```

### Motors don't spin
- Check battery voltage (should be 9-12V)
- Verify common ground: Pi GND connected to L298N GND
- Check all jumper wires are firmly connected

### "Unknown motor controller backend" error
- Check `rover_config.yaml` → `control.backend` is `"pi_pwm"` (with quotes)

## What's Preserved?

- ✅ All dsPIC firmware code (unchanged)
- ✅ All UART protocol code (unchanged)
- ✅ UI (unchanged)
- ✅ Teleop service (unchanged)
- ✅ Video streaming (unchanged)

You can switch back to UART anytime by changing one config line.

## Need Help?

Check the detailed docs:
```bash
cd docs/bringup
ls -l
```

Happy driving! 🚗💨

