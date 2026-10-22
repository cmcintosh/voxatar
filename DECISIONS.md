# Decision Log

This document tracks architectural decisions made during Voxatar development. Each decision follows the ADR (Architecture Decision Record) format.

---

## ADR-001: Project Name — Voxatar
**Date:** 2026-10-21  
**Status:** Accepted  

**Context:** Need a catchy, brandable, unique name for an open-source voice agent project.

**Decision:** Name the project **Voxatar** — a portmanteau of "voice" + "avatar".

**Rationale:**
- Instantly communicates the two key differentiators: voice + avatar
- Short, memorable, easy to type
- No existing major projects with this name
- Domain and GitHub org availability

**Consequences:** The name establishes the brand identity for the project.

---

## ADR-002: Core Framework — Pipecat
**Date:** 2026-10-21  
**Status:** Proposed  

**Context:** Need a framework for real-time voice agent orchestration with WebRTC support.

**Decision:** Use **Pipecat** as the core framework, with custom adapters for local-first components.

**Rationale:**
- Purpose-built for real-time voice agents
- Built-in WebRTC/WebSocket transport
- Supports STT → LLM → TTS pipeline patterns
- Handles interrupt/barge-in
- Active community, MIT licensed

**Consequences:** Must learn Pipecat's adapter API. Components must conform to Pipecat's interface patterns.

---

## ADR-003: STT Engine — Whisper (whisper.cpp)
**Date:** 2026-10-21  
**Status:** Proposed  

**Context:** Need streaming speech-to-text for real-time conversation.

**Decision:** Use **whisper.cpp** as the primary STT engine, with adapter pattern for alternatives.

**Rationale:**
- Best accuracy-to-speed ratio for local inference
- 90+ language support
- MIT license, quantized models for CPU/GPU
- Well-maintained, active development

**Consequences:** Must handle streaming chunking via VAD. Higher latency than Piper but better accuracy.

---

## ADR-004: LLM Backend — Ollama
**Date:** 2026-10-21  
**Status:** Proposed  

**Context:** Need a local LLM for conversation management with streaming output.

**Decision:** Use **Ollama** as the primary LLM backend, supporting any OpenAI-compatible API.

**Rationale:**
- Easy model management (pull, run, switch)
- OpenAI-compatible API (drop-in replacement)
- Streaming support
- Supports Llama, Qwen, GLM, Mistral
- MIT licensed

**Consequences:** Ollama must be installed and running. Model selection affects quality and latency.

---

## ADR-005: TTS Engine — Dual Track (XTTS v2 + Kokoro)
**Date:** 2026-10-21  
**Status:** Proposed  

**Context:** Need TTS with voice cloning for the avatar feature, but XTTS v2 has non-commercial CPML license.

**Decision:** Support both **XTTS v2** (voice cloning, non-commercial) and **Kokoro-82M** (Apache 2.0, built-in voices) via adapter pattern.

**Rationale:**
- XTTS v2 provides voice cloning (key feature) but CPML limits commercial use
- Kokoro is Apache 2.0 (commercial-friendly) but no voice cloning
- Adapter pattern lets users choose based on their use case
- Can add F5-TTS or Chatterbox as additional options

**Consequences:** Must implement two TTS adapters. Users must understand license implications.

---

## ADR-006: Avatar Engine — MuseTalk
**Date:** 2026-10-21  
**Status:** Proposed  

**Context:** Need real-time lip-sync avatar video generation with commercial-friendly license.

**Decision:** Use **MuseTalk** as the primary avatar engine.

**Rationale:**
- 30+ FPS real-time generation
- MIT license (commercial OK)
- Audio-driven (single reference image + audio → video)
- Good quality for real-time applications

**Consequences:** Requires GPU for real-time performance. 256x256 resolution may need upscaling.

---

## ADR-007: Transport — WebRTC
**Date:** 2026-10-21  
**Status:** Proposed  

**Context:** Need real-time audio/video transport between browser and server.

**Decision:** Use **WebRTC** as the transport layer, managed via Pipecat.

**Rationale:**
- Browser-native support (no plugins needed)
- Sub-second latency for audio/video
- Bidirectional (send microphone, receive audio + video)
- Standard protocol with wide tooling support

**Consequences:** Must handle WebRTC signaling, ICE negotiation, and NAT traversal (STUN/TURN for remote access).

---

## ADR-008: License — MIT
**Date:** 2026-10-21  
**Status:** Accepted  

**Context:** Need an open-source license that encourages adoption and contribution.

**Decision:** License Voxatar under the **MIT License**.

**Rationale:**
- Most permissive common license
- Maximum adoption potential
- Compatible with most dependencies
- No copyleft requirements for users

**Consequences:** Note that some component dependencies (XTTS v2, F5-TTS) have non-commercial licenses. Users are responsible for compliance.

---

*Future decisions will be added as issues are resolved. See GitHub issues with `decision` label for pending decisions.*