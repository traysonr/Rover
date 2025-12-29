"""
Rover Message Type Definitions
Pydantic models for all inter-service messages
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


# ============================================================================
# ENUMS
# ============================================================================

class SystemState(str, Enum):
    BOOT = "boot"
    ENABLED = "enabled"
    FAULTED = "faulted"
    STOPPED = "stopped"


class FaultFlag(str, Enum):
    WATCHDOG_TIMEOUT = "watchdog_timeout"
    ESTOP_ACTIVE = "estop_active"
    UNDERVOLTAGE = "undervoltage"
    OVERVOLTAGE = "overvoltage"
    DRIVER_FAULT = "driver_fault"
    OVERCURRENT = "overcurrent"
    THERMAL_WARNING = "thermal_warning"


# ============================================================================
# DRIVE COMMANDS
# ============================================================================

class DriveCommand(BaseModel):
    """Normalized drive command (-1.0 to +1.0)"""
    left_speed: float = Field(ge=-1.0, le=1.0, description="Left motor speed")
    right_speed: float = Field(ge=-1.0, le=1.0, description="Right motor speed")
    enable_request: bool = Field(default=True, description="Request drive enable")
    estop: bool = Field(default=False, description="Emergency stop")
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(default="unknown", description="Command source")


class TeleopInput(BaseModel):
    """Raw teleoperation input"""
    throttle: float = Field(ge=-1.0, le=1.0, description="Forward/backward")
    turn: float = Field(ge=-1.0, le=1.0, description="Left/right turn")
    enable: bool = Field(default=True)
    estop: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# TELEMETRY
# ============================================================================

class Telemetry(BaseModel):
    """dsPIC telemetry data"""
    left_pwm: int = Field(description="Left motor PWM (-10000 to +10000)")
    right_pwm: int = Field(description="Right motor PWM")
    bus_voltage_mv: int = Field(description="Bus voltage in millivolts")
    fault_flags: int = Field(description="Raw fault flags bitmask")
    age_ms: int = Field(description="Age since last command (ms)")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def faults(self) -> List[FaultFlag]:
        """Parse fault flags into list of active faults"""
        active_faults = []
        if self.fault_flags & 0x0001:
            active_faults.append(FaultFlag.WATCHDOG_TIMEOUT)
        if self.fault_flags & 0x0002:
            active_faults.append(FaultFlag.ESTOP_ACTIVE)
        if self.fault_flags & 0x0004:
            active_faults.append(FaultFlag.UNDERVOLTAGE)
        if self.fault_flags & 0x0008:
            active_faults.append(FaultFlag.OVERVOLTAGE)
        if self.fault_flags & 0x0010:
            active_faults.append(FaultFlag.DRIVER_FAULT)
        if self.fault_flags & 0x0020:
            active_faults.append(FaultFlag.OVERCURRENT)
        if self.fault_flags & 0x0040:
            active_faults.append(FaultFlag.THERMAL_WARNING)
        return active_faults
    
    @property
    def has_fault(self) -> bool:
        return self.fault_flags != 0
    
    @property
    def bus_voltage_v(self) -> float:
        return self.bus_voltage_mv / 1000.0


class EncoderData(BaseModel):
    """Encoder data (Phase 2)"""
    left_ticks: int
    right_ticks: int
    left_velocity: float  # ticks/sec
    right_velocity: float
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# SYSTEM STATUS
# ============================================================================

class LinkStatus(BaseModel):
    """Hardware link status"""
    connected: bool = Field(description="Link established")
    last_telemetry_time: Optional[datetime] = None
    last_command_time: Optional[datetime] = None
    frames_sent: int = 0
    frames_received: int = 0
    crc_errors: int = 0
    age_ms: int = 0


class SystemHealth(BaseModel):
    """Overall system health"""
    state: SystemState
    link_status: LinkStatus
    last_telemetry: Optional[Telemetry] = None
    uptime_sec: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# VIDEO
# ============================================================================

class VideoFrame(BaseModel):
    """Video frame metadata (frame data passed separately)"""
    width: int
    height: int
    format: str  # "rgb", "yuv420", etc.
    timestamp: datetime = Field(default_factory=datetime.now)
    sequence: int = 0


class VideoStats(BaseModel):
    """Video streaming statistics"""
    fps: float = 0.0
    bitrate_kbps: float = 0.0
    frames_sent: int = 0
    frames_dropped: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# PERCEPTION (Phase 3)
# ============================================================================

class BoundingBox(BaseModel):
    """Object detection bounding box"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    class_name: str


class Detection(BaseModel):
    """Object detection result"""
    boxes: List[BoundingBox]
    timestamp: datetime = Field(default_factory=datetime.now)


class Marker(BaseModel):
    """Fiducial marker detection"""
    marker_id: int
    corners: List[List[float]]  # 4 corners, each [x, y]
    pose: Optional[List[float]] = None  # [x, y, z, roll, pitch, yaw]
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# MISSIONS (Phase 4)
# ============================================================================

class MissionGoal(BaseModel):
    """High-level mission goal"""
    goal_type: str  # "patrol", "find_object", "return_to_dock"
    target: Optional[str] = None
    parameters: dict = {}
    timestamp: datetime = Field(default_factory=datetime.now)


class MissionStatus(BaseModel):
    """Mission execution status"""
    active: bool
    goal: Optional[MissionGoal] = None
    state: str = "idle"
    progress: float = 0.0
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# EVENTS
# ============================================================================

class Event(BaseModel):
    """Generic system event"""
    event_type: str
    severity: str  # "debug", "info", "warning", "error", "critical"
    message: str
    data: dict = {}
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# API MODELS
# ============================================================================

class HealthResponse(BaseModel):
    """API health check response"""
    status: str
    system_health: SystemHealth


class TeleopCommandRequest(BaseModel):
    """API request to send teleop command"""
    throttle: float = Field(ge=-1.0, le=1.0)
    turn: float = Field(ge=-1.0, le=1.0)


class EmergencyStopRequest(BaseModel):
    """API request for emergency stop"""
    stop: bool = True

