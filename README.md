# 🎙️ Voxatar

**Open-source AI voice agents with cloned voices and real-time avatar video. Self-hosted, local-first.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Self-hosted](https://img.shields.io/badge/Self--hosted-✓-blue.svg)](#)

---

## What is Voxatar?

Voxatar is an open-source, locally-hosted alternative to Fireflies.ai voice agents. It enables you to deploy **AI-powered voice agents** that can:

- 🗣️ **Conduct live, two-way voice conversations** — natural, real-time, with low latency
- 🎭 **Use your own cloned voice** — from a 6-second audio sample (Phase 2)
- 📹 **Present as an AI avatar** — with real-time lip-sync video (Phase 2)
- 📋 **Ask predefined questions** and follow up dynamically based on responses
- 📚 **Reference knowledge bases** — upload docs, FAQs, and context for the agent (Phase 2)
- 📝 **Generate post-call summaries** — transcripts, action items, scorecards (Phase 3)
- 🔒 **Run entirely on your own infrastructure** — no cloud dependencies, no data leaves your machine

## Phase 1 MVP — Audio-Only Voice Agent

This is the Phase 1 MVP: a working audio-only voice agent with STT → LLM → TTS over WebRTC.

### What Works

- ✅ **WebRTC audio transport** — browser captures mic, sends to server via WebRTC
- ✅ **Speech-to-Text** — faster-whisper with VAD for accurate transcription
- ✅ **LLM responses** — Ollama (Llama 3.1, Qwen, etc.) with streaming
- ✅ **Text-to-Speech** — edge-tts for clear, natural speech output
- ✅ **Real-time transcript** — WebSocket-based live transcript display
- ✅ **Barge-in support** — interrupt the agent while it's speaking
- ✅ **Agent configs** — YAML-based agent definitions with objectives and questions
- ✅ **Docker Compose** — one command to run the full stack
- ✅ **Consent management** — configurable consent banner

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone
git clone https://github.com/cmcintosh/voxatar.git
cd voxatar

# Make sure Ollama is running and has the model
ollama pull llama3.1:8b

# Start the server
docker compose -f docker/docker-compose.yml up
```

Open http://localhost:8080 in your browser and click "Start Call".

### Option 2: Run Locally

```bash
# Clone
git clone https://github.com/cmcintosh/voxatar.git
cd voxatar

# Install Python dependencies
pip install -e .

# Make sure Ollama is running
ollama serve  # if not already running
ollama pull llama3.1:8b

# Build the web frontend
cd web
npm install
npm run build
cd ..

# Start the server
voxatar serve --agent examples/simple-agent.yaml
```

Open http://localhost:8080 in your browser and click "Start Call".

### Option 3: Development Mode

```bash
# Terminal 1: Start the Python server
pip install -e .
voxatar serve --agent examples/simple-agent.yaml

# Terminal 2: Start the Vite dev server (hot reload)
cd web
npm install
npm run dev
```

Open http://localhost:5173 (Vite dev server proxies API to localhost:8080).

## Configuration

Agent configs are YAML files. See `examples/simple-agent.yaml` for a full example.

```yaml
name: "Interview Bot"
role: "Technical Recruiter"
organization: "Acme Corp"

# LLM
llm_model: llama3.1:8b
llm_base_url: http://localhost:11434/v1
system_prompt: "You are a technical recruiter..."

# Conversation flow
objectives:
  - "Screen candidate for Python experience"
  - "Assess problem-solving ability"
predefined_questions:
  - "Tell me about your experience with Python."
```

### CLI Options

```bash
# Use a specific agent config
voxatar serve --agent examples/simple-agent.yaml

# Override the LLM model
voxatar serve --agent examples/simple-agent.yaml --model qwen2.5:7b

# Custom Ollama URL
voxatar serve --ollama-url http://192.168.1.100:11434/v1

# Show agent info
voxatar info --agent examples/simple-agent.yaml
```

## Architecture

```
Browser Client (WebRTC) ←→ FastAPI Signaling Server
                                ↓
                    Voice Agent Pipeline
                                ↓
                    ┌─────────────────┐
                    │   STT (Whisper)  │ ← Audio stream (faster-whisper + VAD)
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │   LLM (Ollama)   │ ← Text + system prompt + history
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │  TTS (Edge-TTS)  │ ← Text → Audio (streaming)
                    └────────┬────────┘
                             ↓
                    Audio stream back to browser via WebRTC
                    
                    WebSocket → Live transcript to browser
```

### Components (Phase 1)

| Component | Purpose | Implementation | Alternatives |
|-----------|---------|----------------|--------------|
| **STT** | Speech-to-text | faster-whisper | whisper.cpp, Moonshine |
| **LLM** | Conversation brain | Ollama (Llama 3.1) | Any OpenAI-compatible API |
| **TTS** | Text-to-speech | edge-tts | Kokoro, XTTS v2 (Phase 2) |
| **Transport** | Real-time audio | WebRTC (aiortc) | WebSocket fallback |
| **Frontend** | Web UI | React + Vite + TailwindCSS | — |

## Docker Setup

The `docker-compose.yml` runs the Voxatar server and connects to your host Ollama instance:

```yaml
services:
  voxatar:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Using Docker-Hosted Ollama

To run Ollama in Docker too, uncomment the `ollama` service in `docker-compose.yml`.

## Roadmap

- **Phase 1 (MVP):** ✅ Audio-only voice agent — STT → LLM → TTS pipeline over WebRTC
- **Phase 2 (v1.0):** Voice cloning (Kokoro/XTTS) + avatar video (MuseTalk) + knowledge base RAG (ChromaDB)
- **Phase 3 (v2.0):** Multi-agent handoffs, post-call analytics, integrations

See [ROADMAP.md](ROADMAP.md) for details.

## Project Structure

```
voxatar/
├── voxatar/          # Python package
│   ├── __init__.py   # Component registry
│   ├── cli.py        # CLI entry point (voxatar serve)
│   ├── config.py     # YAML config loading
│   ├── server.py     # FastAPI server + WebRTC signaling
│   ├── pipeline.py   # STT → LLM → TTS orchestration
│   ├── stt/          # Speech-to-text adapters
│   │   └── whisper_adapter.py
│   ├── llm/          # LLM adapters
│   │   └── ollama_adapter.py
│   ├── tts/          # Text-to-speech adapters
│   │   └── edge_tts_adapter.py
│   ├── transport/    # WebRTC transport
│   │   └── webrtc_adapter.py
│   └── avatar/       # Avatar (Phase 2)
├── web/              # React frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── CallPanel.tsx
│   │   │   ├── TranscriptView.tsx
│   │   │   └── Controls.tsx
│   │   └── hooks/
│   │       └── useWebRTC.ts
│   └── ...
├── docker/           # Docker setup
│   ├── Dockerfile
│   └── docker-compose.yml
├── examples/         # Example agents
│   ├── simple-agent.yaml
│   └── simple-agent.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Use Cases

- **Recruiting:** Automated screening interviews with dynamic follow-up questions
- **Sales:** Discovery calls that reference your product knowledge base
- **User Research:** Conduct interviews at scale with consistent question flows
- **Customer Support:** Voice agents that can access your docs and FAQs
- **Check-ins:** Automated wellness or status check-in calls
- **Education:** Interactive tutoring sessions

## Contributing

We welcome contributions! This is an early-stage project with many areas to build.

1. Check [open issues](https://github.com/cmcintosh/voxatar/issues)
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design
3. Check [ROADMAP.md](ROADMAP.md) for what's planned
4. Open an issue or PR

## License

MIT — see [LICENSE](LICENSE)

## Acknowledgments

- [Pipecat](https://github.com/pipecat-ai/pipecat) — real-time voice agent framework
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — fast Whisper inference
- [Ollama](https://ollama.ai) — local LLM serving
- [edge-tts](https://github.com/rany2/edge-tts) — Microsoft Edge TTS
- [aiortc](https://github.com/aiortc/aiortc) — WebRTC for Python
- [React](https://react.dev) + [Vite](https://vitejs.dev) + [TailwindCSS](https://tailwindcss.com)

---

**Star ⭐ this repo if you're interested in self-hosted AI voice agents!**