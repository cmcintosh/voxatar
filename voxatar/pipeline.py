"""
Pipeline orchestration for Voxatar voice agents.

Wires together STT → LLM → TTS components into a real-time conversation pipeline.
Handles:
- Audio reception from WebRTC transport
- STT transcription with VAD
- LLM response generation with streaming
- TTS audio synthesis
- Barge-in (interruption) handling
- Conversation history management
- Transcript events for the frontend
- Conversation flow management (Phase 1.5)
- Real-time SQLite persistence (Phase 1.5)
- RAG context injection (Phase 1.5)
- Post-call processing (Phase 1.5)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Callable, Optional

from voxatar.config import AgentConfig
from voxatar.llm import Message
from voxatar.llm.ollama_adapter import OllamaLLM
from voxatar.stt.whisper_adapter import WhisperSTT
from voxatar.tts.edge_tts_adapter import EdgeTTS
from voxatar.vad import EnergyVAD

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """State of a voice agent session."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ENDED = "ended"


@dataclass
class TranscriptEvent:
    """A transcript event to send to the frontend."""
    type: str  # "user", "agent", "system"
    text: str
    timestamp: float = field(default_factory=time.time)
    is_partial: bool = False


class VoiceAgentPipeline:
    """
    Main orchestration pipeline for a voice agent session.

    Audio flow:
        Browser → WebRTC → STT → LLM → TTS → WebRTC → Browser

    The pipeline runs as a set of async tasks that communicate via queues.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.stt: Optional[WhisperSTT] = None
        self.llm: Optional[OllamaLLM] = None
        self.tts: Optional[EdgeTTS] = None
        self.conversation_history: list[Message] = []
        self.state = SessionState.IDLE
        self.is_speaking = False
        self.is_listening = True
        self._audio_in_queue: asyncio.Queue = asyncio.Queue()
        self._transcript_callbacks: list[Callable] = []
        self._audio_out_callback: Optional[Callable] = None
        self._websocket_transport = None  # WebSocket transport for state updates
        self._audio_loop_task = None  # Reference to the audio loop task
        self._session_start: Optional[float] = None
        self._barge_in_event = asyncio.Event()
        self._vad = EnergyVAD()  # Energy-based VAD for speech detection

        # Phase 1.5 — Conversation flow manager
        self.flow_manager: Optional[FlowManager] = None
        try:
            from voxatar.flow.manager import FlowManager
            if config.objectives:
                self.flow_manager = FlowManager(
                    objectives=config.objectives,
                    mode=config.flow_mode,
                )
        except ImportError:
            logger.warning("FlowManager not available — flow guidance disabled")

        # Phase 1.5 — Knowledge base / RAG
        self.rag_pipeline: Optional[RAGPipeline] = None
        try:
            from voxatar.knowledge.rag import RAGPipeline
            self.rag_pipeline = RAGPipeline(
                persist_dir=config.knowledge_persist_dir,
                ollama_url=config.knowledge_ollama_url,
            )
        except ImportError:
            logger.warning("RAGPipeline not available — knowledge base disabled")

        # Phase 1.5 — SQLite persistence
        self.database: Optional[CallDatabase] = None
        try:
            from voxatar.storage.database import CallDatabase
            self.database = CallDatabase()
        except ImportError:
            logger.warning("CallDatabase not available — persistence disabled")

        # Phase 1.5 — Call ID for persistence
        self.call_id: str = str(uuid.uuid4())

    async def initialize(self) -> None:
        """Initialize all pipeline components."""
        logger.info(f"Initializing pipeline for agent: {self.config.name}")
        logger.info(f"  STT: whisper ({self.config.stt_model})")
        logger.info(f"  LLM: ollama ({self.config.llm_model})")
        logger.info(f"  TTS: edge-tts")
        if self.flow_manager:
            logger.info(f"  Flow: {self.config.flow_mode} mode, {len(self.config.objectives)} objectives")
        if self.rag_pipeline:
            logger.info(f"  RAG: enabled (chromadb at {self.config.knowledge_persist_dir})")
        if self.database:
            logger.info(f"  Persistence: SQLite at {self.database.db_path}")

        # Initialize STT
        self.stt = WhisperSTT(
            model_size=self.config.stt_model,
            device=self.config.stt_device,
            compute_type=self.config.stt_compute_type,
            language=self.config.stt_language,
        )
        await self.stt.initialize()

        # Initialize LLM
        self.llm = OllamaLLM(
            model=self.config.llm_model,
            base_url=self.config.llm_base_url,
        )

        # Initialize TTS
        self.tts = EdgeTTS(
            voice=self.config.voice_id,
            language=self.config.language,
        )

        # Build initial system prompt
        if not self.config.system_prompt:
            self.config.system_prompt = self._build_default_system_prompt()

        # Add consent message as first system message if required
        if self.config.require_consent:
            self._emit_transcript("system", self.config.consent_message)

        self._session_start = time.time()
        logger.info(f"[INFO] pipeline: State transition: {self.state.value} → {SessionState.LISTENING.value}")
        self.state = SessionState.LISTENING

        # Phase 1.5 — Create call record in database
        if self.database:
            try:
                self.database.create_call(
                    call_id=self.call_id,
                    agent_name=self.config.name,
                    start_time=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self._session_start)),
                )
            except Exception as e:
                logger.error(f"Failed to create call record: {e}")

        logger.info("Pipeline initialized — ready for conversation")

    def on_transcript(self, callback: Callable[[TranscriptEvent], None]) -> None:
        """Register a callback for transcript events."""
        self._transcript_callbacks.append(callback)

    def on_audio_out(self, callback: Callable[[bytes], None]) -> None:
        """Register a callback for outbound audio."""
        self._audio_out_callback = callback

    def set_websocket_transport(self, transport) -> None:
        """Set a WebSocket transport for sending state updates and transcripts."""
        self._websocket_transport = transport

    async def _send_ws_state(self, state: str) -> None:
        """Send a state update via the websocket transport if set."""
        if self._websocket_transport:
            try:
                msg = json.dumps({"type": "state", "state": state})
                await self._websocket_transport.send(msg)
            except Exception as e:
                logger.warning(f"Failed to send ws state update: {e}")

    async def _send_ws_json(self, data: dict) -> None:
        """Send a JSON message via the websocket transport if set."""
        if self._websocket_transport:
            try:
                await self._websocket_transport.send(json.dumps(data))
            except Exception as e:
                logger.warning(f"Failed to send ws message: {e}")

    async def process_audio_chunk(self, audio: bytes) -> None:
        """Feed an audio chunk into the pipeline."""
        await self._audio_in_queue.put(audio)

    async def process_user_text(self, text: str) -> None:
        """
        Process a user text message directly (bypassing STT).
        Useful for testing or text-only input.
        """
        if not text.strip():
            return

        logger.info(f"User said: {text}")
        self._emit_transcript("user", text)
        self.conversation_history.append(Message(role="user", content=text))

        # Phase 1.5 — Save transcript entry to database
        self._save_transcript("user", text)

        # Generate and speak the response
        await self._generate_and_speak()

    async def run(self) -> None:
        """Run the agent session — process audio from the input queue."""
        await self.initialize()

        # Start the audio processing loop
        asyncio.ensure_future(self._audio_loop())

        logger.info("Agent session started")

    async def _audio_loop(self) -> None:
        """Main audio processing loop."""
        audio_buffer = bytearray()

        while self.state != SessionState.ENDED:
            try:
                # Get audio chunk with timeout
                chunk = await asyncio.wait_for(
                    self._audio_in_queue.get(),
                    timeout=1.0,
                )

                audio_buffer.extend(chunk)

                # Process when we have ~2 seconds of audio (64KB at 16kHz 16-bit mono)
                if len(audio_buffer) >= 64000:
                    await self._process_utterance(bytes(audio_buffer))
                    audio_buffer = bytearray()

            except asyncio.TimeoutError:
                # Process any remaining audio
                if len(audio_buffer) > 3200:  # At least 100ms
                    await self._process_utterance(bytes(audio_buffer))
                    audio_buffer = bytearray()
            except Exception as e:
                logger.error(f"Audio loop error: {e}")

    async def _process_utterance(self, audio: bytes) -> None:
        """Process a complete utterance: STT → LLM → TTS."""
        chunk_size = len(audio)
        logger.info(f"[INFO] pipeline: Audio chunk received — size={chunk_size} bytes ({chunk_size / 32000:.1f}s)")

        if self.is_speaking:
            # Barge-in: stop current speech
            logger.info("[INFO] pipeline: Barge-in detected — interrupting agent")
            self._barge_in_event.set()
            await asyncio.sleep(0.1)  # Let the barge-in propagate
            self._barge_in_event.clear()

        if not self.stt:
            return

        # VAD check — skip STT if no speech detected
        vad_has_speech = self._vad.is_speech(audio)
        logger.info(f"[INFO] pipeline: VAD result — has_speech={vad_has_speech}")
        if not vad_has_speech:
            logger.info("[INFO] pipeline: No speech detected by VAD — skipping STT")
            return

        # Transcribe with timing
        self.state = SessionState.LISTENING
        stt_start = time.time()
        text = await self.stt.transcribe(audio)
        stt_latency = time.time() - stt_start
        logger.info(f"[INFO] pipeline: STT latency={stt_latency:.3f}s — text=\"{text.strip()[:100]}\"")

        if not text.strip():
            logger.info("[INFO] pipeline: STT returned empty text — skipping")
            return

        logger.info(f"[INFO] pipeline: Transcribed: {text}")
        self._emit_transcript("user", text)
        self.conversation_history.append(Message(role="user", content=text))

        # Phase 1.5 — Save transcript entry to database
        self._save_transcript("user", text)

        # Generate and speak response
        await self._generate_and_speak()

    async def _generate_and_speak(self) -> None:
        """Generate LLM response and synthesize speech."""
        logger.info(f"[INFO] pipeline: State transition: {self.state.value} → {SessionState.THINKING.value}")
        self.state = SessionState.THINKING
        self.is_speaking = True
        await self._send_ws_state("thinking")

        try:
            # Phase 1.5 — Build dynamic system prompt with flow guidance and RAG context
            system_prompt = self.config.system_prompt
            knowledge_context = None

            # Add flow guidance
            if self.flow_manager:
                flow_guidance = self.flow_manager.get_flow_guidance()
                if flow_guidance:
                    system_prompt = system_prompt + "\n\n" + flow_guidance

            # Add RAG context from last user message
            if self.rag_pipeline and self.conversation_history:
                last_user_msg = self.conversation_history[-1].content
                try:
                    knowledge_context = await self.rag_pipeline.get_context_for_prompt(last_user_msg)
                except Exception as e:
                    logger.warning(f"RAG retrieval failed: {e}")
                    knowledge_context = None

            # Stream LLM response with timing
            response_text = ""
            text_chunks = []
            llm_start = time.time()
            logger.info(f"[INFO] pipeline: LLM request — model={self.config.llm_model}")

            async for token in self.llm.generate_stream(
                messages=self.conversation_history,
                system_prompt=system_prompt,
                knowledge_context=knowledge_context,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            ):
                if self._barge_in_event.is_set():
                    logger.info("LLM generation interrupted by barge-in")
                    break

                response_text += token
                text_chunks.append(token)

            response_text = response_text.strip()
            llm_latency = time.time() - llm_start
            logger.info(f"[INFO] pipeline: LLM latency={llm_latency:.3f}s — model={self.config.llm_model} — response=\"{response_text[:100]}\"")

            if response_text:
            logger.info(f"[INFO] pipeline: Agent response: {response_text}")
            self._emit_transcript("agent", response_text)
            self.conversation_history.append(
                Message(role="assistant", content=response_text)
            )

            # Phase 1.5 — Save transcript entry to database
            self._save_transcript("agent", response_text)

            # Phase 1.5 — Update flow manager
            if self.flow_manager and self.conversation_history:
                last_user = self.conversation_history[-2].content if len(self.conversation_history) >= 2 else ""
                self.flow_manager.update(last_user, response_text)

            # Synthesize speech with timing
            logger.info(f"[INFO] pipeline: State transition: {self.state.value} → {SessionState.SPEAKING.value}")
            self.state = SessionState.SPEAKING
            await self._send_ws_state("speaking")

            word_count = len(response_text.split())
            total_audio_bytes = 0
            tts_start = time.time()
            logger.info(f"[INFO] pipeline: TTS synthesis — words={word_count}")

            async for audio_chunk in self.tts.synthesize_stream(
                self._text_chunk_iterator(text_chunks),
                voice_id=self.config.voice_id,
                language=self.config.language,
            ):
                if self._barge_in_event.is_set():
                    logger.info("[INFO] pipeline: TTS interrupted by barge-in")
                    break

                if self._audio_out_callback:
                    result = self._audio_out_callback(audio_chunk)
                    if asyncio.iscoroutine(result):
                        await result
                total_audio_bytes += len(audio_chunk)

            tts_latency = time.time() - tts_start
            logger.info(f"[INFO] pipeline: TTS latency={tts_latency:.3f}s — words={word_count} — audio_size={total_audio_bytes} bytes")

        except Exception as e:
            logger.error(f"[ERROR] pipeline: LLM/TTS error: {e}", exc_info=True)
            self._emit_transcript("agent", f"[Error: {str(e)[:200]}]")
        
        # Always return to listening state
        logger.info(f"[INFO] pipeline: State transition: {self.state.value} → {SessionState.LISTENING.value}")
        self.is_speaking = False
        self.state = SessionState.LISTENING
        await self._send_ws_state("listening")

    async def _text_chunk_iterator(self, chunks: list[str]) -> AsyncIterator[str]:
        """Convert a list of text chunks into an async iterator."""
        for chunk in chunks:
            yield chunk
            await asyncio.sleep(0)  # Yield control

    def _build_default_system_prompt(self) -> str:
        """Build a default system prompt from config."""
        parts = [f"You are {self.config.name}, a {self.config.role}."]
        if self.config.organization:
            parts.append(f"You work for {self.config.organization}.")
        parts.append("Keep responses concise (1-3 sentences) and conversational.")

        if self.config.objectives:
            parts.append("\nObjectives:")
            for obj in self.config.objectives:
                parts.append(f"- {obj}")

        if self.config.predefined_questions:
            parts.append("\nSuggested questions (adapt naturally):")
            for q in self.config.predefined_questions:
                parts.append(f"- {q}")

        return "\n".join(parts)

    def _emit_transcript(self, event_type: str, text: str, is_partial: bool = False) -> None:
        """Emit a transcript event to all registered callbacks."""
        event = TranscriptEvent(type=event_type, text=text, is_partial=is_partial)
        for callback in self._transcript_callbacks:
            try:
                result = callback(event)
                # If callback is async, schedule it
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as e:
                logger.error(f"Transcript callback error: {e}")
        # NOTE: Do NOT also send via _websocket_transport directly —
        # the WebSocketTransport registers its own callback via on_transcript(),
        # so sending here would duplicate the message.

    def _save_transcript(self, speaker: str, text: str) -> None:
        """Save a transcript entry to the SQLite database."""
        if not self.database:
            return
        try:
            self.database.save_transcript_entry(
                call_id=self.call_id,
                timestamp=time.time(),
                speaker=speaker,
                text=text,
                is_partial=False,
            )
        except Exception as e:
            logger.error(f"Failed to save transcript entry: {e}")

    async def handle_interruption(self) -> None:
        """Handle barge-in when user speaks while agent is talking."""
        self.is_speaking = False
        self._barge_in_event.set()
        self.state = SessionState.LISTENING
        logger.info("Interruption handled — agent output stopped")

    async def shutdown(self) -> None:
        """Clean shutdown of all components."""
        self.state = SessionState.ENDED
        self.is_speaking = False
        self.is_listening = False

        duration = time.time() - self._session_start if self._session_start else 0
        logger.info(f"Agent session ended (duration: {duration:.1f}s)")

        # Phase 1.5 — Post-call processing
        if self.conversation_history:
            await self._run_post_call_processing(duration)

        # Phase 1.5 — Update call record in database
        if self.database:
            try:
                end_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
                objectives_met = []
                if self.flow_manager:
                    objectives_met = self.flow_manager.covered_objectives
                self.database.update_call_end(
                    call_id=self.call_id,
                    end_time=end_time,
                    duration=duration,
                    summary="",
                    status="completed",
                    objectives_met=json.dumps(objectives_met),
                )
            except Exception as e:
                logger.error(f"Failed to update call record: {e}")

    async def _run_post_call_processing(self, duration: float) -> None:
        """Run post-call processing: summary, action items, scorecard."""
        try:
            from voxatar.postcall.processor import PostCallProcessor

            if not self.llm or not self.database:
                return

            processor = PostCallProcessor(llm=self.llm, database=self.database)
            record = await processor.process_call(
                call_id=self.call_id,
                agent_name=self.config.name,
                conversation_history=self.conversation_history,
                objectives=self.config.objectives,
                start_time=self._session_start or time.time(),
            )

            # Update call record with summary
            self.database.update_call_end(
                call_id=self.call_id,
                end_time=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                duration=duration,
                summary=record.summary,
                status="completed",
                objectives_met=json.dumps(record.scorecard and [e.objective for e in record.scorecard if e.status == "achieved"] or []),
            )

            logger.info(f"Post-call processing complete: {len(record.action_items)} action items, scorecard with {len(record.scorecard)} entries")

        except Exception as e:
            logger.error(f"Post-call processing failed: {e}", exc_info=True)

    async def _generate_summary(self) -> str:
        """Generate a post-call summary using the LLM."""
        if not self.llm or not self.conversation_history:
            return ""

        summary_prompt = (
            "Please provide a brief summary of this conversation, "
            "including key points discussed and any action items."
        )

        summary = await self.llm.generate(
            messages=self.conversation_history + [
                Message(role="user", content=summary_prompt)
            ],
            system_prompt="You are a helpful assistant that summarizes conversations.",
            temperature=0.3,
            max_tokens=500,
        )

        logger.info(f"Summary generated: {summary[:100]}...")
        self._emit_transcript("system", f"Call Summary: {summary}")
        return summary

    @property
    def transcript(self) -> list[dict]:
        """Get the full conversation transcript."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.conversation_history
        ]