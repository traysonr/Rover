"""
API Server
FastAPI + WebSocket for rover control UI
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from lib.models.messages import (
    TeleopInput, DriveCommand, Telemetry, SystemHealth, SystemState,
    LinkStatus, HealthResponse, TeleopCommandRequest, EmergencyStopRequest
)
from lib.bus.message_bus import get_message_bus

# Import services
import sys
sys.path.insert(0, '..')
from hardware_gateway.hardware_gateway import HardwareGateway
from teleop.teleop_service import TeleopService
from video_service.video_service import VideoService

# Import motor controller backends
from lib.motor.motor_controller import MotorController
from motor_uart.uart_motor_controller import UartMotorController
from motor_pi_pwm.pi_pwm_motor_controller import PiPwmMotorController

logger = logging.getLogger(__name__)


# ============================================================================
# GLOBAL STATE
# ============================================================================

class AppState:
    """Global application state"""
    def __init__(self):
        self.bus = get_message_bus()
        self.motor_controller: Optional[MotorController] = None
        self.hardware_gateway: Optional[HardwareGateway] = None  # Keep for backward compat
        self.teleop_service: Optional[TeleopService] = None
        self.video_service: Optional[VideoService] = None
        self.websocket_connections: Dict[str, WebSocket] = {}
        self.start_time = datetime.now()


app_state = AppState()


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Rover Control API",
    description="REST + WebSocket API for rover teleoperation",
    version="1.0.0"
)

# UI paths (serve `pi/ui/index.html` at "/")
_PI_ROOT = Path(__file__).resolve().parents[2]   # .../Raspberry Pi/pi
_UI_DIR = _PI_ROOT / "ui"
_UI_INDEX = _UI_DIR / "index.html"

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting rover control API server...")
    
    # Load config
    import yaml
    with open('../../config/rover_config.yaml') as f:
        config = yaml.safe_load(f)
    
    # Initialize motor controller backend
    backend = config['control']['backend']
    logger.info(f"Initializing motor controller backend: {backend}")
    
    if backend == "uart":
        # UART/dsPIC backend
        app_state.motor_controller = UartMotorController(
            port=config['uart']['port'],
            baudrate=config['uart']['baudrate'],
            command_rate_hz=config['hardware_gateway']['command_rate_hz'],
            max_command_age_ms=config['hardware_gateway'].get('max_command_age_ms', 250)
        )
        # Keep hardware_gateway reference for backward compatibility
        app_state.hardware_gateway = app_state.motor_controller.hardware_gateway
        
    elif backend == "pi_pwm":
        # Pi GPIO PWM backend (L298N)
        pwm_config = config['control']['pi_pwm']
        app_state.motor_controller = PiPwmMotorController(
            left_in1=pwm_config['left_in1'],
            left_in2=pwm_config['left_in2'],
            left_ena=pwm_config['left_ena'],
            right_in3=pwm_config['right_in3'],
            right_in4=pwm_config['right_in4'],
            right_enb=pwm_config['right_enb'],
            pwm_frequency=pwm_config['pwm_frequency'],
            max_command_age_s=pwm_config['max_command_age_ms'] / 1000.0,
            deadband=pwm_config.get('deadband', 0.05)
        )
        # No hardware_gateway in this mode
        app_state.hardware_gateway = None
    
    else:
        raise ValueError(f"Unknown motor controller backend: {backend}")
    
    # Initialize other services
    app_state.teleop_service = TeleopService(
        max_speed=config['teleop']['max_speed'],
        deadband=config['teleop']['deadband'],
        slew_rate_per_sec=config['teleop']['slew_rate_per_sec']
    )
    
    app_state.video_service = VideoService(
        width=config['video']['width'],
        height=config['video']['height'],
        framerate=config['video']['framerate']
    )
    
    # Start services
    try:
        await app_state.motor_controller.start()
        await app_state.teleop_service.start()
        await app_state.video_service.start()
        
        # Start telemetry broadcaster
        asyncio.create_task(telemetry_broadcaster())
        
        logger.info("All services started successfully")
    
    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down rover control API server...")
    
    # Stop services
    if app_state.video_service:
        await app_state.video_service.stop()
    if app_state.teleop_service:
        await app_state.teleop_service.stop()
    if app_state.motor_controller:
        await app_state.motor_controller.stop()
    
    logger.info("Shutdown complete")


# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Serve the control UI (single-page HTML)"""
    return FileResponse(_UI_INDEX)


@app.get("/api")
async def api_root():
    """API root endpoint (JSON)"""
    return {"service": "Rover Control API", "version": "1.0.0", "status": "running"}


@app.get("/api/v1/health", response_model=HealthResponse)
async def get_health():
    """Get system health status"""
    if not app_state.motor_controller:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    # Get status from motor controller (works with both backends)
    motor_status = app_state.motor_controller.get_status()
    link_status = app_state.motor_controller.get_link_status()
    last_telemetry = app_state.motor_controller.get_telemetry()
    
    # Determine system state
    if last_telemetry and last_telemetry.has_fault:
        state = SystemState.FAULTED
    elif motor_status.enabled:
        state = SystemState.ENABLED
    else:
        state = SystemState.STOPPED
    
    uptime = (datetime.now() - app_state.start_time).total_seconds()
    
    # Create link status if backend doesn't provide it
    if link_status is None:
        link_status = LinkStatus(
            connected=motor_status.enabled,
            frames_sent=0,
            frames_received=0,
            crc_errors=0
        )
    
    system_health = SystemHealth(
        state=state,
        link_status=link_status,
        last_telemetry=last_telemetry,
        uptime_sec=uptime
    )
    
    return HealthResponse(
        status="ok",
        system_health=system_health
    )


@app.post("/api/v1/teleop")
async def post_teleop_command(cmd: TeleopCommandRequest):
    """Send teleoperation command"""
    teleop_input = TeleopInput(
        throttle=cmd.throttle,
        turn=cmd.turn,
        enable=True,
        estop=False
    )
    
    await app_state.bus.publish("teleop_input", teleop_input)
    
    return {"status": "ok", "message": "Command sent"}


@app.post("/api/v1/stop")
async def post_emergency_stop(req: EmergencyStopRequest):
    """Emergency stop"""
    if req.stop:
        teleop_input = TeleopInput(
            throttle=0.0,
            turn=0.0,
            enable=False,
            estop=True
        )
        
        await app_state.bus.publish("teleop_input", teleop_input)
        
        return {"status": "ok", "message": "Emergency stop activated"}
    else:
        return {"status": "ok", "message": "No action taken"}


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time control and telemetry.
    
    Client → Server messages:
        {"type": "teleop", "throttle": 0.5, "turn": 0.0}
        {"type": "stop"}
        {"type": "webrtc_offer", "sdp": "...", "type": "offer"}
        {"type": "webrtc_answer", "sdp": "...", "type": "answer"}
    
    Server → Client messages:
        {"type": "telemetry", "data": {...}}
        {"type": "health", "data": {...}}
        {"type": "webrtc_offer", "sdp": "...", "type": "offer"}
    """
    await websocket.accept()
    
    connection_id = str(uuid.uuid4())
    app_state.websocket_connections[connection_id] = websocket
    
    logger.info(f"WebSocket connected: {connection_id}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "teleop":
                # Teleop command
                teleop_input = TeleopInput(
                    throttle=message.get("throttle", 0.0),
                    turn=message.get("turn", 0.0),
                    enable=message.get("enable", True),
                    estop=message.get("estop", False)
                )
                await app_state.bus.publish("teleop_input", teleop_input)
            
            elif msg_type == "stop":
                # Emergency stop
                teleop_input = TeleopInput(
                    throttle=0.0,
                    turn=0.0,
                    enable=False,
                    estop=True
                )
                await app_state.bus.publish("teleop_input", teleop_input)
            
            elif msg_type == "webrtc_answer":
                # WebRTC answer from client
                answer = {
                    "sdp": message.get("sdp"),
                    "type": message.get("sdpType", "answer")
                }
                await app_state.video_service.handle_answer(connection_id, answer)
            
            elif msg_type == "webrtc_request":
                # Client requesting WebRTC offer
                offer = await app_state.video_service.create_offer(connection_id)
                await websocket.send_text(json.dumps({
                    "type": "webrtc_offer",
                    "sdp": offer["sdp"],
                    "sdpType": offer["type"]
                }))
            
            else:
                logger.warning(f"Unknown message type: {msg_type}")
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        # Cleanup
        app_state.websocket_connections.pop(connection_id, None)
        await app_state.video_service.close_connection(connection_id)


# ============================================================================
# TELEMETRY BROADCASTER
# ============================================================================

async def telemetry_broadcaster():
    """Broadcast telemetry to all connected WebSocket clients"""
    queue = await app_state.bus.subscribe("telemetry")
    
    while True:
        try:
            telemetry: Telemetry = await queue.get()
            
            # Convert to dict for JSON serialization
            telemetry_dict = telemetry.dict()
            telemetry_dict['timestamp'] = telemetry.timestamp.isoformat()
            
            # Get link status from motor controller (if available)
            link_status = app_state.motor_controller.get_link_status()
            if link_status:
                link_status_dict = link_status.dict()
            else:
                # Pi PWM backend doesn't have link status
                link_status_dict = {
                    "connected": True,
                    "frames_sent": 0,
                    "frames_received": 0,
                    "crc_errors": 0
                }
            
            message = {
                "type": "telemetry",
                "data": telemetry_dict,
                "link_status": link_status_dict
            }
            
            # Broadcast to all connections
            for connection_id, websocket in list(app_state.websocket_connections.items()):
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to send telemetry to {connection_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in telemetry broadcaster: {e}")
            await asyncio.sleep(1)


# ============================================================================
# STATIC FILES (UI)
# ============================================================================

# If you add additional UI assets later, expose them under /ui/.
# (Today the UI is a single HTML file served at "/".)
if _UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_UI_DIR)), name="ui")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

