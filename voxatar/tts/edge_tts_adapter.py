"""
Edge-TTS adapter for text-to-speech synthesis.

Uses Microsoft Edge's online TTS service (MIT-licensed package).
This is the MVP fallback for Kokoro — simpler to install, no model files needed.

Supports:
- Streaming synthesis (text in, audio chunks out)
- Batch synthesis
- Multiple built-in voices
- Adjustable rate and volume
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from voxatar.tts import TTSEngine

logger = logging.getLogger(__name__)

import voxatar
voxatar.register_tts("edge-tts", None)  # placeholder, replaced below


# Default English voices
DEFAULT_VOICES = {
    "en": "en-US-AriaNeural",
    "en-US": "en-US-AriaNeural",
    "en-GB": "en-GB-SoniaNeural",
    "en-AU": "en-AU-NatashaNeural",
}

# Curated voice list for the UI
POPULAR_VOICES = [
    {"id": "en-US-AriaNeural", "name": "Aria (US Female)", "language": "en-US"},
    {"id": "en-US-GuyNeural", "name": "Guy (US Male)", "language": "en-US"},
    {"id": "en-US-JennyNeural", "name": "Jenny (US Female)", "language": "en-US"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher (US Male)", "language": "en-US"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia (UK Female)", "language": "en-GB"},
    {"id": "en-GB-RyanNeural", "name": "Ryan (UK Male)", "language": "en-GB"},
    {"id": "en-AU-NatashaNeural", "name": "Natasha (AU Female)", "language": "en-AU"},
    {"id": "en-AU-WilliamNeural", "name": "William (AU Male)", "language": "en-AU"},
]


class EdgeTTS(TTSEngine):
    """
    Text-to-Speech using edge-tts (Microsoft Edge TTS).

    Streaming-first architecture: text chunks go in, audio chunks come out.
    Output format: MP3 by default, can be configured.
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        language: str = "en",
        rate: str = "+0%",
        volume: str = "+0%",
        output_format: str = "audio-24khz-48kbitrate-mono-mp3",
    ):
        """
        Initialize the Edge TTS engine.

        Args:
            voice: Voice ID (e.g., "en-US-AriaNeural"). If None, uses default for language.
            language: Language code
            rate: Speech rate adjustment (e.g., "+10%", "-5%")
            volume: Volume adjustment (e.g., "+0%", "-10%")
            output_format: Audio output format
        """
        self.voice = voice or DEFAULT_VOICES.get(language, DEFAULT_VOICES["en"])
        self.language = language
        self.rate = rate
        self.volume = volume
        self.output_format = output_format

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en",
    ) -> bytes:
        """
        Synthesize a complete text string (batch mode).

        Args:
            text: Text to synthesize
            voice_id: Override voice ID
            language: Override language

        Returns:
            MP3 audio bytes
        """
        if not text.strip():
            return b""

        import edge_tts

        voice = voice_id or self.voice
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=self.rate,
            volume=self.volume,
        )

        audio_buffer = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])

        return bytes(audio_buffer)

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice_id: Optional[str] = None,
        language: str = "en",
    ) -> AsyncIterator[bytes]:
        """
        Stream text in, get audio chunks out.

        Accumulates text tokens until a sentence boundary is detected,
        then synthesizes and yields audio for that segment.

        Args:
            text_stream: Async iterator of text tokens/chunks
            voice_id: Override voice ID
            language: Override language

        Yields:
            MP3 audio bytes (chunks)
        """
        import edge_tts

        voice = voice_id or self.voice
        buffer = ""
        sentence_endings = ".!?\n"

        async for token in text_stream:
            buffer += token

            # Check for sentence boundary
            if any(buffer.endswith(c) for c in sentence_endings):
                sentence = buffer.strip()
                buffer = ""

                if sentence:
                    communicate = edge_tts.Communicate(
                        text=sentence,
                        voice=voice,
                        rate=self.rate,
                        volume=self.volume,
                    )

                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            yield chunk["data"]

        # Flush remaining buffer
        if buffer.strip():
            communicate = edge_tts.Communicate(
                text=buffer.strip(),
                voice=voice,
                rate=self.rate,
                volume=self.volume,
            )
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

    def list_voices(self) -> list[dict]:
        """List available built-in voices."""
        return POPULAR_VOICES


# Replace placeholder registration
voxatar._REGISTRY["tts"]["edge-tts"] = EdgeTTS