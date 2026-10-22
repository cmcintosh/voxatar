# Voxatar - Open-Source AI Voice Agents

"""
Voxatar: Open-source AI voice agents with cloned voices and real-time avatar video.
Self-hosted, local-first alternative to Fireflies.ai voice agents.
"""

__version__ = "0.1.0"
__author__ = "Wembassy / Voxatar Contributors"
__license__ = "MIT"
__description__ = "Open-source AI voice agents with cloned voices and real-time avatar video"

# Component registry (populated by adapters on import)
_REGISTRY = {
    "stt": {},
    "llm": {},
    "tts": {},
    "avatar": {},
    "transport": {},
}


def register_stt(name: str, cls) -> None:
    """Register a Speech-to-Text engine."""
    _REGISTRY["stt"][name] = cls


def register_llm(name: str, cls) -> None:
    """Register an LLM engine."""
    _REGISTRY["llm"][name] = cls


def register_tts(name: str, cls) -> None:
    """Register a Text-to-Speech engine."""
    _REGISTRY["tts"][name] = cls


def register_avatar(name: str, cls) -> None:
    """Register an avatar engine."""
    _REGISTRY["avatar"][name] = cls


def register_transport(name: str, cls) -> None:
    """Register a transport engine."""
    _REGISTRY["transport"][name] = cls


def get_stt(name: str):
    """Get a registered STT engine."""
    return _REGISTRY["stt"].get(name)


def get_llm(name: str):
    """Get a registered LLM engine."""
    return _REGISTRY["llm"].get(name)


def get_tts(name: str):
    """Get a registered TTS engine."""
    return _REGISTRY["tts"].get(name)


def get_avatar(name: str):
    """Get a registered avatar engine."""
    return _REGISTRY["avatar"].get(name)


def get_transport(name: str):
    """Get a registered transport engine."""
    return _REGISTRY["transport"].get(name)