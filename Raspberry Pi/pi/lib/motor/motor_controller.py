"""
Motor Controller Interface
Abstract base for motor control backends (UART/dsPIC or Pi GPIO PWM)
"""

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from lib.models.messages import DriveCommand, Telemetry, LinkStatus


class MotorStatus(BaseModel):
    """Generic motor controller status"""
    enabled: bool = False
    last_command_time: Optional[datetime] = None
    has_fault: bool = False
    backend_name: str = "unknown"


class MotorController(ABC):
    """
    Abstract motor controller interface.
    
    Implementations:
    - UartMotorController: dsPIC via UART (existing hardware_gateway)
    - PiGpioMotorController: Direct L298N control via Pi GPIO PWM
    """
    
    @abstractmethod
    async def start(self):
        """Start the motor controller"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the motor controller and cleanup resources"""
        pass
    
    @abstractmethod
    async def send_drive_command(self, cmd: DriveCommand):
        """
        Send a drive command to the motors.
        
        Args:
            cmd: Normalized drive command (-1.0 to +1.0 for each motor)
        """
        pass
    
    @abstractmethod
    def get_status(self) -> MotorStatus:
        """Get current motor controller status"""
        pass
    
    @abstractmethod
    def get_telemetry(self) -> Optional[Telemetry]:
        """
        Get latest telemetry (if available).
        Returns None if backend doesn't provide telemetry.
        """
        pass
    
    @abstractmethod
    def get_link_status(self) -> Optional[LinkStatus]:
        """
        Get link status (if available).
        Returns None if backend doesn't track link status.
        """
        pass

