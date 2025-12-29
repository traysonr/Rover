"""
UART Motor Controller
Wraps existing HardwareGateway to provide MotorController interface
"""

import logging
from typing import Optional
from datetime import datetime

from lib.motor.motor_controller import MotorController, MotorStatus
from lib.models.messages import DriveCommand, Telemetry, LinkStatus
from apps.hardware_gateway.hardware_gateway import HardwareGateway

logger = logging.getLogger(__name__)


class UartMotorController(MotorController):
    """
    Motor controller that wraps the existing HardwareGateway.
    
    This preserves the full dsPIC/UART protocol implementation:
    - Binary framed protocol
    - CRC checking
    - Telemetry reception
    - Link status tracking
    - Watchdog safety
    """
    
    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        command_rate_hz: int = 50,
        max_command_age_ms: int = 250
    ):
        """
        Args:
            port: UART port (e.g. /dev/serial0)
            baudrate: UART baud rate
            command_rate_hz: Command send rate
            max_command_age_ms: Max command age before forcing stop
        """
        self.hardware_gateway = HardwareGateway(
            port=port,
            baudrate=baudrate,
            command_rate_hz=command_rate_hz,
            max_command_age_ms=max_command_age_ms
        )
    
    async def start(self):
        """Start the UART motor controller (hardware gateway)"""
        try:
            self.hardware_gateway.open_serial()
            await self.hardware_gateway.start()
            logger.info("UART motor controller started")
        except Exception as e:
            logger.error(f"Failed to start UART motor controller: {e}")
            raise
    
    async def stop(self):
        """Stop the UART motor controller"""
        await self.hardware_gateway.stop()
        logger.info("UART motor controller stopped")
    
    async def send_drive_command(self, cmd: DriveCommand):
        """Send drive command via UART to dsPIC"""
        await self.hardware_gateway.send_drive_command(cmd)
    
    def get_status(self) -> MotorStatus:
        """Get current status"""
        link = self.hardware_gateway.link_status
        return MotorStatus(
            enabled=link.connected,
            last_command_time=datetime.now() if self.hardware_gateway.current_drive_cmd else None,
            has_fault=False,  # Fault info comes from telemetry
            backend_name="uart"
        )
    
    def get_telemetry(self) -> Optional[Telemetry]:
        """Get latest telemetry from dsPIC"""
        return self.hardware_gateway.last_telemetry
    
    def get_link_status(self) -> Optional[LinkStatus]:
        """Get UART link status"""
        return self.hardware_gateway.link_status

