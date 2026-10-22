"""
Example: Simple Voice Agent

This example shows how to configure and run a basic Voxatar voice agent.
Requires: Ollama running locally, microphone access in browser.
"""

import asyncio
import sys
sys.path.insert(0, "..")

from voxatar.pipeline import AgentConfig, VoiceAgentPipeline


async def main():
    # Configure the agent
    config = AgentConfig(
        name="Interview Bot",
        role="Technical Recruiter",
        organization="Acme Corp",
        
        # Components
        stt_engine="whisper",
        llm_engine="ollama",
        tts_engine="kokoro",
        avatar_engine="musetalk",
        transport_engine="webrtc",
        
        # LLM
        llm_model="llama3.1:8b",
        system_prompt=(
            "You are a technical recruiter conducting a screening interview. "
            "Keep responses short (1-3 sentences). Ask follow-up questions. "
            "Be professional but conversational."
        ),
        temperature=0.7,
        max_tokens=150,
        
        # Voice
        voice_id=None,  # Use default voice
        language="en",
        
        # Avatar
        reference_image="./avatars/recruiter.png",
        
        # Conversation flow
        objectives=[
            "Screen candidate for Python experience",
            "Assess problem-solving ability",
            "Gauge cultural fit",
        ],
        predefined_questions=[
            "Tell me about your experience with Python.",
            "Describe a challenging project you worked on recently.",
            "How do you approach debugging a complex issue?",
            "What are your salary expectations?",
        ],
        max_duration=1800,  # 30 minutes
        
        # Knowledge base
        knowledge_sources=[
            "./docs/product-faq.md",
        ],
        
        # Post-call
        generate_summary=True,
        extract_action_items=True,
    )
    
    # Create and run the pipeline
    agent = VoiceAgentPipeline(config)
    
    try:
        print(f"Starting {config.name}...")
        print(f"  LLM: {config.llm_model}")
        print(f"  STT: {config.stt_engine}")
        print(f"  TTS: {config.tts_engine}")
        print(f"  Avatar: {config.avatar_engine}")
        print(f"  Duration: {config.max_duration}s")
        print()
        print("Open http://localhost:8080 in your browser to start talking.")
        print("Press Ctrl+C to stop.")
        
        await agent.run()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await agent.shutdown()
        print("Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())