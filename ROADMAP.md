# Roadmap

## Phase 1: MVP — Audio-Only Voice Agent
**Target: Q1 2027**

Get a working voice agent that can conduct a conversation over WebRTC with STT → LLM → TTS pipeline.

### Milestone 1.1: Project Skeleton
- [x] Repo created with architecture docs
- [ ] Python package structure with abstract base classes
- [ ] Configuration system (YAML-based agent definitions)
- [ ] CLI entry point (`voxatar serve`)
- [ ] Basic logging and error handling

### Milestone 1.2: STT Integration
- [ ] Whisper.cpp adapter (streaming mode)
- [ ] VAD (Voice Activity Detection) for chunking
- [ ] Partial vs final transcript handling
- [ ] Language auto-detection

### Milestone 1.3: LLM Integration
- [ ] Ollama adapter (OpenAI-compatible API)
- [ ] Streaming token generation
- [ ] System prompt template system
- [ ] Conversation history management
- [ ] Function/tool calling support

### Milestone 1.4: TTS Integration
- [ ] Kokoro adapter (Apache 2.0, built-in voices)
- [ ] XTTS v2 adapter (voice cloning, non-commercial)
- [ ] Streaming audio output
- [ ] SSML support for prosody control

### Milestone 1.5: Transport Layer
- [ ] WebRTC signaling server (WebSocket + SDP)
- [ ] Audio track management (send/receive)
- [ ] Browser client (minimal — microphone + audio playback)
- [ ] Interrupt/barge-in handling

### Milestone 1.6: Pipeline Orchestration
- [ ] STT → LLM → TTS pipeline wiring
- [ ] Turn detection (when to respond vs listen)
- [ ] Error recovery (STT failure, LLM timeout, etc.)
- [ ] Graceful shutdown

**Deliverable:** A user can open a browser, talk to a voice agent, and get spoken responses in real-time.

---

## Phase 2: v1.0 — Voice Cloning + Avatar + Knowledge Base
**Target: Q2 2027**

Add voice cloning, AI avatar video, and knowledge base RAG.

### Milestone 2.1: Voice Cloning
- [ ] Voice cloning UI (upload 6+ second audio sample)
- [ ] XTTS v2 voice cloning pipeline
- [ ] Voice profile management (save, list, delete)
- [ ] Consent recording and storage
- [ ] Voice quality validation

### Milestone 2.2: Avatar Video
- [ ] MuseTalk integration
- [ ] Reference image upload (face photo)
- [ ] Real-time avatar video generation
- [ ] WebRTC video track to browser
- [ ] Avatar preset library

### Milestone 2.3: Knowledge Base / RAG
- [ ] Document ingestion (PDF, TXT, MD, DOCX)
- [ ] Chunking and embedding (nomic-embed-text)
- [ ] Vector store (ChromaDB or SQLite-vec)
- [ ] Retrieval at conversation time
- [ ] RAG context injection into LLM prompts
- [ ] Knowledge base management UI

### Milestone 2.4: Frontend Client
- [ ] React web client with WebRTC
- [ ] Avatar video display
- [ ] Real-time transcript view
- [ ] Call controls (start, stop, mute)
- [ ] Agent configuration UI
- [ ] Shareable agent links (URL → join call)

### Milestone 2.5: Conversation Flow
- [ ] Predefined question flows (YAML-defined)
- [ ] Dynamic follow-up generation
- [ ] Structured interview mode
- [ ] Free-form conversation mode
- [ ] Timeout and session management

**Deliverable:** A user can configure an agent with a cloned voice, avatar, and knowledge base, share a link, and conduct a video voice call.

---

## Phase 3: v2.0 — Post-Call + Multi-Agent + Integrations
**Target: Q3 2027**

Add post-call analytics, multi-agent support, and external integrations.

### Milestone 3.1: Post-Call Processing
- [ ] Full call transcription (high-accuracy Whisper)
- [ ] LLM-powered summarization
- [ ] Action item extraction
- [ ] Scorecard generation (structured interviews)
- [ ] Export: JSON, Markdown, PDF
- [ ] Recap email generation

### Milestone 3.2: Multi-Agent Support
- [ ] Agent handoff (transfer call to another agent)
- [ ] Multi-agent orchestration (specialist agents)
- [ ] Agent routing logic
- [ ] Shared conversation context

### Milestone 3.3: Integrations
- [ ] Webhook system (post-call events)
- [ ] CRM sync (HubSpot, Salesforce)
- [ ] ATS sync (Greenhouse, Lever)
- [ ] Calendar integration
- [ ] Slack notifications

### Milestone 3.4: Distribution
- [ ] Embeddable widget (iframe)
- [ ] QR code generation
- [ ] Calendar invite integration
- [ ] Agent templates marketplace

### Milestone 3.5: Production Hardening
- [ ] Authentication and access control
- [ ] Rate limiting
- [ ] Monitoring and metrics (Prometheus)
- [ ] Health checks
- [ ] Horizontal scaling support
- [ ] Load testing

**Deliverable:** A production-ready, self-hosted voice agent platform with analytics, integrations, and multi-agent support.

---

## Backlog (Future)

- [ ] Mobile app (React Native)
- [ ] Plugin system for custom components
- [ ] Fine-tuning pipeline for domain-specific models
- [ ] Real-time translation (multi-language calls)
- [ ] Emotion detection and response
- [ ] Voice activity detection improvements
- [ ] Acoustic echo cancellation
- [ ] Noise suppression
- [ ] Multi-participant calls (3+ people + agent)
- [ ] Agent analytics dashboard
- [ ] A/B testing for agent configurations