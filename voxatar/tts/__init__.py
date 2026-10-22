# TTS (Text-to-Speech) adapters

"""Text-to-Speech engine adapters for Voxatar."""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""
    
    @abstractmethod
    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice_id: str | None = None,
        language: str = "en",
    ) -> AsyncIterator[bytes]:
        """
        Stream text in, get audio chunks out.
        
        Args:
            text_stream: Async iterator of text tokens/chunks
            voice_id: Voice identifier (cloned or built-in)
            language: Language code
            
        Yields:
            Audio bytes (PCM or WAV format)
        """
        pass
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "en",
    ) -> bytes:
        """Synthesize a complete text string (batch mode)."""
        pass
    
    async def clone_voice(self, audio_sample: bytes, name: str) -> str:
        """
        Clone a voice from an audio sample.
        Not supported by all engines — override if available.
        
        Args:
            audio_sample: Audio bytes (6+ seconds)
            name: Name for the cloned voice
            
        Returns:
            voice_id for the cloned voice
        """
        raise NotImplementedError("Voice cloning not supported by this engine")
    
    def list_voices(self) -> list[dict]:
        """List available built-in voices."""
        return []