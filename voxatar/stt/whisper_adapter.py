"""
Whisper STT adapter using faster-whisper.

Provides streaming and batch speech-to-text with Voice Activity Detection (VAD).
"""

import asyncio
import io
import logging
import wave
from typing import AsyncIterator, Optional

import numpy as np

from voxatar.stt import STTEngine

logger = logging.getLogger(__name__)

# Register with the component registry
import voxatar
voxatar.register_stt("whisper", None)  # placeholder, replaced below


class WhisperSTT(STTEngine):
    """
    Speech-to-Text using faster-whisper.

    Supports:
    - Streaming transcription with VAD (Voice Activity Detection)
    - Batch transcription of complete audio
    - Multiple model sizes (tiny, base, small, medium, large)
    - CPU and CUDA inference
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        vad_filter: bool = True,
        vad_parameters: Optional[dict] = None,
    ):
        """
        Initialize the Whisper STT engine.

        Args:
            model_size: Model size — tiny, base, small, medium, large
            device: Inference device — cpu or cuda
            compute_type: Compute type — int8, float16, float32
            language: Language code for transcription
            vad_filter: Enable voice activity detection
            vad_parameters: Custom VAD parameters (min_silence_duration_ms, etc.)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.vad_filter = vad_filter
        self.vad_parameters = vad_parameters or {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 250,
        }
        self._model = None
        self._initialized = False

    async def initialize(self) -> None:
        """Load the whisper model (lazy initialization)."""
        if self._initialized:
            return

        logger.info(f"Loading faster-whisper model: {self.model_size} ({self.device}/{self.compute_type})")

        # Run in executor since model loading is synchronous
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            self._load_model,
        )
        self._initialized = True
        logger.info("Whisper model loaded successfully")

    def _load_model(self):
        """Load the model (runs in executor)."""
        from faster_whisper import WhisperModel

        return WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    async def transcribe(self, audio: bytes) -> str:
        """
        Transcribe a complete audio buffer (batch mode).

        Args:
            audio: WAV format audio bytes (16kHz, 16-bit, mono preferred)

        Returns:
            Transcribed text
        """
        await self.initialize()

        # Convert WAV bytes to numpy array
        audio_array = self._wav_to_numpy(audio)

        if audio_array is None or len(audio_array) == 0:
            return ""

        # Run transcription in executor
        loop = asyncio.get_event_loop()
        segments, _info = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            audio_array,
        )

        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """
        Stream audio in, get transcribed text chunks out.

        Collects audio chunks until a silence is detected (via VAD),
        then transcribes the accumulated audio and yields the text.

        Args:
            audio_stream: Async iterator of audio bytes (WAV chunks)

        Yields:
            Transcribed text chunks (final results per utterance)
        """
        await self.initialize()

        audio_buffer = bytearray()
        chunk_count = 0

        async for chunk in audio_stream:
            audio_buffer.extend(chunk)
            chunk_count += 1

            # Process every ~1 second of audio (32KB at 16kHz 16-bit mono)
            if len(audio_buffer) >= 32000:
                audio_array = self._wav_to_numpy(bytes(audio_buffer))

                if audio_array is not None and len(audio_array) > 0:
                    loop = asyncio.get_event_loop()
                    segments, info = await loop.run_in_executor(
                        None,
                        self._transcribe_sync,
                        audio_array,
                    )

                    for segment in segments:
                        text = segment.text.strip()
                        if text:
                            yield text

                # Reset buffer
                audio_buffer = bytearray()

        # Process remaining audio
        if audio_buffer:
            audio_array = self._wav_to_numpy(bytes(audio_buffer))
            if audio_array is not None and len(audio_array) > 0:
                loop = asyncio.get_event_loop()
                segments, _info = await loop.run_in_executor(
                    None,
                    self._transcribe_sync,
                    audio_array,
                )
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        yield text

    def _transcribe_sync(self, audio_array: np.ndarray):
        """Synchronous transcription (runs in executor)."""
        return self._model.transcribe(
            audio_array,
            language=self.language,
            vad_filter=self.vad_filter,
            vad_parameters=self.vad_parameters,
            beam_size=5,
        )

    @staticmethod
    def _wav_to_numpy(wav_bytes: bytes) -> Optional[np.ndarray]:
        """Convert WAV bytes to numpy float32 array."""
        try:
            with io.BytesIO(wav_bytes) as wav_io:
                with wave.open(wav_io, "rb") as wav_file:
                    frames = wav_file.readframes(wav_file.getnframes())
                    sample_width = wav_file.getsampwidth()
                    n_channels = wav_file.getnchannels()

                    # Convert to numpy
                    if sample_width == 2:
                        audio = np.frombuffer(frames, dtype=np.int16)
                    elif sample_width == 1:
                        audio = np.frombuffer(frames, dtype=np.uint8)
                        audio = (audio.astype(np.float32) - 128) / 128
                    else:
                        audio = np.frombuffer(frames, dtype=np.int32)
                        audio = audio / (2**31)

                    if sample_width == 2:
                        audio = audio.astype(np.float32) / 32768.0

                    # Average channels if stereo
                    if n_channels > 1:
                        audio = audio[::n_channels]

                    return audio
        except Exception as e:
            logger.debug(f"WAV parsing failed: {e}, trying raw PCM")
            # Try raw 16-bit PCM
            try:
                audio = np.frombuffer(wav_bytes, dtype=np.int16)
                if len(audio) > 0:
                    return audio.astype(np.float32) / 32768.0
            except Exception:
                pass
            return None


# Replace placeholder registration
voxatar._REGISTRY["stt"]["whisper"] = WhisperSTT