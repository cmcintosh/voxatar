"""
WebSocket audio transport adapter for Voxatar.

Receives raw 16kHz 16-bit PCM mono directly from the browser's AudioWorklet.
No ffmpeg decoding needed for incoming audio — PCM goes straight to STT.

Outgoing TTS audio: EdgeTTS produces MP3 → ffmpeg decodes to PCM → sent as binary WS frames.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from voxatar.config import AgentConfig
from voxatar.pipeline import VoiceAgentPipeline, TranscriptEvent, SessionState

logger = logging.getLogger(__name__)


class WebSocketTransport:
    """WebSocket transport for real-time voice agent sessions."""

    def __init__(
        self,
        websocket: WebSocket,
        pipeline: Optional[VoiceAgentPipeline] = None,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.websocket = websocket
        self.pipeline = pipeline
        self.config = config

        self._session_active: bool = False
        self._is_muted: bool = False
        self._agent_speaking: bool = False

        # PCM accumulation buffer — raw 16-bit PCM from AudioWorklet
        self._pcm_buffer: bytearray = bytearray()
        self._pcm_buffer_max: int = 192_000  # ~6s of 16kHz 16-bit mono

        logger.debug(
            "WebSocketTransport created (agent=%s, voice=%s)",
            config.name if config else "unknown",
            config.voice_id if config else "default",
        )

    async def handle_session(self) -> None:
        """Main WebSocket session handler."""
        logger.info("WebSocket session starting…")

        await self.websocket.accept()
        self._session_active = True
        logger.info("WebSocket connection accepted from %s", self.websocket.client)

        self.set_pipeline_callbacks()
        await self.send_state("idle")

        try:
            self._receive_task = asyncio.create_task(self._receive_loop(), name="ws-receive")
            self._process_task = asyncio.create_task(self._process_loop(), name="ws-process")

            done, pending = await asyncio.wait(
                {self._receive_task, self._process_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                logger.debug("Cancelling remaining task: %s", task.get_name())
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected by client")
        except Exception as exc:
            logger.exception("Unexpected error in WebSocket session: %s", exc)
        finally:
            await self._cleanup()

    async def _receive_loop(self) -> None:
        """Receive loop: reads raw PCM binary frames and JSON commands."""
        logger.debug("Receive loop started")
        while self._session_active:
            try:
                message = await self.websocket.receive()
            except WebSocketDisconnect:
                logger.info("Client disconnected in receive loop")
                self._session_active = False
                break
            except Exception as exc:
                logger.exception("Error receiving from WebSocket: %s", exc)
                self._session_active = False
                break

            if "bytes" in message and message["bytes"] is not None:
                pcm_chunk: bytes = message["bytes"]
                logger.debug("Received PCM audio: %d bytes (%.1fms)", len(pcm_chunk), len(pcm_chunk) / 32.0)

                if self._is_muted:
                    continue

                # Accumulate raw PCM — no decoding needed!
                self._pcm_buffer.extend(pcm_chunk)
                if len(self._pcm_buffer) >= self._pcm_buffer_max:
                    await self._flush_pcm_buffer()

            elif "text" in message and message["text"] is not None:
                await self._handle_command(message["text"])
            else:
                logger.warning("Received unknown message format: %s", message)

        logger.debug("Receive loop ended")

    async def _handle_command(self, raw_text: str) -> None:
        """Parse and execute a JSON command from the browser."""
        try:
            cmd = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON command: %s → %s", raw_text, exc)
            return

        cmd_type = cmd.get("type", "")
        logger.info("Received command: %s", cmd_type)

        if cmd_type == "mute":
            self._is_muted = True
            await self.send_state("listening")
            logger.info("Microphone muted")

        elif cmd_type == "unmute":
            self._is_muted = False
            await self.send_state("listening")
            logger.info("Microphone unmuted")

        elif cmd_type == "barge_in":
            await self._handle_barge_in()

        elif cmd_type == "end_session":
            logger.info("End session requested by client")
            await self.send_state("ended")
            self._session_active = False

        elif cmd_type == "flush_audio":
            await self._flush_pcm_buffer()

        else:
            logger.warning("Unknown command type: %s", cmd_type)

    async def _process_loop(self) -> None:
        """Process loop: periodically flushes PCM buffer to the pipeline."""
        logger.debug("Process loop started")
        flush_interval: float = 0.5  # Check every 500ms

        while self._session_active:
            await asyncio.sleep(flush_interval)
            if len(self._pcm_buffer) > 3200:  # At least 100ms of audio
                await self._flush_pcm_buffer()

        logger.debug("Process loop ended")

    async def _flush_pcm_buffer(self) -> None:
        """Flush accumulated PCM to the pipeline for STT processing."""
        if len(self._pcm_buffer) == 0:
            return

        pcm_data = bytes(self._pcm_buffer)
        self._pcm_buffer.clear()

        logger.info(
            "[INFO] transport: Flushing PCM to pipeline — %d bytes (%.1fs)",
            len(pcm_data),
            len(pcm_data) / 32000.0,
        )

        # Check for barge-in during agent speech
        if self._agent_speaking:
            if self._detect_pcm_energy(pcm_data):
                await self._handle_barge_in()

        try:
            if self.pipeline:
                await self.pipeline.process_audio_chunk(pcm_data)
            else:
                logger.warning("No pipeline set — cannot process audio chunk")
        except Exception as exc:
            logger.exception("Pipeline processing error: %s", exc)

    async def _handle_barge_in(self) -> None:
        """Handle barge-in: stop agent TTS and transition to listening."""
        if not self._agent_speaking:
            return

        logger.info("Barge-in detected — stopping agent speech")
        self._agent_speaking = False
        self.pipeline.is_speaking = False
        self.pipeline._barge_in_event.set()
        await self.send_state("listening")

    async def decode_mp3_to_pcm(self, mp3_bytes: bytes) -> bytes:
        """Decode MP3 to 16kHz 16-bit PCM mono using ffmpeg."""
        if not mp3_bytes:
            return b""

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "mp3",
            "-i", "pipe:0",
            "-ar", "16000",
            "-ac", "1",
            "-f", "s16le",
            "pipe:1",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate(input=mp3_bytes)

            if process.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error("ffmpeg MP3 decode failed (exit %d): %s", process.returncode, err_msg)
                return b""

            logger.debug("ffmpeg decoded MP3: %d → %d bytes PCM", len(mp3_bytes), len(stdout))
            return stdout

        except Exception as exc:
            logger.exception("ffmpeg subprocess error: %s", exc)
            return b""

    async def send(self, message: str) -> None:
        """Send a raw text message to the browser."""
        try:
            try:
                data = json.loads(message)
                if data.get("type") == "state":
                    state = data.get("state", "")
                    if state in ("listening", "idle", "ended"):
                        self._agent_speaking = False
                    elif state == "speaking":
                        self._agent_speaking = True
            except (json.JSONDecodeError, KeyError):
                pass

            await self.websocket.send_text(message)
            logger.debug("Sent text: %s", message[:100])
        except Exception as exc:
            logger.warning("Failed to send message: %s", exc)

    async def send_state(self, state: str) -> None:
        """Send a state update to the browser."""
        if state in ("listening", "idle", "ended"):
            self._agent_speaking = False
        elif state == "speaking":
            self._agent_speaking = True

        message = json.dumps({"type": "state", "state": state})
        try:
            await self.websocket.send_text(message)
            logger.info("[INFO] transport: Sent state → %s", state)
        except Exception as exc:
            logger.warning("Failed to send state '%s': %s", state, exc)

    async def send_transcript(self, speaker: str, text: str, is_final: bool = True) -> None:
        """Send a transcript update to the browser."""
        message = json.dumps({
            "type": "transcript",
            "speaker": speaker,
            "text": text,
            "is_final": is_final,
            "timestamp": time.time(),
        })
        try:
            await self.websocket.send_text(message)
            logger.info("[INFO] transport: Sent transcript — speaker=%s, text=%s…", speaker, text[:60])
        except Exception as exc:
            logger.warning("Failed to send transcript: %s", exc)

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send raw PCM audio to the browser as a binary WebSocket frame."""
        if not pcm_bytes:
            return
        try:
            await self.websocket.send_bytes(pcm_bytes)
            logger.debug("Sent audio: %d bytes PCM", len(pcm_bytes))
        except Exception as exc:
            logger.warning("Failed to send audio: %s", exc)

    def set_pipeline_callbacks(self) -> None:
        """Wire up pipeline event callbacks to WebSocket send methods."""
        if not self.pipeline:
            logger.warning("Cannot set pipeline callbacks — no pipeline set")
            return

        async def _on_transcript(event: TranscriptEvent) -> None:
            await self.send_transcript(
                speaker=event.type,
                text=event.text,
                is_final=not event.is_partial,
            )

        async def _on_audio_out(mp3_bytes: bytes) -> None:
            """Receive MP3 TTS audio, decode to PCM, send to browser."""
            if not mp3_bytes:
                return
            try:
                pcm_data = await self.decode_mp3_to_pcm(mp3_bytes)
                if pcm_data:
                    await self.send_audio(pcm_data)
            except Exception as exc:
                logger.exception("Audio output error: %s", exc)

        self.pipeline.on_transcript(_on_transcript)
        self.pipeline.on_audio_out(_on_audio_out)
        logger.debug("Pipeline callbacks wired to WebSocket transport")

    @staticmethod
    def _detect_pcm_energy(pcm_bytes: bytes, threshold: float = 500.0) -> bool:
        """Quick energy check on PCM to detect speech."""
        if len(pcm_bytes) < 4:
            return False
        try:
            import array
            samples = array.array("h")
            samples.frombytes(pcm_bytes[: len(pcm_bytes) - (len(pcm_bytes) % 2)])
            if not samples:
                return False
            n = len(samples)
            sum_sq = sum(s * s for s in samples)
            rms = (sum_sq / n) ** 0.5
            return rms >= threshold
        except Exception:
            return False

    async def _cleanup(self) -> None:
        """Clean up resources and close the WebSocket."""
        self._session_active = False
        logger.info("WebSocket session cleanup")

        try:
            await self.websocket.close()
            logger.debug("WebSocket closed")
        except Exception as exc:
            logger.debug("WebSocket close error (expected): %s", exc)