"""
Pi GPIO PWM Motor Controller
Direct L298N control via Raspberry Pi GPIO

Safety features:
- Motors disabled on startup
- STOP on stale command
- GPIO cleanup on exit
- Configurable deadband
"""

import asyncio
import logging
import time
from typing import Optional
from datetime import datetime

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available - Pi PWM motor controller will run in simulation mode")

from lib.motor.motor_controller import MotorController, MotorStatus
from lib.models.messages import DriveCommand, Telemetry, LinkStatus
from lib.bus.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class PiPwmMotorController(MotorController):
    """
    L298N motor controller via Raspberry Pi GPIO PWM.
    
    L298N connections:
    - IN1, IN2: Left motor direction
    - ENA: Left motor PWM (enable/speed)
    - IN3, IN4: Right motor direction
    - ENB: Right motor PWM (enable/speed)
    
    Logic:
    - Forward: IN1=HIGH, IN2=LOW, ENA=PWM
    - Reverse: IN1=LOW, IN2=HIGH, ENA=PWM
    - Stop/Brake: IN1=LOW, IN2=LOW, ENA=0
    """
    
    def __init__(
        self,
        left_in1: int,
        left_in2: int,
        left_ena: int,
        right_in3: int,
        right_in4: int,
        right_enb: int,
        pwm_frequency: int = 1000,
        max_command_age_s: float = 0.25,
        deadband: float = 0.05,
    ):
        """
        Args:
            left_in1, left_in2: Left motor direction pins (BCM numbering)
            left_ena: Left motor PWM enable pin
            right_in3, right_in4: Right motor direction pins
            right_enb: Right motor PWM enable pin
            pwm_frequency: PWM frequency in Hz
            max_command_age_s: Max age for command before forcing STOP
            deadband: Input deadband (0-1)
        """
        self.left_in1 = left_in1
        self.left_in2 = left_in2
        self.left_ena = left_ena
        self.right_in3 = right_in3
        self.right_in4 = right_in4
        self.right_enb = right_enb
        
        self.pwm_frequency = pwm_frequency
        self.max_command_age_s = max_command_age_s
        self.deadband = deadband
        
        # State
        self.running = False
        self.enabled = False
        self.current_command: Optional[DriveCommand] = None
        self.last_command_time: Optional[datetime] = None
        self._last_stale_warn_time = 0.0
        self._stale_warn_interval = 2.0
        
        # GPIO objects
        self.left_pwm = None
        self.right_pwm = None
        
        # Message bus
        self.bus = get_message_bus()
        
        # Tasks
        self._tasks = []
    
    async def start(self):
        """Start the motor controller"""
        if not GPIO_AVAILABLE:
            logger.warning("GPIO not available - running in simulation mode")
            self.running = True
            return
        
        try:
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Configure direction pins as outputs
            GPIO.setup(self.left_in1, GPIO.OUT)
            GPIO.setup(self.left_in2, GPIO.OUT)
            GPIO.setup(self.right_in3, GPIO.OUT)
            GPIO.setup(self.right_in4, GPIO.OUT)
            
            # Configure PWM pins
            GPIO.setup(self.left_ena, GPIO.OUT)
            GPIO.setup(self.right_enb, GPIO.OUT)
            
            # Initialize to STOP
            GPIO.output(self.left_in1, GPIO.LOW)
            GPIO.output(self.left_in2, GPIO.LOW)
            GPIO.output(self.right_in3, GPIO.LOW)
            GPIO.output(self.right_in4, GPIO.LOW)
            
            # Setup PWM
            self.left_pwm = GPIO.PWM(self.left_ena, self.pwm_frequency)
            self.right_pwm = GPIO.PWM(self.right_enb, self.pwm_frequency)
            
            self.left_pwm.start(0)  # Start at 0% duty
            self.right_pwm.start(0)
            
            logger.info(
                f"Pi PWM motor controller started: "
                f"L=(IN1:{self.left_in1}, IN2:{self.left_in2}, ENA:{self.left_ena}), "
                f"R=(IN3:{self.right_in3}, IN4:{self.right_in4}, ENB:{self.right_enb}) @ {self.pwm_frequency}Hz"
            )
            
            self.running = True
            
            # Start command listener task
            task = asyncio.create_task(self._command_listener_task())
            self._tasks.append(task)
            
        except Exception as e:
            logger.error(f"Failed to start Pi PWM motor controller: {e}")
            self._cleanup_gpio()
            raise
    
    async def stop(self):
        """Stop the motor controller"""
        self.running = False
        
        # Stop all motors immediately
        self._apply_stop()
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        # Cleanup GPIO
        self._cleanup_gpio()
        
        logger.info("Pi PWM motor controller stopped")
    
    def _cleanup_gpio(self):
        """Cleanup GPIO resources"""
        if not GPIO_AVAILABLE:
            return
        
        try:
            if self.left_pwm:
                self.left_pwm.stop()
            if self.right_pwm:
                self.right_pwm.stop()
            
            GPIO.cleanup([
                self.left_in1, self.left_in2, self.left_ena,
                self.right_in3, self.right_in4, self.right_enb
            ])
            
            logger.info("GPIO cleanup complete")
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")
    
    async def send_drive_command(self, cmd: DriveCommand):
        """Send drive command (called by teleop service via bus)"""
        self.current_command = cmd
        self.last_command_time = datetime.now()
    
    async def _command_listener_task(self):
        """Listen for drive commands on message bus"""
        queue = await self.bus.subscribe("drive_command")
        
        while self.running:
            try:
                cmd: DriveCommand = await asyncio.wait_for(queue.get(), timeout=0.1)
                await self.send_drive_command(cmd)
                
                # Apply command
                self._apply_command(cmd)
                
            except asyncio.TimeoutError:
                # Check for stale command
                if self.current_command:
                    age = (datetime.now() - self.last_command_time).total_seconds()
                    if age > self.max_command_age_s:
                        now = time.monotonic()
                        if (now - self._last_stale_warn_time) >= self._stale_warn_interval:
                            logger.warning(
                                f"Stale command (age={age:.3f}s > {self.max_command_age_s:.3f}s), stopping motors"
                            )
                            self._last_stale_warn_time = now
                        
                        self._apply_stop()
                
            except Exception as e:
                logger.error(f"Error in command listener: {e}")
                await asyncio.sleep(0.1)
    
    def _apply_command(self, cmd: DriveCommand):
        """Apply drive command to motors"""
        if not GPIO_AVAILABLE:
            # Simulation mode - just log
            logger.debug(f"[SIM] Drive: L={cmd.left_speed:.2f}, R={cmd.right_speed:.2f}, estop={cmd.estop}")
            return
        
        # Check for emergency stop
        if cmd.estop or not cmd.enable_request:
            self._apply_stop()
            self.enabled = False
            return
        
        self.enabled = True
        
        # Apply deadband
        left_speed = cmd.left_speed if abs(cmd.left_speed) > self.deadband else 0.0
        right_speed = cmd.right_speed if abs(cmd.right_speed) > self.deadband else 0.0
        
        # Apply to left motor
        self._set_motor(
            in1_pin=self.left_in1,
            in2_pin=self.left_in2,
            pwm=self.left_pwm,
            speed=left_speed
        )
        
        # Apply to right motor
        self._set_motor(
            in1_pin=self.right_in3,
            in2_pin=self.right_in4,
            pwm=self.right_pwm,
            speed=right_speed
        )
    
    def _set_motor(self, in1_pin: int, in2_pin: int, pwm, speed: float):
        """
        Set motor direction and speed.
        
        Args:
            in1_pin, in2_pin: Direction control pins
            pwm: PWM object
            speed: -1.0 (full reverse) to +1.0 (full forward)
        """
        if speed > 0:
            # Forward
            GPIO.output(in1_pin, GPIO.HIGH)
            GPIO.output(in2_pin, GPIO.LOW)
            duty = min(abs(speed) * 100.0, 100.0)
            pwm.ChangeDutyCycle(duty)
        
        elif speed < 0:
            # Reverse
            GPIO.output(in1_pin, GPIO.LOW)
            GPIO.output(in2_pin, GPIO.HIGH)
            duty = min(abs(speed) * 100.0, 100.0)
            pwm.ChangeDutyCycle(duty)
        
        else:
            # Stop
            GPIO.output(in1_pin, GPIO.LOW)
            GPIO.output(in2_pin, GPIO.LOW)
            pwm.ChangeDutyCycle(0)
    
    def _apply_stop(self):
        """Stop all motors immediately"""
        if not GPIO_AVAILABLE:
            return
        
        try:
            # Set all direction pins LOW
            GPIO.output(self.left_in1, GPIO.LOW)
            GPIO.output(self.left_in2, GPIO.LOW)
            GPIO.output(self.right_in3, GPIO.LOW)
            GPIO.output(self.right_in4, GPIO.LOW)
            
            # Set PWM to 0%
            if self.left_pwm:
                self.left_pwm.ChangeDutyCycle(0)
            if self.right_pwm:
                self.right_pwm.ChangeDutyCycle(0)
            
            self.enabled = False
        
        except Exception as e:
            logger.error(f"Error stopping motors: {e}")
    
    def get_status(self) -> MotorStatus:
        """Get current status"""
        return MotorStatus(
            enabled=self.enabled,
            last_command_time=self.last_command_time,
            has_fault=False,
            backend_name="pi_pwm"
        )
    
    def get_telemetry(self) -> Optional[Telemetry]:
        """
        Pi PWM backend doesn't provide telemetry.
        Returns None.
        """
        return None
    
    def get_link_status(self) -> Optional[LinkStatus]:
        """
        Pi PWM backend doesn't track link status.
        Returns None.
        """
        return None

