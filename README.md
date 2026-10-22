# 🎙️ Voxatar

**Open-source AI voice agents with cloned voices and real-time avatar video. Self-hosted, local-first.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Self-hosted](https://img.shields.io/badge/Self--hosted-✓-blue.svg)](#)

---

## What is Voxatar?

Voxatar is an open-source, locally-hosted alternative to Fireflies.ai voice agents. It enables you to deploy **AI-powered voice agents** that can:

- 🗣️ **Conduct live, two-way voice conversations** — natural, real-time, with low latency
- 🎭 **Use your own cloned voice** — from a 6-second audio sample
- 📹 **Present as an AI avatar** — with real-time lip-sync video
- 📋 **Ask predefined questions** and follow up dynamically based on responses
- 📚 **Reference knowledge bases** — upload docs, FAQs, and context for the agent
- 📝 **Generate post-call summaries** — transcripts, action items, scorecards
- 🔗 **Share via link, embed, or QR code** — anyone can join from a browser
- 🔒 **Run entirely on your own infrastructure** — no cloud dependencies, no data leaves your machine

## Why Voxatar?

Commercial voice agent platforms like Fireflies.ai charge monthly fees, lock your data in their cloud, and limit customization. Voxatar puts the entire pipeline — speech-to-text, LLM reasoning, text-to-speech, voice cloning, and avatar video — **on your own hardware**, under your control.

| Feature | Fireflies.ai | Voxatar |
|---------|-------------|---------|
| Self-hosted | ❌ | ✅ |
| Open source | ❌ | ✅ (MIT) |
| Voice cloning | ✅ (cloud) | ✅ (local) |
| Avatar video | ✅ (cloud) | ✅ (local) |
| Custom LLM | ❌ | ✅ (Ollama, vLLM, any OpenAI-compatible API) |
| Knowledge base / RAG | ✅ (cloud) | ✅ (local docs) |
| Data privacy | ⚠️ Cloud | ✅ Fully local |
| Cost | $10-19/seat/mo + usage | Free (your hardware) |
| Customization | Limited | Full source access |

## Quick Start

```bash
# Clone
git clone https://github.com/cmcintosh/voxatar.git
cd voxatar

# Run with Docker (coming soon)
docker compose up

# Or run locally
pip install -e .
voxatar serve --agent examples/simple-agent.py
```

## Architecture

```
Browser Client (WebRTC) ←→ Signaling Server
                              ↓
                    Voice Agent Pipeline
                              ↓
                    ┌─────────────────┐
                    │   STT (Whisper)  │ ← Audio stream
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │   LLM (Ollama)   │ ← Text + system prompt + knowledge base
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │  TTS (XTTS/F5)   │ ← Text → Audio (cloned voice)
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Lip Sync (MuseTalk) │ ← Audio + Face image → Video frames
                    └────────┬────────┘
                             ↓
                    WebRTC video stream back to browser
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical breakdown.

## Components

| Component | Purpose | Recommended | Alternatives |
|-----------|---------|-------------|--------------|
| **STT** | Speech-to-text, streaming | Whisper (whisper.cpp) | FunASR, Moonshine, Piper |
| **LLM** | Conversation brain | Ollama (Llama 3, Qwen, GLM) | vLLM, any OpenAI-compatible API |
| **TTS** | Text-to-speech + voice cloning | XTTS v2 | F5-TTS, Chatterbox, Kokoro, Piper |
| **Avatar** | Lip-sync video generation | MuseTalk | SadTalker, LatentSync, LivePortrait |
| **Transport** | Real-time audio/video | WebRTC (Pipecat) | WebSocket, aiortc |

## Roadmap

- **Phase 1 (MVP):** Audio-only voice agent — STT → LLM → TTS pipeline over WebRTC
- **Phase 2 (v1.0):** Voice cloning + avatar video + knowledge base RAG
- **Phase 3 (v2.0):** Multi-agent handoffs, post-call analytics, integrations

See [ROADMAP.md](ROADMAP.md) for details.

## Project Structure

```
voxatar/
├── voxatar/          # Python package (pipeline, components)
│   ├── stt/          # Speech-to-text adapters
│   ├── tts/          # Text-to-speech + voice cloning
│   ├── llm/          # LLM conversation management
│   ├── avatar/       # Lip-sync / avatar video
│   └── transport/    # WebRTC / WebSocket transport
├── web/              # Frontend client
├── docker/           # Docker setup
├── docs/             # Documentation
├── examples/         # Example agents
└── tests/            # Test suite
```

## Use Cases

- **Recruiting:** Automated screening interviews with dynamic follow-up questions
- **Sales:** Discovery calls that reference your product knowledge base
- **User Research:** Conduct interviews at scale with consistent question flows
- **Customer Support:** Voice agents that can access your docs and FAQs
- **Check-ins:** Automated wellness or status check-in calls
- **Education:** Interactive tutoring sessions with avatar presence

## Contributing

We welcome contributions! This is an early-stage project with many areas to build.

1. Check [open issues](https://github.com/cmcintosh/voxatar/issues) — look for `decision` and `wayfinder` labels
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design
3. Check [ROADMAP.md](ROADMAP.md) for what's planned
4. Open an issue or PR

## License

MIT — see [LICENSE](LICENSE)

## Acknowledgments

Voxatar builds on the shoulders of giants:
- [Pipecat](https://github.com/pipecat-ai/pipecat) — real-time voice agent framework
- [Whisper](https://github.com/openai/whisper) / [whisper.cpp](https://github.com/ggerganov/whisper.cpp) — STT
- [Ollama](https://ollama.ai) — local LLM serving
- [XTTS v2](https://github.com/coqui-ai/TTS) / [F5-TTS](https://github.com/SWivid/F5-TTS) — TTS + voice cloning
- [MuseTalk](https://github.com/TMElyralab/MuseTalk) — real-time lip sync
- [WebRTC](https://webrtc.org) — real-time transport

---

**Star ⭐ this repo if you're interested in self-hosted AI voice agents!**