# LLM (Large Language Model) adapters

"""LLM engine adapters for Voxatar conversation management."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class Message:
    """A conversation message."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class Tool:
    """A function/tool the LLM can call."""
    name: str
    description: str
    parameters: dict  # JSON schema


class LLMEngine(ABC):
    """Abstract base class for LLM engines."""
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str = "",
        knowledge_context: Optional[str] = None,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from the LLM.
        
        Args:
            messages: Conversation history
            system_prompt: System prompt for agent behavior
            knowledge_context: RAG-retrieved context to inject
            tools: Available tools/functions
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Text tokens (streaming)
        """
        pass
    
    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        system_prompt: str = "",
        knowledge_context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a complete response (batch mode)."""
        pass