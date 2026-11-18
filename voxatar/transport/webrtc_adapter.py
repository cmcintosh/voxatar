"""
WebRTC transport adapter using aiortc.

Provides real-time audio transport between the browser and the Voxatar pipeline.
Implements a signaling endpoint for WebRTC connection establishment.
"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

import voxatar
voxatar.register_transport("webrtc", None)  # placeholder, replaced below


class WebRTCTransport:
    """
    WebRTC transport using aiortc.

    Handles:
    - WebRTC peer connection setup via SDP offer/answer
    - Audio track reception from browser (microphone)
    - Audio track transmission to browser (TTS output)
    - Track event handling for pipeline integration
    """

    def __init__(
        self,
        on_audio_chunk: Optional[Callable] = None,
        on_connection_state_change: Optional[Callable] = None,
    ):
        """
        Initialize the WebRTC transport.

        Args:
            on_audio_chunk: Callback for received audio chunks from browser
            on_connection_state_change: Callback for connection state changes
        """
        self.on_audio_chunk = on_audio_chunk
        self.on_connection_state_change = on_connection_state_change
        self._pc = None
        self._audio_track_in = None  # Track receiving audio from browser
        self._audio_track_out = None  # Track sending audio to browser
        self._running = False
        self._outbound_queue: asyncio.Queue = asyncio.Queue()

    async def create_peer_connection(self, offer_sdp: str) -> str:
        """
        Create a peer connection from an SDP offer.

        Args:
            offer_sdp: SDP offer from the browser

        Returns:
            SDP answer to send back to the browser
        """
        from aiortc import RTCPeerConnection, RTCSessionDescription
        from aiortc.contrib.media import MediaStreamTrack

        pc = RTCPeerConnection()

        # Store reference
        self._pc = pc

        # Handle connection state changes
        @pc.on("connectionstatechange")
        async def on_state_change():
            state = pc.connectionState
            logger.info(f"WebRTC connection state: {state}")
            if self.on_connection_state_change:
                await self.on_connection_state_change(state)
            if state in ("failed", "closed"):
                self._running = False

        # Handle incoming audio track from browser
        @pc.on("track")
        def on_track(track):
            logger.info(f"Received track: {track.kind}")
            if track.kind == "audio":
                self._audio_track_in = track
                self._running = True
                # Start receiving audio
                asyncio.ensure_future(self._receive_audio(track))

        # Create an outbound audio track for TTS output
        from aiortc.mediastreams import AudioStreamTrack

        class OutboundAudioTrack(AudioStreamTrack):
            """Custom audio track that pulls from the outbound queue."""

            def __init__(self, transport):
                super().__init__()
                self._transport = transport
                self._sample_rate = 48000
                self._samples_per_frame = 960  # 20ms at 48kHz

            async def recv(self):
                import av
                from datetime import datetime

                pts, time_base = await self.next_timestamp()

                # Try to get audio from queue (non-blocking with small timeout)
                try:
                    audio_data = await asyncio.wait_for(
                        self._transport._outbound_queue.get(),
                        timeout=0.02,
                    )
                    # Convert MP3 bytes to PCM frames
                    # For MVP, we'll generate silence if conversion fails
                    frame = self._create_silence_frame(pts, time_base)
                    return frame
                except asyncio.TimeoutError:
                    # No audio available, send silence
                    frame = self._create_silence_frame(pts, time_base)
                    return frame

            def _create_silence_frame(self, pts, time_base):
                """Create a silence audio frame."""
                import av
                frame = av.AudioFrame(format="s16", layout="mono", samples=960)
                frame.pts = pts
                frame.time_base = time_base
                frame.planes[0].update(b"\x00" * 1920)  # 960 samples * 2 bytes
                return frame

        self._audio_track_out = OutboundAudioTrack(self)
        pc.addTrack(self._audio_track_out)

        # Set remote description (the offer)
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await pc.setRemoteDescription(offer)

        # Create and set local description (the answer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        logger.info("WebRTC peer connection established")
        return pc.localDescription.sdp

    async def _receive_audio(self, track):
        """Receive audio frames from the browser's microphone."""
        logger.info("Starting audio reception loop")

        while self._running:
            try:
                frame = await track.recv()
                # Convert frame to PCM bytes
                audio_bytes = self._frame_to_pcm(frame)

                if self.on_audio_chunk:
                    await self.on_audio_chunk(audio_bytes)

            except Exception as e:
                if self._running:
                    logger.debug(f"Audio reception error: {e}")
                break

        logger.info("Audio reception loop ended")

    @staticmethod
    def _frame_to_pcm(frame) -> bytes:
        """Convert an aiortc audio frame to 16-bit PCM bytes."""
        import numpy as np

        try:
            # Get the frame data as numpy array
            arr = frame.to_ndarray()
            # Flatten to mono if needed
            if arr.ndim > 1:
                arr = arr.mean(axis=0)
            # Convert to 16-bit PCM
            arr = (arr * 32768).clip(-32768, 32767).astype(np.int16)
            return arr.tobytes()
        except Exception as e:
            logger.debug(f"Frame conversion error: {e}")
            return b""

    async def send_audio(self, audio: bytes) -> None:
        """
        Send audio to the browser via the outbound track.

        For MVP, this puts audio into the outbound queue.
        Full MP3→PCM conversion would be implemented for production.

        Args:
            audio: Audio bytes to send
        """
        await self._outbound_queue.put(audio)

    async def send_video(self, frame: bytes) -> None:
        """Send video frame to browser (not implemented in Phase 1)."""
        pass

    async def close(self) -> None:
        """Close the peer connection."""
        self._running = False
        if self._pc:
            await self._pc.close()
            self._pc = None
        logger.info("WebRTC transport closed")

    async def start_server(self, host: str, port: int) -> None:
        """Start the transport server (handled by FastAPI for WebRTC)."""
        pass

    async def stop_server(self) -> None:
        """Stop the transport server."""
        await self.close()


# Replace placeholder registration
voxatar._REGISTRY["transport"]["webrtc"] = WebRTCTransport