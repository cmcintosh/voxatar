"""
FastAPI server for Voxatar.

Provides:
- WebRTC signaling endpoint (/api/webrtc/offer)
- Agent configuration endpoint (/api/agent)
- WebSocket endpoint for transcript streaming (/ws/transcript)
- Static file serving for the web frontend
- Health check endpoint
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from voxatar.config import AgentConfig
from voxatar.pipeline import VoiceAgentPipeline, TranscriptEvent
from voxatar.transport.webrtc_adapter import WebRTCTransport

logger = logging.getLogger(__name__)


class VoxatarServer:
    """
    FastAPI server that hosts the Voxatar voice agent.

    Manages:
    - Agent pipeline instances
    - WebRTC peer connections
    - WebSocket connections for transcript streaming
    - Static frontend serving
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.app = FastAPI(
            title="Voxatar",
            description="Open-source AI voice agent server",
            version="0.1.0",
        )
        self.pipeline: Optional[VoiceAgentPipeline] = None
        self.transport: Optional[WebRTCTransport] = None
        self._websocket_clients: list[WebSocket] = []
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """Configure CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """Set up all API routes."""

        @self.app.get("/api/health")
        async def health():
            """Health check endpoint."""
            return {
                "status": "ok",
                "agent": self.config.name,
                "state": self.pipeline.state.value if self.pipeline else "uninitialized",
            }

        @self.app.get("/api/agent")
        async def get_agent_config():
            """Get agent configuration (safe to expose to frontend)."""
            return {
                "name": self.config.name,
                "role": self.config.role,
                "organization": self.config.organization,
                "objectives": self.config.objectives,
                "predefined_questions": self.config.predefined_questions,
                "require_consent": self.config.require_consent,
                "consent_message": self.config.consent_message,
                "max_duration": self.config.max_duration,
                "tts_voice": self.config.voice_id,
                "available_voices": self.tts.list_voices() if self.tts else [],
            }

        @self.app.post("/api/webrtc/offer")
        async def webrtc_offer(request: Request):
            """Handle WebRTC SDP offer from the browser."""
            body = await request.json()
            offer_sdp = body.get("sdp")

            if not offer_sdp:
                return JSONResponse(
                    {"error": "Missing SDP offer"},
                    status_code=400,
                )

            try:
                # Initialize pipeline if not already done
                if not self.pipeline:
                    self.pipeline = VoiceAgentPipeline(self.config)

                    # Set up transcript callback to broadcast to WebSocket clients
                    def on_transcript(event: TranscriptEvent):
                        asyncio.ensure_future(self._broadcast_transcript(event))

                    self.pipeline.on_transcript(on_transcript)

                    # Set up audio out callback
                    async def on_audio_out(audio: bytes):
                        if self.transport:
                            await self.transport.send_audio(audio)

                    self.pipeline.on_audio_out(on_audio_out)

                    await self.pipeline.initialize()

                # Create WebRTC transport
                self.transport = WebRTCTransport(
                    on_audio_chunk=self.pipeline.process_audio_chunk,
                )

                # Set up audio chunk callback
                async def on_audio_chunk(audio: bytes):
                    await self.pipeline.process_audio_chunk(audio)

                self.transport.on_audio_chunk = on_audio_chunk

                # Create answer
                answer_sdp = await self.transport.create_peer_connection(offer_sdp)

                return {
                    "sdp": answer_sdp,
                    "type": "answer",
                }

            except Exception as e:
                logger.error(f"WebRTC setup error: {e}", exc_info=True)
                return JSONResponse(
                    {"error": str(e)},
                    status_code=500,
                )

        @self.app.post("/api/session/end")
        async def end_session():
            """End the current agent session."""
            if self.transport:
                await self.transport.close()
                self.transport = None

            if self.pipeline:
                await self.pipeline.shutdown()
                self.pipeline = None

            return {"status": "ended"}

        @self.app.websocket("/ws/transcript")
        async def transcript_websocket(ws: WebSocket):
            """WebSocket endpoint for real-time transcript streaming."""
            await ws.accept()
            self._websocket_clients.append(ws)

            try:
                while True:
                    # Keep connection alive, receive any client messages
                    data = await ws.receive_text()
                    # Handle client commands
                    msg = json.loads(data) if data else {}

                    if msg.get("type") == "end_session":
                        if self.transport:
                            await self.transport.close()
                        if self.pipeline:
                            await self.pipeline.shutdown()

                    elif msg.get("type") == "barge_in":
                        if self.pipeline:
                            await self.pipeline.handle_interruption()

            except WebSocketDisconnect:
                self._websocket_clients.remove(ws)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if ws in self._websocket_clients:
                    self._websocket_clients.remove(ws)

        # Serve static frontend files
        web_dir = Path(__file__).parent.parent / "web" / "dist"
        if web_dir.exists():
            self.app.mount(
                "/",
                StaticFiles(directory=str(web_dir), html=True),
                name="frontend",
            )
            logger.info(f"Serving frontend from {web_dir}")
        else:
            # Fallback: serve a simple status page
            @self.app.get("/", response_class=HTMLResponse)
            async def index():
                return """
                <!DOCTYPE html>
                <html>
                <head><title>Voxatar</title></head>
                <body>
                    <h1>Voxatar Server</h1>
                    <p>Web frontend not built. Run <code>cd web && npm install && npm run build</code></p>
                    <p>API: <a href="/api/health">/api/health</a> | <a href="/api/agent">/api/agent</a></p>
                </body>
                </html>
                """

    async def _broadcast_transcript(self, event: TranscriptEvent) -> None:
        """Broadcast a transcript event to all WebSocket clients."""
        data = json.dumps({
            "type": "transcript",
            "event": {
                "type": event.type,
                "text": event.text,
                "timestamp": event.timestamp,
                "is_partial": event.is_partial,
            }
        })

        dead_clients = []
        for ws in self._websocket_clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead_clients.append(ws)

        for ws in dead_clients:
            if ws in self._websocket_clients:
                self._websocket_clients.remove(ws)

    def run(self, host: str, port: int) -> None:
        """Run the server using uvicorn."""
        import uvicorn
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
        )