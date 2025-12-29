"""
Video Service
WebRTC video streaming from Pi Camera
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import av
from fractions import Fraction

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    logging.warning("Picamera2 not available - video service will run in dummy mode")

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from av import VideoFrame
import numpy as np

from lib.bus.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class CameraVideoTrack(VideoStreamTrack):
    """
    Video track that captures from Pi Camera
    """
    
    def __init__(self, width=640, height=480, framerate=30):
        super().__init__()
        self.width = width
        self.height = height
        self.framerate = framerate
        
        # Frame state
        self.frame_count = 0
        self.start_time = datetime.now()
        
        # Initialize camera
        if PICAMERA2_AVAILABLE:
            self._init_picamera2()
        else:
            self._init_dummy()
    
    def _init_picamera2(self):
        """Initialize Picamera2"""
        try:
            self.camera = Picamera2()
            
            # Configure camera
            config = self.camera.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"}
            )
            self.camera.configure(config)
            self.camera.start()
            
            logger.info(f"Picamera2 initialized: {self.width}x{self.height}@{self.framerate}fps")
        
        except Exception as e:
            logger.error(f"Failed to initialize Picamera2: {e}")
            self._init_dummy()
    
    def _init_dummy(self):
        """Initialize dummy mode (no camera)"""
        self.camera = None
        logger.warning("Running in dummy video mode (no camera)")
    
    async def recv(self):
        """Receive next video frame"""
        # aiortc helper provides monotonically increasing pts/time_base
        pts, time_base = await self.next_timestamp()
        
        if self.camera:
            # Capture from real camera
            try:
                # Capture frame
                frame_array = self.camera.capture_array()
                
                # Convert to VideoFrame
                frame = VideoFrame.from_ndarray(frame_array, format="rgb24")
                frame.pts = pts
                frame.time_base = time_base
                
                self.frame_count += 1
                
                return frame
            
            except Exception as e:
                logger.error(f"Failed to capture frame: {e}")
                # Fall through to dummy frame
        
        # Generate dummy frame (color bars or test pattern)
        frame = self._generate_dummy_frame()
        frame.pts = pts
        frame.time_base = time_base
        
        self.frame_count += 1
        
        # Sleep to maintain framerate
        await asyncio.sleep(1.0 / self.framerate)
        
        return frame
    
    def _generate_dummy_frame(self):
        """Generate a dummy test pattern frame"""
        # Create color bars test pattern
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Color bars
        bar_width = self.width // 7
        colors = [
            (255, 255, 255),  # White
            (255, 255, 0),    # Yellow
            (0, 255, 255),    # Cyan
            (0, 255, 0),      # Green
            (255, 0, 255),    # Magenta
            (255, 0, 0),      # Red
            (0, 0, 255),      # Blue
        ]
        
        for i, color in enumerate(colors):
            x_start = i * bar_width
            x_end = min((i + 1) * bar_width, self.width)
            img[:, x_start:x_end] = color
        
        # Add frame counter text (simple)
        # (Requires cv2 for actual text rendering, skipping for simplicity)
        
        return VideoFrame.from_ndarray(img, format="rgb24")
    
    def stop(self):
        """Stop camera"""
        if self.camera and PICAMERA2_AVAILABLE:
            try:
                self.camera.stop()
                logger.info("Camera stopped")
            except Exception as e:
                logger.error(f"Error stopping camera: {e}")


class VideoService:
    """
    WebRTC video streaming service.
    Manages peer connections and video tracks.
    """
    
    def __init__(self, width=640, height=480, framerate=30):
        self.width = width
        self.height = height
        self.framerate = framerate
        
        # Peer connections
        self.peer_connections = {}
        
        # Message bus
        self.bus = get_message_bus()
        
        # Control
        self.running = False
    
    async def create_offer(self, connection_id: str) -> dict:
        """
        Create WebRTC offer for a client.
        Returns SDP offer.
        """
        pc = RTCPeerConnection()
        self.peer_connections[connection_id] = pc

        @pc.on("iceconnectionstatechange")
        async def on_ice_state_change():
            logger.info(f"ICE state ({connection_id}): {pc.iceConnectionState}")

        @pc.on("connectionstatechange")
        async def on_conn_state_change():
            logger.info(f"Peer connection state ({connection_id}): {pc.connectionState}")
        
        # Add video track
        video_track = CameraVideoTrack(
            width=self.width,
            height=self.height,
            framerate=self.framerate
        )
        pc.addTrack(video_track)
        
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # Wait for ICE gathering to complete so SDP includes candidates.
        # Without this, many browsers will stay stuck at "waiting for video" on LAN.
        async def wait_for_ice_gathering_complete(timeout_s: float = 5.0):
            if pc.iceGatheringState == "complete":
                return
            done = asyncio.Event()

            @pc.on("icegatheringstatechange")
            async def on_ice_gathering_state_change():
                if pc.iceGatheringState == "complete":
                    done.set()

            try:
                await asyncio.wait_for(done.wait(), timeout=timeout_s)
            except asyncio.TimeoutError:
                logger.warning(f"ICE gathering did not complete within {timeout_s}s (state={pc.iceGatheringState})")

        await wait_for_ice_gathering_complete()
        
        logger.info(f"Created WebRTC offer for connection: {connection_id}")
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
    
    async def handle_answer(self, connection_id: str, answer: dict):
        """Handle WebRTC answer from client"""
        pc = self.peer_connections.get(connection_id)
        if not pc:
            logger.error(f"No peer connection found for: {connection_id}")
            return
        
        # Set remote description
        remote_desc = RTCSessionDescription(
            sdp=answer["sdp"],
            type=answer["type"]
        )
        await pc.setRemoteDescription(remote_desc)
        
        logger.info(f"Handled WebRTC answer for connection: {connection_id}")
    
    async def close_connection(self, connection_id: str):
        """Close peer connection"""
        pc = self.peer_connections.pop(connection_id, None)
        if pc:
            await pc.close()
            logger.info(f"Closed WebRTC connection: {connection_id}")
    
    async def start(self):
        """Start video service"""
        self.running = True
        logger.info("Video service started")
    
    async def stop(self):
        """Stop video service"""
        self.running = False
        
        # Close all peer connections
        for connection_id in list(self.peer_connections.keys()):
            await self.close_connection(connection_id)
        
        logger.info("Video service stopped")


# ============================================================================
# STANDALONE RUNNER
# ============================================================================

async def main():
    """Run video service standalone for testing"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = VideoService()
    
    try:
        await service.start()
        
        # Keep running
        logger.info("Video service running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())

