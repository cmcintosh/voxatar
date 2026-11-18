"""
CLI entry point for Voxatar.

Usage:
    voxatar serve --agent examples/simple-agent.yaml
    voxatar serve --host 0.0.0.0 --port 8080
    voxatar info
"""

import logging
import sys

import click

from voxatar.config import AgentConfig
from voxatar.server import VoxatarServer

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """Voxatar — Open-source AI voice agents."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@cli.command()
@click.option(
    "--agent", "-a",
    type=click.Path(exists=True),
    help="Path to agent YAML config file",
)
@click.option(
    "--host", "-h",
    default="0.0.0.0",
    help="Host to bind to (default: 0.0.0.0)",
)
@click.option(
    "--port", "-p",
    default=8080,
    type=int,
    help="Port to bind to (default: 8080)",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override LLM model (e.g., llama3.1:8b)",
)
@click.option(
    "--ollama-url",
    default=None,
    help="Override Ollama API URL (default: http://localhost:11434/v1)",
)
def serve(agent, host, port, model, ollama_url):
    """Start the Voxatar voice agent server."""
    # Load config
    if agent:
        click.echo(f"Loading agent config from: {agent}")
        config = AgentConfig.from_yaml(agent)
    else:
        click.echo("Using default agent configuration")
        config = AgentConfig()

    # Apply overrides
    if model:
        config.llm_model = model
    if ollama_url:
        config.llm_base_url = ollama_url

    config.host = host
    config.port = port

    click.echo(f"  Agent: {config.name}")
    click.echo(f"  Role: {config.role}")
    click.echo(f"  LLM: {config.llm_model} at {config.llm_base_url}")
    click.echo(f"  STT: whisper ({config.stt_model})")
    click.echo(f"  TTS: edge-tts")
    click.echo(f"  Server: http://{host}:{port}")
    click.echo()
    click.echo("Open the URL above in your browser to start a voice call.")
    click.echo("Press Ctrl+C to stop.")
    click.echo()

    # Start server
    server = VoxatarServer(config)
    server.run(host, port)


@cli.command()
@click.option(
    "--agent", "-a",
    type=click.Path(exists=True),
    help="Path to agent YAML config file",
)
def info(agent):
    """Display agent configuration info."""
    if agent:
        config = AgentConfig.from_yaml(agent)
    else:
        config = AgentConfig()

    click.echo(f"Agent Name: {config.name}")
    click.echo(f"Role: {config.role}")
    click.echo(f"Organization: {config.organization or 'N/A'}")
    click.echo()
    click.echo(f"STT Engine: {config.stt_engine} (model: {config.stt_model})")
    click.echo(f"LLM Engine: {config.llm_engine} (model: {config.llm_model})")
    click.echo(f"TTS Engine: {config.tts_engine}")
    click.echo(f"Transport: {config.transport_engine}")
    click.echo()

    if config.objectives:
        click.echo("Objectives:")
        for obj in config.objectives:
            click.echo(f"  - {obj}")

    if config.predefined_questions:
        click.echo("Predefined Questions:")
        for q in config.predefined_questions:
            click.echo(f"  - {q}")

    click.echo()
    if config.system_prompt:
        click.echo("System Prompt:")
        click.echo(f"  {config.system_prompt[:200]}...")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()