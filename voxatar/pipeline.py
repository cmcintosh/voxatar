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
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Callable, Optional

from voxatar.config import AgentConfig
from voxatar.llm import Message
from voxatar.llm.ollama_adapter import OllamaLLM
from voxatar.stt.whisper_adapter import WhisperSTT
from voxatar.tts.edge_tts_adapter import EdgeTTS

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
        self._session_start: Optional[float] = None
        self._barge_in_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize all pipeline components."""
        logger.info(f"Initializing pipeline for agent: {self.config.name}")
        logger.info(f"  STT: whisper ({self.config.stt_model})")
        logger.info(f"  LLM: ollama ({self.config.llm_model})")
        logger.info(f"  TTS: edge-tts")

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
        self.state = SessionState.LISTENING

        logger.info("Pipeline initialized — ready for conversation")

    def on_transcript(self, callback: Callable[[TranscriptEvent], None]) -> None:
        """Register a callback for transcript events."""
        self._transcript_callbacks.append(callback)

    def on_audio_out(self, callback: Callable[[bytes], None]) -> None:
        """Register a callback for outbound audio."""
        self._audio_out_callback = callback

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
        if self.is_speaking:
            # Barge-in: stop current speech
            logger.info("Barge-in detected — interrupting agent")
            self._barge_in_event.set()
            await asyncio.sleep(0.1)  # Let the barge-in propagate
            self._barge_in_event.clear()

        if not self.stt:
            return

        # Transcribe
        self.state = SessionState.LISTENING
        text = await self.stt.transcribe(audio)

        if not text.strip():
            return

        logger.info(f"Transcribed: {text}")
        self._emit_transcript("user", text)
        self.conversation_history.append(Message(role="user", content=text))

        # Generate and speak response
        await self._generate_and_speak()

    async def _generate_and_speak(self) -> None:
        """Generate LLM response and synthesize speech."""
        self.state = SessionState.THINKING
        self.is_speaking = True

        # Stream LLM response
        response_text = ""
        text_chunks = []

        async for token in self.llm.generate_stream(
            messages=self.conversation_history,
            system_prompt=self.config.system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            if self._barge_in_event.is_set():
                logger.info("LLM generation interrupted by barge-in")
                break

            response_text += token
            text_chunks.append(token)

        response_text = response_text.strip()

        if response_text:
            logger.info(f"Agent response: {response_text}")
            self._emit_transcript("agent", response_text)
            self.conversation_history.append(
                Message(role="assistant", content=response_text)
            )

            # Synthesize speech
            self.state = SessionState.SPEAKING

            async for audio_chunk in self.tts.synthesize_stream(
                self._text_chunk_iterator(text_chunks),
                voice_id=self.config.voice_id,
                language=self.config.language,
            ):
                if self._barge_in_event.is_set():
                    logger.info("TTS interrupted by barge-in")
                    break

                if self._audio_out_callback:
                    await self._audio_out_callback(audio_chunk)

        self.is_speaking = False
        self.state = SessionState.LISTENING

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
                callback(event)
            except Exception as e:
                logger.error(f"Transcript callback error: {e}")

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

        # Generate summary if enabled
        if self.config.generate_summary and self.conversation_history:
            await self._generate_summary()

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