"""
Hardware Gateway Service
Manages UART communication with dsPIC
"""

import asyncio
import serial
import logging
import time
from datetime import datetime
from typing import Optional

from lib.protocol.uart_protocol import (
    FrameEncoder, FrameParser, MessageType, TelemetryPayload
)
from lib.models.messages import DriveCommand, Telemetry, LinkStatus
from lib.bus.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class HardwareGateway:
    """
    Hardware gateway service.
    - Owns UART connection
    - Sends DriveCmd at fixed rate
    - Receives and parses telemetry
    - Publishes telemetry to message bus
    """
    
    def __init__(self, port: str, baudrate: int = 115200, 
                 command_rate_hz: int = 50,
                 max_command_age_ms: int = 250):
        self.port = port
        self.baudrate = baudrate
        self.command_rate_hz = command_rate_hz
        self.command_period = 1.0 / command_rate_hz
        self.max_command_age_s = max_command_age_ms / 1000.0
        
        # Serial port
        self.serial: Optional[serial.Serial] = None
        
        # Protocol
        self.encoder = FrameEncoder()
        self.parser = FrameParser()
        
        # State
        self.current_drive_cmd: Optional[DriveCommand] = None
        self.last_telemetry: Optional[Telemetry] = None
        self.link_status = LinkStatus(
            connected=False,
            frames_sent=0,
            frames_received=0,
            crc_errors=0
        )
        
        # Message bus
        self.bus = get_message_bus()
        
        # Control
        self.running = False
        self._tasks = []
        
        # Stale command tracking
        self._last_stale_warn_time = 0.0
        self._stale_warn_interval = 2.0  # Warn at most every 2 seconds
    
    def open_serial(self):
        """Open serial port"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,  # Non-blocking read with short timeout
                write_timeout=0.5
            )
            logger.info(f"Opened serial port: {self.port} @ {self.baudrate}")
            self.link_status.connected = True
        except serial.SerialException as e:
            logger.error(f"Failed to open serial port: {e}")
            raise
    
    def close_serial(self):
        """Close serial port"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Closed serial port")
        self.link_status.connected = False
    
    async def start(self):
        """Start hardware gateway"""
        self.open_serial()
        self.running = True
        
        # Start tasks
        self._tasks = [
            asyncio.create_task(self._command_sender_task()),
            asyncio.create_task(self._telemetry_receiver_task()),
            asyncio.create_task(self._drive_cmd_subscriber_task())
        ]
        
        logger.info("Hardware gateway started")
    
    async def stop(self):
        """Stop hardware gateway"""
        self.running = False
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to finish
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Close serial
        self.close_serial()
        
        logger.info("Hardware gateway stopped")
    
    async def _drive_cmd_subscriber_task(self):
        """Subscribe to drive commands from message bus"""
        queue = await self.bus.subscribe("drive_command")
        
        try:
            while self.running:
                try:
                    cmd: DriveCommand = await asyncio.wait_for(queue.get(), timeout=1.0)
                    self.current_drive_cmd = cmd
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.debug("Drive command subscriber task cancelled")
    
    async def _command_sender_task(self):
        """Send drive commands at fixed rate"""
        try:
            while self.running:
                start_time = time.monotonic()
                
                # Get current command or default to stop
                if self.current_drive_cmd:
                    cmd = self.current_drive_cmd
                    
                    # Check command age
                    age = (datetime.now() - cmd.timestamp).total_seconds()
                    if age > self.max_command_age_s:
                        # Throttle warning spam
                        now = time.monotonic()
                        if (now - self._last_stale_warn_time) >= self._stale_warn_interval:
                            logger.warning(
                                f"Stale command (age={age:.3f}s > {self.max_command_age_s:.3f}s), sending stop"
                            )
                            self._last_stale_warn_time = now
                        
                        # Send STOP (not E-STOP) - just zero speeds with enable still set
                        # This prevents latching E-STOP on dsPIC
                        cmd = DriveCommand(
                            left_speed=0.0, 
                            right_speed=0.0, 
                            enable_request=True,
                            estop=False,
                            source="hardware_gateway_stale"
                        )
                else:
                    # No command - send stop
                    cmd = DriveCommand(left_speed=0.0, right_speed=0.0, enable_request=False)
                
                # Encode and send
                try:
                    frame = self.encoder.encode_drive_cmd(
                        cmd.left_speed,
                        cmd.right_speed,
                        cmd.enable_request,
                        cmd.estop
                    )
                    
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.serial.write, frame
                    )
                    
                    self.link_status.frames_sent += 1
                    self.link_status.last_command_time = datetime.now()
                    
                except Exception as e:
                    logger.error(f"Failed to send command: {e}")
                
                # Sleep to maintain rate
                elapsed = time.monotonic() - start_time
                sleep_time = max(0, self.command_period - elapsed)
                await asyncio.sleep(sleep_time)
        
        except asyncio.CancelledError:
            logger.debug("Command sender task cancelled")
    
    async def _telemetry_receiver_task(self):
        """Receive and parse telemetry"""
        try:
            while self.running:
                # Read available bytes
                try:
                    if self.serial.in_waiting > 0:
                        data = await asyncio.get_event_loop().run_in_executor(
                            None, self.serial.read, self.serial.in_waiting
                        )
                        
                        # Parse frames
                        frames = self.parser.feed_bytes(data)
                        
                        for frame in frames:
                            self._process_frame(frame)
                        
                        # Update stats
                        self.link_status.crc_errors = self.parser.crc_errors
                    
                    else:
                        # No data available, sleep briefly
                        await asyncio.sleep(0.01)
                
                except Exception as e:
                    logger.error(f"Error receiving telemetry: {e}")
                    await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            logger.debug("Telemetry receiver task cancelled")
    
    def _process_frame(self, frame):
        """Process received frame"""
        if frame.msg_type == MessageType.TELEMETRY:
            try:
                payload = TelemetryPayload.decode(frame.payload)
                
                # Convert to message model
                telemetry = Telemetry(
                    left_pwm=payload.left_pwm,
                    right_pwm=payload.right_pwm,
                    bus_voltage_mv=payload.bus_mv,
                    fault_flags=payload.fault_flags,
                    age_ms=payload.age_ms,
                    timestamp=datetime.now()
                )
                
                self.last_telemetry = telemetry
                self.link_status.frames_received += 1
                self.link_status.last_telemetry_time = datetime.now()
                self.link_status.age_ms = payload.age_ms
                
                # Publish to bus
                asyncio.create_task(self.bus.publish("telemetry", telemetry))
                
            except Exception as e:
                logger.error(f"Failed to decode telemetry: {e}")
        
        elif frame.msg_type == MessageType.ENCODER_DATA:
            # Phase 2: Handle encoder data
            logger.debug("Received encoder data (not yet implemented)")
        
        else:
            logger.debug(f"Received unknown message type: {frame.msg_type}")
    
    def get_link_status(self) -> LinkStatus:
        """Get current link status"""
        return self.link_status
    
    def get_last_telemetry(self) -> Optional[Telemetry]:
        """Get last received telemetry"""
        return self.last_telemetry


# ============================================================================
# STANDALONE RUNNER
# ============================================================================

async def main():
    """Run hardware gateway standalone for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import yaml
    with open('config/rover_config.yaml') as f:
        config = yaml.safe_load(f)
    
    gateway = HardwareGateway(
        port=config['uart']['port'],
        baudrate=config['uart']['baudrate'],
        command_rate_hz=config['hardware_gateway']['command_rate_hz']
    )
    
    try:
        await gateway.start()
        
        # Run for 30 seconds
        await asyncio.sleep(30)
        
    finally:
        await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())

