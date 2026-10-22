# Avatar (Lip-Sync Video) adapters

"""Avatar video generation adapters for Voxatar."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional


class AvatarEngine(ABC):
    """Abstract base class for avatar/lip-sync engines."""
    
    @abstractmethod
    async def generate_video_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        reference_image: str | bytes,
        fps: int = 30,
    ) -> AsyncIterator[bytes]:
        """
        Generate lip-synced video frames from audio.
        
        Args:
            audio_stream: Async iterator of audio bytes
            reference_image: Path to reference face image or raw bytes
            fps: Target frames per second
            
        Yields:
            Video frame bytes (JPEG or PNG)
        """
        pass
    
    @abstractmethod
    async def generate_video(
        self,
        audio: bytes,
        reference_image: str | bytes,
        fps: int = 30,
    ) -> bytes:
        """Generate complete video from audio (batch mode)."""
        pass
    
    def supported_resolutions(self) -> list[tuple[int, int]]:
        """Return supported output resolutions."""
        return [(256, 256)]