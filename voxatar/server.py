"""
FastAPI server for Voxatar.

Provides:
- WebRTC signaling endpoint (/api/webrtc/offer)
- Agent configuration endpoint (/api/agent)
- WebSocket endpoint for transcript streaming (/ws/transcript)
- Static file serving for the web frontend
- Health check endpoint
- Post-call API endpoints (/api/calls, /api/calls/{id}, etc.)
- Knowledge base endpoints (/api/knowledge/upload, etc.)
- Shareable agent links (/c/{agent_slug})
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import yaml
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Request,
    UploadFile,
    File,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
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
    - Call history API
    - Knowledge base API
    - Shareable agent links
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.app = FastAPI(
            title="Voxatar",
            description="Open-source AI voice agent server",
            version="0.1.5",
        )
        self.pipeline: Optional[VoiceAgentPipeline] = None
        self.transport: Optional[WebRTCTransport] = None
        self._websocket_clients: list[WebSocket] = []

        # Phase 1.5 — Initialize database
        self.database = None
        try:
            from voxatar.storage.database import CallDatabase
            self.database = CallDatabase()
        except ImportError:
            logger.warning("CallDatabase not available — call history disabled")

        # Phase 1.5 — Initialize knowledge base manager
        self.kb_manager = None
        try:
            from voxatar.knowledge.rag import RAGPipeline
            from voxatar.knowledge.manager import KnowledgeBaseManager
            rag = RAGPipeline(
                persist_dir=config.knowledge_persist_dir,
                ollama_url=config.knowledge_ollama_url,
            )
            self.kb_manager = KnowledgeBaseManager(
                rag=rag,
                storage_dir=config.knowledge_documents_dir,
            )
        except ImportError:
            logger.warning("KnowledgeBase not available — RAG disabled")

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

        # ─── Health & Agent Info ───────────────────────────────────────

        @self.app.get("/api/health")
        async def health():
            """Health check endpoint."""
            return {
                "status": "ok",
                "agent": self.config.name,
                "state": self.pipeline.state.value if self.pipeline else "uninitialized",
                "version": "0.1.5",
                "features": {
                    "database": self.database is not None,
                    "knowledge_base": self.kb_manager is not None,
                    "flow_manager": bool(self.config.objectives),
                },
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
                "flow_mode": self.config.flow_mode,
                "available_voices": self.tts.list_voices() if self.tts else [],
            }

        # ─── WebRTC & Session ──────────────────────────────────────────

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
                if ws in self._websocket_clients:
                    self._websocket_clients.remove(ws)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if ws in self._websocket_clients:
                    self._websocket_clients.remove(ws)

        # ─── Call History API (Phase 1.5) ─────────────────────────────

        @self.app.get("/api/calls")
        async def list_calls(limit: int = 50, offset: int = 0):
            """List all past calls."""
            if not self.database:
                raise HTTPException(status_code=503, detail="Database not available")
            calls = self.database.get_calls(limit=limit, offset=offset)
            return {"calls": calls, "total": len(calls)}

        @self.app.get("/api/calls/{call_id}")
        async def get_call(call_id: str):
            """Get a specific call record."""
            if not self.database:
                raise HTTPException(status_code=503, detail="Database not available")
            call = self.database.get_call(call_id)
            if not call:
                raise HTTPException(status_code=404, detail="Call not found")
            action_items = self.database.get_action_items(call_id)
            scorecard = self.database.get_scorecard(call_id)
            return {
                "call": call,
                "action_items": action_items,
                "scorecard": scorecard,
            }

        @self.app.get("/api/calls/{call_id}/transcript")
        async def get_call_transcript(call_id: str):
            """Get the full transcript for a call."""
            if not self.database:
                raise HTTPException(status_code=503, detail="Database not available")
            transcript = self.database.get_transcript(call_id)
            return {"call_id": call_id, "transcript": transcript}

        @self.app.delete("/api/calls/{call_id}")
        async def delete_call(call_id: str):
            """Delete a call record."""
            if not self.database:
                raise HTTPException(status_code=503, detail="Database not available")
            deleted = self.database.delete_call(call_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Call not found")
            return {"status": "deleted", "call_id": call_id}

        @self.app.post("/api/calls/{call_id}/export")
        async def export_call(call_id: str, request: Request):
            """Export a call as markdown or JSON."""
            if not self.database:
                raise HTTPException(status_code=503, detail="Database not available")

            body = await request.json() if request.headers.get("content-type") == "application/json" else {}
            fmt = body.get("format", "markdown")

            call = self.database.get_call(call_id)
            if not call:
                raise HTTPException(status_code=404, detail="Call not found")

            transcript = self.database.get_transcript(call_id)
            action_items = self.database.get_action_items(call_id)
            scorecard = self.database.get_scorecard(call_id)

            if fmt == "json":
                export_data = {
                    "call": call,
                    "transcript": transcript,
                    "action_items": action_items,
                    "scorecard": scorecard,
                }
                return PlainTextResponse(
                    content=json.dumps(export_data, indent=2),
                    media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=call-{call_id}.json"},
                )
            else:
                # Markdown export
                md_lines = [
                    f"# Call Report: {call.get('agent_name', 'Unknown')}",
                    "",
                    f"**Date:** {call.get('start_time', 'N/A')}",
                    f"**Duration:** {call.get('duration', 0):.1f}s",
                    f"**Status:** {call.get('status', 'N/A')}",
                    "",
                    "## Summary",
                    "",
                    call.get("summary", "No summary available."),
                    "",
                    "## Transcript",
                    "",
                ]
                for entry in transcript:
                    ts = entry.get("timestamp", 0)
                    speaker = entry.get("speaker", "unknown")
                    text = entry.get("text", "")
                    md_lines.append(f"**[{speaker}]** ({ts}): {text}")
                    md_lines.append("")

                if action_items:
                    md_lines.append("## Action Items")
                    md_lines.append("")
                    for item in action_items:
                        status_badge = f" [{item.get('status', 'open')}]"
                        assignee = f" — *{item.get('assignee', 'Unassigned')}*" if item.get("assignee") else ""
                        due = f" (due: {item.get('due_date')})" if item.get("due_date") else ""
                        md_lines.append(f"- {item.get('task', '')}{status_badge}{assignee}{due}")
                    md_lines.append("")

                if scorecard:
                    md_lines.append("## Scorecard")
                    md_lines.append("")
                    md_lines.append("| Objective | Status | Notes |")
                    md_lines.append("|-----------|--------|-------|")
                    for entry in scorecard:
                        md_lines.append(
                            f"| {entry.get('objective', '')} | {entry.get('status', '')} | {entry.get('notes', '')} |"
                        )
                    md_lines.append("")

                markdown = "\n".join(md_lines)
                return PlainTextResponse(
                    content=markdown,
                    media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=call-{call_id}.md"},
                )

        # ─── Knowledge Base API (Phase 1.5) ───────────────────────────

        @self.app.post("/api/knowledge/upload")
        async def upload_document(file: UploadFile = File(...)):
            """Upload a document to the knowledge base."""
            if not self.kb_manager:
                raise HTTPException(status_code=503, detail="Knowledge base not available")

            content = await file.read()
            content_type = file.content_type or "application/octet-stream"
            filename = file.filename or "uploaded_document"

            try:
                result = await self.kb_manager.upload_document(
                    filename=filename,
                    content=content,
                    content_type=content_type,
                )
                return result
            except Exception as e:
                logger.error(f"Document upload failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/knowledge/documents")
        async def list_documents():
            """List all documents in the knowledge base."""
            if not self.kb_manager:
                raise HTTPException(status_code=503, detail="Knowledge base not available")
            return {"documents": self.kb_manager.list_documents()}

        @self.app.delete("/api/knowledge/documents/{doc_id}")
        async def delete_document(doc_id: str):
            """Delete a document from the knowledge base."""
            if not self.kb_manager:
                raise HTTPException(status_code=503, detail="Knowledge base not available")
            deleted = self.kb_manager.delete_document(doc_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Document not found")
            return {"status": "deleted", "doc_id": doc_id}

        # ─── Shareable Agent Links (Phase 1.5) ────────────────────────

        @self.app.get("/api/agents")
        async def list_agents():
            """List all available agent configurations."""
            agents_dir = Path(self.config.agents_dir)
            if not agents_dir.exists():
                return {"agents": []}

            agents = []
            for yaml_file in agents_dir.glob("*.yaml"):
                try:
                    with open(yaml_file) as f:
                        data = yaml.safe_load(f)
                    if data:
                        slug = yaml_file.stem
                        agents.append({
                            "slug": slug,
                            "name": data.get("name", slug),
                            "role": data.get("role", ""),
                            "organization": data.get("organization", ""),
                        })
                except Exception as e:
                    logger.warning(f"Failed to parse agent config {yaml_file}: {e}")

            return {"agents": agents}

        @self.app.get("/api/agents/{slug}")
        async def get_agent_by_slug(slug: str):
            """Get agent configuration by URL slug."""
            # Security: only allow alphanumeric, hyphens, underscores
            if not slug.replace("-", "").replace("_", "").isalnum():
                raise HTTPException(status_code=400, detail="Invalid agent slug")

            agents_dir = Path(self.config.agents_dir)
            yaml_file = agents_dir / f"{slug}.yaml"

            if not yaml_file.exists():
                raise HTTPException(status_code=404, detail="Agent not found")

            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                return data
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # ─── Static Frontend Serving ──────────────────────────────────

        web_dir = Path(__file__).parent.parent / "web" / "dist"
        if web_dir.exists():
            # Serve frontend assets
            self.app.mount(
                "/assets",
                StaticFiles(directory=str(web_dir / "assets")),
                name="frontend-assets",
            )

            # SPA fallback: serve index.html for all non-API routes
            @self.app.get("/{path:path}", response_class=HTMLResponse)
            async def spa_fallback(path: str):
                """Serve the React SPA for all non-API routes."""
                # Skip API and WebSocket routes
                if path.startswith("api/") or path.startswith("ws/"):
                    raise HTTPException(status_code=404)

                # Check for specific static files
                file_path = web_dir / path
                if file_path.exists() and file_path.is_file():
                    return FileResponse(str(file_path))

                # Return index.html for SPA routing
                index_path = web_dir / "index.html"
                if index_path.exists():
                    return HTMLResponse(index_path.read_text())

                raise HTTPException(status_code=404, detail="Not found")

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