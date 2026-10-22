"""
Configuration management for Voxatar agents.

Loads agent definitions from YAML files, supporting:
- System prompts and LLM settings
- Objectives and predefined questions
- Component engine selection
- Voice and language settings
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a voice agent session."""

    # Identity
    name: str = "Voxatar Agent"
    role: str = "Assistant"
    organization: str = ""

    # Component engines
    stt_engine: str = "whisper"
    llm_engine: str = "ollama"
    tts_engine: str = "edge-tts"
    transport_engine: str = "webrtc"

    # LLM settings
    llm_model: str = "llama3.1:8b"
    llm_base_url: str = "http://localhost:11434/v1"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 150

    # STT settings
    stt_model: str = "base"  # tiny, base, small, medium, large
    stt_language: str = "en"
    stt_device: str = "cpu"  # cpu or cuda
    stt_compute_type: str = "int8"  # int8, float16, float32

    # TTS settings
    voice_id: Optional[str] = None
    tts_rate: str = "+0%"
    tts_volume: str = "+0%"
    language: str = "en"

    # Conversation settings
    objectives: list[str] = field(default_factory=list)
    predefined_questions: list[str] = field(default_factory=list)
    max_duration: int = 1800  # seconds

    # Knowledge base
    knowledge_sources: list[str] = field(default_factory=list)
    knowledge_persist_dir: str = "/app/data/chromadb"
    knowledge_documents_dir: str = "/app/data/documents"
    knowledge_embedding_model: str = "nomic-embed-text"
    knowledge_ollama_url: str = "http://host.docker.internal:11434"

    # Conversation flow
    flow_mode: str = "guided"  # "guided" or "freeform"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    # Post-call
    generate_summary: bool = True
    extract_action_items: bool = True
    extract_key_topics: bool = True
    analyze_sentiment: bool = True
    generate_scorecard: bool = True

    # Agent configs directory (for shareable links)
    agents_dir: str = "/app/agents"

    # Privacy
    require_consent: bool = True
    consent_message: str = (
        "This call may be recorded and transcribed for quality purposes. "
        "By continuing, you consent to audio recording and AI processing."
    )
    data_retention_days: int = 30

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AgentConfig":
        """Load agent configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Agent config not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty config file: {path}")

        logger.info(f"Loading agent config from {path}")

        # Build system prompt from components if not explicitly set
        system_prompt = data.get("system_prompt", "")
        objectives = data.get("objectives", [])
        questions = data.get("predefined_questions", [])

        if not system_prompt and (objectives or questions):
            system_prompt = _build_system_prompt(data)

        # Map YAML keys to dataclass fields
        field_map = {
            "name": "name",
            "role": "role",
            "organization": "organization",
            "stt_engine": "stt_engine",
            "llm_engine": "llm_engine",
            "tts_engine": "tts_engine",
            "transport_engine": "transport_engine",
            "llm_model": "llm_model",
            "llm_base_url": "llm_base_url",
            "system_prompt": "system_prompt",
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "stt_model": "stt_model",
            "stt_language": "stt_language",
            "voice_id": "voice_id",
            "language": "language",
            "objectives": "objectives",
            "predefined_questions": "predefined_questions",
            "max_duration": "max_duration",
            "knowledge_sources": "knowledge_sources",
            "knowledge_persist_dir": "knowledge_persist_dir",
            "knowledge_documents_dir": "knowledge_documents_dir",
            "knowledge_embedding_model": "knowledge_embedding_model",
            "knowledge_ollama_url": "knowledge_ollama_url",
            "flow_mode": "flow_mode",
            "agents_dir": "agents_dir",
            "host": "host",
            "port": "port",
            "generate_summary": "generate_summary",
            "extract_action_items": "extract_action_items",
            "require_consent": "require_consent",
            "consent_message": "consent_message",
            "data_retention_days": "data_retention_days",
        }

        kwargs = {}
        for yaml_key, dc_key in field_map.items():
            if yaml_key in data:
                kwargs[dc_key] = data[yaml_key]

        config = cls(**kwargs)

        # If system prompt was auto-built, override
        if not data.get("system_prompt") and (objectives or questions):
            config.system_prompt = system_prompt

        return config

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith("_")
        }


def _build_system_prompt(data: dict) -> str:
    """Build a system prompt from objectives and predefined questions."""
    parts = []

    name = data.get("name", "Voxatar Agent")
    role = data.get("role", "Assistant")
    org = data.get("organization", "")

    parts.append(f"You are {name}, a {role}.")
    if org:
        parts.append(f"You work for {org}.")

    parts.append("Keep your responses concise (1-3 sentences) and conversational.")
    parts.append("Ask follow-up questions naturally based on the conversation.")

    objectives = data.get("objectives", [])
    if objectives:
        parts.append("\nYour objectives for this conversation:")
        for obj in objectives:
            parts.append(f"- {obj}")

    questions = data.get("predefined_questions", [])
    if questions:
        parts.append("\nSuggested questions to ask (adapt as conversation flows):")
        for q in questions:
            parts.append(f"- {q}")

    return "\n".join(parts)