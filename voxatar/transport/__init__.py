# Transport (WebRTC / WebSocket) adapters

"""Transport layer adapters for Voxatar real-time communication."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Optional


class TransportEngine(ABC):
    """Abstract base class for transport engines."""
    
    @abstractmethod
    async def start_server(self, host: str, port: int) -> None:
        """Start the transport server."""
        pass
    
    @abstractmethod
    async def stop_server(self) -> None:
        """Stop the transport server."""
        pass
    
    @abstractmethod
    async def handle_connection(
        self,
        on_audio_received: Callable[[bytes], None],
        on_video_received: Callable[[bytes], None],
    ) -> AsyncIterator[tuple[bytes, bytes]]:
        """
        Handle an incoming client connection.
        
        Yields:
            Tuples of (audio_out, video_out) to send to client
        """
        pass
    
    @abstractmethod
    async def send_audio(self, audio: bytes) -> None:
        """Send audio to connected client."""
        pass
    
    @abstractmethod
    async def send_video(self, frame: bytes) -> None:
        """Send video frame to connected client."""
        pass