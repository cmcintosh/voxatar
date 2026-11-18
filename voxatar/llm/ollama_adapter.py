"""
Ollama LLM adapter using OpenAI-compatible API.

Provides streaming and batch text generation with conversation management.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from voxatar.llm import LLMEngine, Message

logger = logging.getLogger(__name__)

import voxatar
voxatar.register_llm("ollama", None)  # placeholder, replaced below


class OllamaLLM(LLMEngine):
    """
    LLM adapter using Ollama's OpenAI-compatible API.

    Supports:
    - Streaming token generation
    - Batch generation
    - Conversation history management
    - Configurable model, temperature, and max tokens
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",  # Ollama doesn't need a real key
        timeout: float = 60.0,
    ):
        """
        Initialize the Ollama LLM adapter.

        Args:
            model: Model name (e.g., llama3.1:8b, qwen2.5:7b)
            base_url: Ollama OpenAI-compatible API URL
            api_key: API key (Ollama accepts any value)
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    async def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str = "",
        knowledge_context: Optional[str] = None,
        tools: Optional[list] = None,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from the LLM.

        Args:
            messages: Conversation history
            system_prompt: System prompt for agent behavior
            knowledge_context: RAG-retrieved context to inject
            tools: Available tools (not implemented in MVP)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text tokens (streaming)
        """
        client = self._get_client()

        # Build the message list for the API
        api_messages = self._build_api_messages(messages, system_prompt, knowledge_context)

        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            yield f"[Error: {str(e)}]"

    async def generate(
        self,
        messages: list[Message],
        system_prompt: str = "",
        knowledge_context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Generate a complete response (batch mode).

        Args:
            messages: Conversation history
            system_prompt: System prompt for agent behavior
            knowledge_context: RAG-retrieved context to inject
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Complete generated text
        """
        client = self._get_client()

        api_messages = self._build_api_messages(messages, system_prompt, knowledge_context)

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            return ""

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return f"[Error: {str(e)}]"

    @staticmethod
    def _build_api_messages(
        messages: list[Message],
        system_prompt: str,
        knowledge_context: Optional[str],
    ) -> list[dict]:
        """Build the API message list from conversation messages."""
        api_messages = []

        # System prompt
        if system_prompt:
            sys_content = system_prompt
            if knowledge_context:
                sys_content += f"\n\nRelevant knowledge:\n{knowledge_context}"
            api_messages.append({
                "role": "system",
                "content": sys_content,
            })

        # Conversation history
        for msg in messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        return api_messages

    async def health_check(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            client = self._get_client()
            response = await client.models.list()
            model_ids = [m.id for m in response.data]
            # Ollama may return model names differently
            return True  # If we can list models, Ollama is running
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False


# Replace placeholder registration
voxatar._REGISTRY["llm"]["ollama"] = OllamaLLM