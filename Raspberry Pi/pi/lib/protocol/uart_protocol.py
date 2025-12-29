"""
UART Protocol Implementation (Python side)
Matches dsPIC firmware protocol specification
"""

import struct
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum


# ============================================================================
# PROTOCOL CONSTANTS
# ============================================================================

SOF_BYTE_0 = 0xAA
SOF_BYTE_1 = 0x55
PROTOCOL_VERSION = 0x01

class MessageType(IntEnum):
    DRIVE_CMD = 0x01
    STOP_CMD = 0x02
    TELEMETRY = 0x10
    ENCODER_DATA = 0x11
    HEARTBEAT = 0xFE
    ERROR_REPORT = 0xFF


# Drive command flags
DRIVE_FLAG_ESTOP = 0x0001
DRIVE_FLAG_ENABLE_REQUEST = 0x0002


# ============================================================================
# CRC-16/CCITT-FALSE
# ============================================================================

def crc16_ccitt(data: bytes) -> int:
    """Compute CRC-16/CCITT-FALSE"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF  # Keep 16-bit
    return crc


# ============================================================================
# FRAME STRUCTURES
# ============================================================================

@dataclass
class Frame:
    """Protocol frame"""
    version: int
    msg_type: int
    seq: int
    payload: bytes
    
    def encode(self) -> bytes:
        """Encode frame to bytes"""
        # Header
        header = struct.pack(
            '<BBBB',
            self.version,
            self.msg_type,
            self.seq,
            len(self.payload)
        )
        
        # Compute CRC over header + payload
        crc_data = header + self.payload
        crc = crc16_ccitt(crc_data)
        
        # Assemble frame
        frame = struct.pack('<BB', SOF_BYTE_0, SOF_BYTE_1)
        frame += crc_data
        frame += struct.pack('<H', crc)
        
        return frame


# ============================================================================
# MESSAGE PAYLOADS
# ============================================================================

@dataclass
class DriveCmdPayload:
    """Drive command payload"""
    left_q15: int  # -32767 to +32767
    right_q15: int
    flags: int
    
    def encode(self) -> bytes:
        return struct.pack('<hhH', self.left_q15, self.right_q15, self.flags)
    
    @staticmethod
    def from_speeds(left_speed: float, right_speed: float, 
                   enable: bool = True, estop: bool = False) -> 'DriveCmdPayload':
        """Create from normalized speeds (-1.0 to +1.0)"""
        # Clamp
        left_speed = max(-1.0, min(1.0, left_speed))
        right_speed = max(-1.0, min(1.0, right_speed))
        
        # Convert to Q15
        left_q15 = int(left_speed * 32767)
        right_q15 = int(right_speed * 32767)
        
        # Set flags
        flags = 0
        if estop:
            flags |= DRIVE_FLAG_ESTOP
        if enable:
            flags |= DRIVE_FLAG_ENABLE_REQUEST
        
        return DriveCmdPayload(left_q15, right_q15, flags)


@dataclass
class TelemetryPayload:
    """Telemetry payload"""
    left_pwm: int
    right_pwm: int
    bus_mv: int
    fault_flags: int
    age_ms: int
    
    @staticmethod
    def decode(data: bytes) -> 'TelemetryPayload':
        """Decode from bytes"""
        if len(data) != 10:
            raise ValueError(f"Invalid telemetry payload length: {len(data)}")
        
        left_pwm, right_pwm, bus_mv, fault_flags, age_ms = struct.unpack('<hhHHH', data)
        
        return TelemetryPayload(
            left_pwm=left_pwm,
            right_pwm=right_pwm,
            bus_mv=bus_mv,
            fault_flags=fault_flags,
            age_ms=age_ms
        )


@dataclass
class EncoderDataPayload:
    """Encoder data payload (Phase 2)"""
    left_ticks: int
    right_ticks: int
    left_vel: int
    right_vel: int
    timestamp: int
    
    @staticmethod
    def decode(data: bytes) -> 'EncoderDataPayload':
        """Decode from bytes"""
        if len(data) != 16:
            raise ValueError(f"Invalid encoder payload length: {len(data)}")
        
        left_ticks, right_ticks, left_vel, right_vel, timestamp = struct.unpack(
            '<iihhI', data
        )
        
        return EncoderDataPayload(
            left_ticks=left_ticks,
            right_ticks=right_ticks,
            left_vel=left_vel,
            right_vel=right_vel,
            timestamp=timestamp
        )


# ============================================================================
# FRAME ENCODER
# ============================================================================

class FrameEncoder:
    """Encode protocol frames"""
    
    def __init__(self):
        self.seq = 0
    
    def encode_drive_cmd(self, left_speed: float, right_speed: float,
                        enable: bool = True, estop: bool = False) -> bytes:
        """Encode drive command"""
        payload = DriveCmdPayload.from_speeds(left_speed, right_speed, enable, estop)
        frame = Frame(
            version=PROTOCOL_VERSION,
            msg_type=MessageType.DRIVE_CMD,
            seq=self.seq,
            payload=payload.encode()
        )
        self.seq = (self.seq + 1) & 0xFF
        return frame.encode()
    
    def encode_stop_cmd(self) -> bytes:
        """Encode stop command"""
        frame = Frame(
            version=PROTOCOL_VERSION,
            msg_type=MessageType.STOP_CMD,
            seq=self.seq,
            payload=b''
        )
        self.seq = (self.seq + 1) & 0xFF
        return frame.encode()


# ============================================================================
# FRAME PARSER
# ============================================================================

class ParserState(IntEnum):
    SCANNING_SOF = 0
    READING_HEADER = 1
    READING_PAYLOAD = 2
    READING_CRC = 3


class FrameParser:
    """Parse incoming protocol frames"""
    
    def __init__(self):
        self.state = ParserState.SCANNING_SOF
        self.sof_buf = bytearray(2)
        self.header_buf = bytearray(4)
        self.header_idx = 0
        self.payload_buf = bytearray(255)
        self.payload_idx = 0
        self.payload_len = 0
        self.crc_buf = bytearray(2)
        self.crc_idx = 0
        
        # Current frame being parsed
        self.version = 0
        self.msg_type = 0
        self.seq = 0
        
        # Statistics
        self.frames_received = 0
        self.crc_errors = 0
        self.version_errors = 0
    
    def feed_byte(self, byte: int) -> Optional[Frame]:
        """
        Feed a byte to the parser.
        Returns Frame if complete valid frame received, None otherwise.
        """
        if self.state == ParserState.SCANNING_SOF:
            # Shift SOF buffer
            self.sof_buf[0] = self.sof_buf[1]
            self.sof_buf[1] = byte
            
            # Check for SOF
            if self.sof_buf[0] == SOF_BYTE_0 and self.sof_buf[1] == SOF_BYTE_1:
                self.state = ParserState.READING_HEADER
                self.header_idx = 0
        
        elif self.state == ParserState.READING_HEADER:
            self.header_buf[self.header_idx] = byte
            self.header_idx += 1
            
            if self.header_idx >= 4:
                # Parse header
                self.version = self.header_buf[0]
                self.msg_type = self.header_buf[1]
                self.seq = self.header_buf[2]
                self.payload_len = self.header_buf[3]
                
                # Validate version
                if self.version != PROTOCOL_VERSION:
                    self.version_errors += 1
                    self.state = ParserState.SCANNING_SOF
                    return None
                
                # Move to payload or CRC
                self.payload_idx = 0
                if self.payload_len > 0:
                    self.state = ParserState.READING_PAYLOAD
                else:
                    self.state = ParserState.READING_CRC
                    self.crc_idx = 0
        
        elif self.state == ParserState.READING_PAYLOAD:
            self.payload_buf[self.payload_idx] = byte
            self.payload_idx += 1
            
            if self.payload_idx >= self.payload_len:
                self.state = ParserState.READING_CRC
                self.crc_idx = 0
        
        elif self.state == ParserState.READING_CRC:
            self.crc_buf[self.crc_idx] = byte
            self.crc_idx += 1
            
            if self.crc_idx >= 2:
                # Extract CRC (little-endian)
                received_crc = self.crc_buf[0] | (self.crc_buf[1] << 8)
                
                # Compute CRC
                crc_data = bytes(self.header_buf) + bytes(self.payload_buf[:self.payload_len])
                computed_crc = crc16_ccitt(crc_data)
                
                # Validate
                self.state = ParserState.SCANNING_SOF
                
                if computed_crc == received_crc:
                    self.frames_received += 1
                    payload = bytes(self.payload_buf[:self.payload_len])
                    return Frame(
                        version=self.version,
                        msg_type=self.msg_type,
                        seq=self.seq,
                        payload=payload
                    )
                else:
                    self.crc_errors += 1
        
        return None
    
    def feed_bytes(self, data: bytes) -> list:
        """Feed multiple bytes, return list of complete frames"""
        frames = []
        for byte in data:
            frame = self.feed_byte(byte)
            if frame is not None:
                frames.append(frame)
        return frames


# ============================================================================
# ASCII PROTOCOL (Fallback)
# ============================================================================

class AsciiProtocol:
    """ASCII protocol encoder/decoder for debugging"""
    
    @staticmethod
    def encode_drive_cmd(left_speed: float, right_speed: float) -> bytes:
        """Encode drive command as ASCII"""
        line = f"D {left_speed:.3f} {right_speed:.3f}\n"
        return line.encode('ascii')
    
    @staticmethod
    def encode_stop_cmd() -> bytes:
        """Encode stop command"""
        return b"S\n"
    
    @staticmethod
    def encode_enable_cmd() -> bytes:
        """Encode enable command"""
        return b"E\n"
    
    @staticmethod
    def parse_telemetry(line: str) -> Optional[TelemetryPayload]:
        """Parse ASCII telemetry line"""
        # Format: T <left_pwm> <right_pwm> <bus_mv> <fault> <age>
        if not line.startswith('T '):
            return None
        
        try:
            parts = line[2:].split()
            if len(parts) != 5:
                return None
            
            return TelemetryPayload(
                left_pwm=int(parts[0]),
                right_pwm=int(parts[1]),
                bus_mv=int(parts[2]),
                fault_flags=int(parts[3]),
                age_ms=int(parts[4])
            )
        except (ValueError, IndexError):
            return None

