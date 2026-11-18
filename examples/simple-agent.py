"""
Example: Simple Voice Agent

This example shows how to configure and run a basic Voxatar voice agent.
Requires: Ollama running locally, microphone access in browser.

Usage:
    python examples/simple-agent.py
    # Or use the CLI:
    # voxatar serve --agent examples/simple-agent.yaml
"""

import asyncio
import logging
import sys
sys.path.insert(0, "..")

from voxatar.config import AgentConfig
from voxatar.server import VoxatarServer


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load config from YAML
    config = AgentConfig.from_yaml("examples/simple-agent.yaml")

    print(f"Starting {config.name}...")
    print(f"  LLM: {config.llm_model}")
    print(f"  STT: whisper ({config.stt_model})")
    print(f"  TTS: edge-tts")
    print(f"  Server: http://{config.host}:{config.port}")
    print()
    print("Open the URL above in your browser to start talking.")
    print("Press Ctrl+C to stop.")

    # Start the server
    server = VoxatarServer(config)
    server.run(config.host, config.port)


if __name__ == "__main__":
    main()