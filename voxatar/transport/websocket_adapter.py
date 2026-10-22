"""
WebSocket audio transport adapter for Voxatar.

Replaces WebRTC as the primary transport for real-time voice communication
between the browser and the Voxatar pipeline. Handles:

- Binary audio reception (WebM/Opus from MediaRecorder)
- Audio decoding via ffmpeg subprocess (WebM → PCM, MP3 → PCM)
- Feeding decoded PCM to the VoiceAgentPipeline
- Sending TTS audio back to the browser as raw PCM
- Sending transcript and state updates as JSON text frames
- Barge-in handling (user interrupts agent speech)
- Command processing (mute, barge-in, end session)
"""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from voxatar.config import AgentConfig
from voxatar.pipeline import VoiceAgentPipeline, TranscriptEvent, SessionState

logger = logging.getLogger(__name__)


class WebSocketTransport:
    """
    WebSocket-based transport for real-time voice agent sessions.

    Audio flow::

        Browser (MediaRecorder)  ──WebM/Opus──►  WebSocket
            │                                          │
            │                                   decode_webm_to_pcm
            │                                          │
            │                                      PCM 16kHz
            │                                          │
            │                              pipeline.process_audio_chunk
            │                                          │
            │                                    STT → LLM → TTS
            │                                          │
            │                                   MP3 from EdgeTTS
            │                                          │
            │                                   decode_mp3_to_pcm
            │                                          │
            │                                      PCM 16kHz
            │                                          │
        Browser  ◄──raw PCM binary──  WebSocket  ◄──────┘
        Browser  ◄──JSON text──       WebSocket  (transcript / state)
    """

    def __init__(
        self,
        websocket: WebSocket,
        pipeline: Optional[VoiceAgentPipeline] = None,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.websocket = websocket
        self.pipeline = pipeline
        self.config = config

        # Session state
        self._session_active: bool = False
        self._is_muted: bool = False
        self._agent_speaking: bool = False
        self._barge_in_requested: bool = False

        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._process_task: Optional[asyncio.Task] = None

        # Buffer for accumulating WebM chunks before decode
        self._webm_buffer: bytearray = bytearray()
        self._webm_buffer_max: int = 192_000  # ~6s of WebM at 32 kbps

        logger.debug(
            "WebSocketTransport created (agent=%s, voice=%s)",
            config.name,
            config.voice_id or "default",
        )

    # ------------------------------------------------------------------ #
    # Main session loop
    # ------------------------------------------------------------------ #

    async def handle_session(self) -> None:
        """
        Main WebSocket session handler.

        Accepts the connection, wires up pipeline callbacks, and runs
        concurrent receive/process loops until the client disconnects
        or the session ends.
        """
        logger.info("WebSocket session starting…")

        # 1. Accept the WebSocket connection
        await self.websocket.accept()
        self._session_active = True
        logger.info("WebSocket connection accepted from %s", self.websocket.client)

        # 2. Wire up pipeline callbacks so transcript/audio events
        #    are forwarded to the browser automatically.
        self.set_pipeline_callbacks()

        # 3. Send initial idle state
        await self.send_state("idle")

        # 4. Launch concurrent tasks
        try:
            self._receive_task = asyncio.create_task(
                self._receive_loop(), name="ws-receive"
            )
            self._process_task = asyncio.create_task(
                self._process_loop(), name="ws-process"
            )

            # Wait for either task to complete (or raise)
            done, pending = await asyncio.wait(
                {self._receive_task, self._process_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel any still-running task
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

    # ------------------------------------------------------------------ #
    # Receive loop — handles incoming messages from the browser
    # ------------------------------------------------------------------ #

    async def _receive_loop(self) -> None:
        """
        Receive loop: reads messages from the WebSocket.

        Binary messages → WebM audio chunks → enqueued for processing.
        Text messages   → JSON commands → handled immediately.
        """
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

            # Determine message type
            if "bytes" in message and message["bytes"] is not None:
                # Binary audio chunk (WebM/Opus)
                webm_chunk: bytes = message["bytes"]
                logger.debug(
                    "Received binary audio: %d bytes", len(webm_chunk)
                )

                if self._is_muted:
                    logger.debug("Ignoring audio chunk (muted)")
                    continue

                # Accumulate WebM data for batch decoding
                self._webm_buffer.extend(webm_chunk)
                if len(self._webm_buffer) >= self._webm_buffer_max:
                    logger.debug(
                        "WebM buffer flush: %d bytes", len(self._webm_buffer)
                    )
                    await self._flush_webm_buffer()

            elif "text" in message and message["text"] is not None:
                # JSON command message
                await self._handle_command(message["text"])

            else:
                logger.warning("Received unknown message format: %s", message)

        logger.debug("Receive loop ended")

    async def _handle_command(self, raw_text: str) -> None:
        """
        Parse and execute a JSON command from the browser.

        Supported commands:
        - ``{"type": "mute"}`` / ``{"type": "unmute"}``
        - ``{"type": "barge_in"}``
        - ``{"type": "end_session"}``
        - ``{"type": "flush_audio"}`` — flush accumulated WebM buffer
        """
        try:
            cmd = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON command: %s → %s", raw_text, exc)
            return

        cmd_type = cmd.get("type", "")
        logger.info("Received command: %s", cmd_type)

        if cmd_type == "mute":
            self._is_muted = True
            await self.send_state("listening_muted")
            logger.info("Microphone muted")

        elif cmd_type == "unmute":
            self._is_muted = False
            await self.send_state("listening")
            logger.info("Microphone unmuted")

        elif cmd_type == "barge_in":
            await self._handle_barge_in()
            logger.info("Barge-in requested by client")

        elif cmd_type == "end_session":
            logger.info("End session requested by client")
            await self.send_state("ended")
            self._session_active = False

        elif cmd_type == "flush_audio":
            await self._flush_webm_buffer()

        else:
            logger.warning("Unknown command type: %s", cmd_type)

    # ------------------------------------------------------------------ #
    # Process loop — decodes WebM and feeds pipeline
    # ------------------------------------------------------------------ #

    async def _process_loop(self) -> None:
        """
        Processing loop: periodically flushes the WebM buffer,
        decodes to PCM, and feeds chunks to the pipeline.
        """
        logger.debug("Process loop started")
        flush_interval: float = 0.3  # seconds between flushes

        while self._session_active:
            await asyncio.sleep(flush_interval)

            if len(self._webm_buffer) > 0:
                await self._flush_webm_buffer()

        logger.debug("Process loop ended")

    async def _flush_webm_buffer(self) -> None:
        """Flush the accumulated WebM buffer through the decode → pipeline path."""
        if len(self._webm_buffer) == 0:
            return

        webm_data = bytes(self._webm_buffer)
        self._webm_buffer.clear()

        try:
            pcm_data = await self.decode_webm_to_pcm(webm_data)
        except Exception as exc:
            logger.error("WebM decode failed: %s", exc)
            return

        if pcm_data:
            logger.debug(
                "Decoded %d bytes WebM → %d bytes PCM", len(webm_data), len(pcm_data)
            )

            # Check for barge-in during agent speech
            if self._agent_speaking:
                # Simple energy check on the PCM to see if user is talking
                if self._detect_pcm_energy(pcm_data):
                    await self._handle_barge_in()

            # Feed to pipeline
            try:
                if self.pipeline:
                    await self.pipeline.process_audio_chunk(pcm_data)
                else:
                    logger.warning("No pipeline set — cannot process audio chunk")
            except Exception as exc:
                logger.exception("Pipeline processing error: %s", exc)

    # ------------------------------------------------------------------ #
    # Barge-in handling
    # ------------------------------------------------------------------ #

    async def _handle_barge_in(self) -> None:
        """
        Handle barge-in: stop agent TTS playback and transition to listening.

        Called when the user starts speaking while the agent is talking.
        """
        if not self._agent_speaking:
            logger.debug("Barge-in ignored — agent not speaking")
            return

        logger.info("Barge-in detected — stopping agent speech")
        self._barge_in_requested = True
        self._agent_speaking = False

        # Signal the pipeline to stop TTS
        self.pipeline.is_speaking = False
        self.pipeline._barge_in_event.set()

        # Notify the browser
        await self.send_state("listening")
        self._barge_in_requested = False

    # ------------------------------------------------------------------ #
    # Audio decoding
    # ------------------------------------------------------------------ #

    async def decode_webm_to_pcm(self, webm_bytes: bytes) -> bytes:
        """
        Decode WebM/Opus audio to 16 kHz 16-bit signed PCM mono using ffmpeg.

        Parameters
        ----------
        webm_bytes : bytes
            WebM container with Opus audio (as produced by MediaRecorder).

        Returns
        -------
        bytes
            Raw 16-bit signed little-endian PCM at 16 kHz mono.
        """
        return await self._ffmpeg_decode(
            webm_bytes,
            input_format="webm",
            codec="libopus",
        )

    async def decode_mp3_to_pcm(self, mp3_bytes: bytes) -> bytes:
        """
        Decode MP3 audio to 16 kHz 16-bit signed PCM mono using ffmpeg.

        Used to convert EdgeTTS MP3 output to raw PCM before sending
        to the browser.

        Parameters
        ----------
        mp3_bytes : bytes
            MP3 audio data (as produced by Edge TTS).

        Returns
        -------
        bytes
            Raw 16-bit signed little-endian PCM at 16 kHz mono.
        """
        return await self._ffmpeg_decode(
            mp3_bytes,
            input_format="mp3",
            codec=None,  # ffmpeg auto-detects MP3
        )

    async def _ffmpeg_decode(
        self,
        audio_bytes: bytes,
        input_format: str,
        codec: Optional[str] = None,
    ) -> bytes:
        """
        Generic ffmpeg-based audio decoder.

        Runs ffmpeg as a subprocess, piping raw audio bytes to stdin
        and reading decoded PCM from stdout.

        Parameters
        ----------
        audio_bytes : bytes
            Input audio data to decode.
        input_format : str
            ffmpeg input format specifier (e.g. ``"webm"``, ``"mp3"``).
        codec : str or None
            Optional input codec override (e.g. ``"libopus"``).

        Returns
        -------
        bytes
            Decoded 16 kHz 16-bit signed PCM mono.
        """
        if not audio_bytes:
            logger.debug("Empty audio buffer, skipping decode")
            return b""

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", input_format,
        ]
        if codec:
            cmd.extend(["-acodec", codec])
        cmd.extend([
            "-i", "pipe:0",           # read from stdin
            "-ar", "16000",           # 16 kHz sample rate
            "-ac", "1",               # mono
            "-f", "s16le",            # 16-bit signed little-endian PCM
            "pipe:1",                 # write to stdout
        ])

        logger.debug(
            "ffmpeg decode: format=%s, codec=%s, input=%d bytes",
            input_format,
            codec or "auto",
            len(audio_bytes),
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate(input=audio_bytes)

            if process.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error(
                    "ffmpeg failed (exit %d): %s", process.returncode, err_msg
                )
                return b""

            logger.debug(
                "ffmpeg decoded %d bytes → %d bytes PCM",
                len(audio_bytes),
                len(stdout),
            )
            return stdout

        except FileNotFoundError:
            logger.error(
                "ffmpeg not found — ensure ffmpeg is installed and on PATH"
            )
            return b""
        except Exception as exc:
            logger.exception("ffmpeg subprocess error: %s", exc)
            return b""

    # ------------------------------------------------------------------ #
    # Sending helpers
    # ------------------------------------------------------------------ #

    async def send(self, message: str) -> None:
        """
        Send a raw text message to the browser.

        This is a generic send method used by the pipeline for
        state updates and JSON messages.
        """
        try:
            # Parse JSON to check if it's a state update for internal tracking
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
        """
        Send a state update to the browser as a JSON text frame.

        Also updates internal flags based on the state.

        Parameters
        ----------
        state : str
            The new session state (e.g. ``"idle"``, ``"listening"``,
            ``"thinking"``, ``"speaking"``, ``"ended"``).
        """
        # Update internal flags based on state
        if state in ("listening", "idle", "ended"):
            self._agent_speaking = False
        elif state == "speaking":
            self._agent_speaking = True

        message = json.dumps({"type": "state", "state": state})
        try:
            await self.websocket.send_text(message)
            logger.debug("Sent state: %s", state)
        except Exception as exc:
            logger.warning("Failed to send state '%s': %s", state, exc)

    async def send_transcript(
        self,
        speaker: str,
        text: str,
        is_final: bool = True,
    ) -> None:
        """
        Send a transcript update to the browser as a JSON text frame.

        Parameters
        ----------
        speaker : str
            Who produced the text: ``"user"``, ``"agent"``, or ``"system"``.
        text : str
            The transcript text.
        is_final : bool
            Whether this is a final transcript (vs. partial/interim).
        """
        message = json.dumps({
            "type": "transcript",
            "speaker": speaker,
            "text": text,
            "is_final": is_final,
            "timestamp": time.time(),
        })
        try:
            await self.websocket.send_text(message)
            logger.debug(
                "Sent transcript: speaker=%s, final=%s, text=%s…",
                speaker,
                is_final,
                text[:60],
            )
        except Exception as exc:
            logger.warning("Failed to send transcript: %s", exc)

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """
        Send raw PCM audio to the browser as a binary WebSocket frame.

        The audio must be 16 kHz 16-bit signed little-endian mono PCM.
        The browser plays it back via an AudioContext / ScriptProcessorNode.

        Parameters
        ----------
        pcm_bytes : bytes
            Raw 16-bit PCM audio data to send.
        """
        if not pcm_bytes:
            return
        try:
            await self.websocket.send_bytes(pcm_bytes)
            logger.debug("Sent audio: %d bytes PCM", len(pcm_bytes))
        except Exception as exc:
            logger.warning("Failed to send audio: %s", exc)

    # ------------------------------------------------------------------ #
    # Pipeline callback wiring
    # ------------------------------------------------------------------ #

    def set_pipeline_callbacks(self) -> None:
        """
        Wire up pipeline event callbacks to WebSocket send methods.

        - ``pipeline.on_transcript`` → :meth:`send_transcript`
        - ``pipeline.on_audio_out``  → TTS MP3 decode + :meth:`send_audio`
        """
        if not self.pipeline:
            logger.warning("Cannot set pipeline callbacks — no pipeline set")
            return

        async def _on_transcript(event: TranscriptEvent) -> None:
            """Forward pipeline transcript events to the browser."""
            await self.send_transcript(
                speaker=event.type,
                text=event.text,
                is_final=not event.is_partial,
            )

        async def _on_audio_out(mp3_bytes: bytes) -> None:
            """
            Receive MP3 TTS audio from the pipeline, decode to PCM,
            and send to the browser.
            """
            if not mp3_bytes:
                return

            try:
                pcm_data = await self.decode_mp3_to_pcm(mp3_bytes)
                if pcm_data:
                    await self.send_audio(pcm_data)
            except Exception as exc:
                logger.exception("Audio output error: %s", exc)

        # Register callbacks on the pipeline
        self.pipeline.on_transcript(_on_transcript)
        self.pipeline.on_audio_out(_on_audio_out)

        logger.debug("Pipeline callbacks wired to WebSocket transport")

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _detect_pcm_energy(pcm_bytes: bytes, threshold: float = 500.0) -> bool:
        """
        Quick energy check on a PCM chunk to detect speech.

        Uses a simple RMS calculation without numpy to avoid import
        overhead in hot paths. Falls back to ``False`` on any error.

        Parameters
        ----------
        pcm_bytes : bytes
            Raw 16-bit PCM audio.
        threshold : float
            RMS energy threshold for speech detection.

        Returns
        -------
        bool
            ``True`` if the chunk likely contains speech.
        """
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

    # ------------------------------------------------------------------ #
    # Cleanup
    # ------------------------------------------------------------------ #

    async def _cleanup(self) -> None:
        """Clean up resources and close the WebSocket."""
        self._session_active = False
        logger.info("WebSocket session cleanup")

        # Cancel tasks if still running
        for task in (self._receive_task, self._process_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close the WebSocket
        try:
            await self.websocket.close()
            logger.debug("WebSocket closed")
        except Exception as exc:
            logger.debug("WebSocket close error (expected): %s", exc)