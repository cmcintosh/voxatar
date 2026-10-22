# STT (Speech-to-Text) adapters

"""Speech-to-Text engine adapters for Voxatar."""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class STTEngine(ABC):
    """Abstract base class for STT engines."""
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """
        Stream audio in, get transcribed text chunks out.
        
        Args:
            audio_stream: Async iterator of audio bytes (16kHz, 16-bit, mono)
            
        Yields:
            Transcribed text chunks (partial and final)
        """
        pass
    
    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe a complete audio buffer (batch mode)."""
        pass