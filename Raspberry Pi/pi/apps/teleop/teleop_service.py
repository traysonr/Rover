"""
Teleoperation Service
Converts user input to drive commands
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from lib.models.messages import TeleopInput, DriveCommand
from lib.bus.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class TeleopService:
    """
    Teleoperation service.
    - Receives TeleopInput from UI
    - Applies deadband, scaling, slewing
    - Outputs DriveCommand to message bus
    """
    
    def __init__(self, max_speed: float = 1.0, deadband: float = 0.05,
                 slew_rate_per_sec: float = 2.0):
        self.max_speed = max_speed
        self.deadband = deadband
        self.slew_rate_per_sec = slew_rate_per_sec
        
        # State
        self.current_left = 0.0
        self.current_right = 0.0
        self.last_update_time = datetime.now()
        
        # Message bus
        self.bus = get_message_bus()
        
        # Control
        self.running = False
        self._tasks = []
    
    def apply_deadband(self, value: float) -> float:
        """Apply deadband to input"""
        if abs(value) < self.deadband:
            return 0.0
        # Scale remaining range
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - self.deadband) / (1.0 - self.deadband)
    
    def differential_drive(self, throttle: float, turn: float) -> tuple:
        """
        Convert throttle + turn to left/right wheel speeds.
        
        Args:
            throttle: Forward/backward (-1 to +1)
            turn: Left/right (-1 to +1)
        
        Returns:
            (left_speed, right_speed) tuple
        """
        # Simple differential steering
        left = throttle + turn
        right = throttle - turn
        
        # Normalize if exceeds range
        max_val = max(abs(left), abs(right))
        if max_val > 1.0:
            left /= max_val
            right /= max_val
        
        return left, right
    
    def apply_slew(self, target: float, current: float, dt: float) -> float:
        """Apply slew rate limit"""
        max_change = self.slew_rate_per_sec * dt
        error = target - current
        
        if abs(error) <= max_change:
            return target
        
        return current + (max_change if error > 0 else -max_change)
    
    def process_input(self, input_cmd: TeleopInput) -> DriveCommand:
        """Process teleop input and generate drive command"""
        # Calculate delta time
        now = datetime.now()
        dt = (now - self.last_update_time).total_seconds()
        self.last_update_time = now
        
        # Apply deadband
        throttle = self.apply_deadband(input_cmd.throttle)
        turn = self.apply_deadband(input_cmd.turn)
        
        # Convert to differential drive
        target_left, target_right = self.differential_drive(throttle, turn)
        
        # Scale by max speed
        target_left *= self.max_speed
        target_right *= self.max_speed
        
        # Apply slew rate
        self.current_left = self.apply_slew(target_left, self.current_left, dt)
        self.current_right = self.apply_slew(target_right, self.current_right, dt)
        
        # Create drive command
        return DriveCommand(
            left_speed=self.current_left,
            right_speed=self.current_right,
            enable_request=input_cmd.enable,
            estop=input_cmd.estop,
            timestamp=now,
            source="teleop"
        )
    
    async def start(self):
        """Start teleop service"""
        self.running = True
        self._tasks = [
            asyncio.create_task(self._input_subscriber_task())
        ]
        logger.info("Teleop service started")
    
    async def stop(self):
        """Stop teleop service"""
        self.running = False
        
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info("Teleop service stopped")
    
    async def _input_subscriber_task(self):
        """Subscribe to teleop input and publish drive commands"""
        queue = await self.bus.subscribe("teleop_input")
        
        try:
            while self.running:
                try:
                    input_cmd: TeleopInput = await asyncio.wait_for(
                        queue.get(), timeout=1.0
                    )
                    
                    # Process input
                    drive_cmd = self.process_input(input_cmd)
                    
                    # Publish drive command
                    await self.bus.publish("drive_command", drive_cmd)
                    
                except asyncio.TimeoutError:
                    # No input - maintain current state or decay to zero
                    # For now, just continue
                    continue
        
        except asyncio.CancelledError:
            logger.debug("Input subscriber task cancelled")


# ============================================================================
# STANDALONE RUNNER
# ============================================================================

async def main():
    """Run teleop service standalone for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = TeleopService()
    
    try:
        await service.start()
        
        # Simulate some inputs
        bus = get_message_bus()
        
        for i in range(10):
            input_cmd = TeleopInput(
                throttle=0.5 if i % 2 == 0 else -0.5,
                turn=0.2,
                enable=True
            )
            await bus.publish("teleop_input", input_cmd)
            await asyncio.sleep(0.1)
        
        await asyncio.sleep(2)
        
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())

