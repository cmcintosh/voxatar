# Open-Source Component Comparison

Detailed comparison of open-source alternatives for each Voxatar component.

## STT (Speech-to-Text)

| Feature | Whisper.cpp | FunASR | Moonshine | Piper |
|---------|------------|--------|-----------|-------|
| **License** | MIT | Apache 2.0 | Apache 2.0 | GPL |
| **Languages** | 90+ | CN + EN + multilingual | English only | 20+ |
| **Latency** | Medium (~300ms) | Low (~150ms) | Low (~200ms) | Very Low (~50ms) |
| **Accuracy** | High | High (CN) | Medium | Medium |
| **Streaming** | Yes (VAD + chunks) | Yes | Yes | No (batch) |
| **GPU Required** | Optional | Yes | No | No |
| **Model Size** | 75MB-3GB | ~1GB | 27-61MB | 30-100MB |
| **Commercial Use** | ✅ | ✅ | ✅ | ⚠️ GPL |

**Recommendation:** Whisper.cpp for general use. Piper for ultra-low-latency English-only. FunASR for Chinese-primary.

---

## LLM (Conversation Brain)

| Feature | Ollama | vLLM | LM Studio | llama.cpp |
|---------|--------|------|-----------|-----------|
| **License** | MIT | Apache 2.0 | Freeware | MIT |
| **API** | OpenAI-compatible | OpenAI-compatible | OpenAI-compatible | Custom |
| **Streaming** | Yes (SSE) | Yes (SSE) | Yes | Yes |
| **Model Support** | Llama, Qwen, GLM, Mistral | Llama, Qwen, GLM, Mistral | Llama, Qwen, GLM | Llama, Qwen, GLM |
| **Multi-GPU** | No | Yes | No | No |
| **Ease of Use** | Excellent | Good | Excellent | Fair |
| **Production Ready** | Yes | Yes | Hobbyist | Yes |
| **Commercial Use** | ✅ | ✅ | ✅ | ✅ |

**Recommendation:** Ollama for ease of use and local development. vLLM for production multi-GPU deployments.

---

## TTS + Voice Cloning

| Feature | XTTS v2 | F5-TTS | Chatterbox | Kokoro-82M | Piper | CosyVoice |
|---------|---------|--------|------------|------------|-------|-----------|
| **License** | CPML (non-commercial) | CC-BY-NC | MIT? | Apache 2.0 | GPL | Apache 2.0 |
| **Voice Cloning** | ✅ (6s sample) | ✅ (5s sample) | ✅ | ❌ | Limited | ✅ |
| **Languages** | 17 | EN + CN | EN | EN + JP | 20+ | CN + EN |
| **Quality** | High | Highest | Good | Good | Medium | High |
| **Speed** | Medium | Slow | Medium | Fast | Fast | Medium |
| **Streaming** | Yes | No | Yes | Yes | Yes | Yes |
| **Commercial Use** | ❌ | ❌ | ✅ | ✅ | ⚠️ GPL | ✅ |

**Recommendation:**
- **For non-commercial/demo:** XTTS v2 (best voice cloning quality)
- **For commercial:** Kokoro (Apache 2.0, fast) + CosyVoice (multilingual + cloning)
- **For highest quality (non-commercial):** F5-TTS

**License Note:** Voxatar uses an adapter pattern — users choose their TTS engine and are responsible for compliance with each engine's license.

---

## Avatar / Lip-Sync

| Feature | MuseTalk | SadTalker | LatentSync | LivePortrait | Wav2Lip |
|---------|----------|-----------|------------|--------------|---------|
| **License** | MIT | Apache 2.0 | Apache 2.0 | MIT | Non-commercial |
| **FPS** | 30+ | 15-20 | 20-25 | 30+ | 25-30 |
| **Input** | Image + Audio | Image + Audio | Image + Audio | Image + Audio | Image + Audio |
| **Quality** | Good | Good | High | Highest | Medium |
| **Head Movement** | Minimal | Yes | Minimal | Yes (expressive) | No |
| **Real-time** | Yes | No | Near | Yes | No |
| **Resolution** | 256x256 | 256x256 | 256x256 | 512x512 | 96x96 |
| **Commercial Use** | ✅ | ✅ | ✅ | ✅ | ❌ |

**Recommendation:** MuseTalk for real-time performance with commercial license. LivePortrait for highest quality if FPS allows.

---

## Transport / Framework

| Feature | Pipecat | Custom (aiortc) | LiveKit |
|---------|---------|----------------|---------|
| **License** | BSD-2-Clause | BSD-3-Clause | Apache 2.0 |
| **Purpose** | Voice agent framework | WebRTC library | Real-time video platform |
| **STT/TTS/LLM** | Built-in adapters | DIY | DIY |
| **WebRTC** | Yes | Yes | Yes |
| **WebSocket** | Yes | Yes | No |
| **Interrupt Handling** | Yes | DIY | Yes |
| **Multi-agent** | Yes | DIY | Yes |
| **Community** | Growing | Small | Large |

**Recommendation:** Pipecat for fastest development. Custom aiortc for maximum control. LiveKit if already using their platform.

---

## Knowledge Base / RAG

| Feature | ChromaDB | FAISS | SQLite-vec | Qdrant |
|---------|----------|-------|------------|--------|
| **License** | Apache 2.0 | MIT | MIT | Apache 2.0 |
| **Storage** | File-based | In-memory | SQLite extension | Server |
| **Embeddings** | Built-in | DIY | DIY | Built-in |
| **Scalability** | Medium | High | Low | High |
| **Ease of Use** | High | Medium | High | Medium |
| **Commercial Use** | ✅ | ✅ | ✅ | ✅ |

**Embedding Models:**

| Model | License | Size | Languages |
|-------|--------|------|-----------|
| nomic-embed-text | Apache 2.0 | 137MB | English |
| BGE-small | MIT | 130MB | EN + CN |
| multilingual-e5 | MIT | 560MB | 100+ |

**Recommendation:** ChromaDB + nomic-embed-text (via Ollama) for simplicity. SQLite-vec for minimal dependencies.

---

## Summary: Recommended Stack

| Component | Primary | Commercial Alternative | Low-Resource Alternative |
|-----------|---------|----------------------|-------------------------|
| STT | Whisper.cpp | Whisper.cpp | Piper |
| LLM | Ollama (Llama 3.1) | Ollama (Llama 3.1) | Ollama (Qwen 2.5 3B) |
| TTS | XTTS v2 (non-commercial) | Kokoro-82M | Piper |
| Avatar | MuseTalk | MuseTalk | SadTalker |
| Transport | Pipecat (WebRTC) | Pipecat (WebRTC) | Pipecat (WebRTC) |
| RAG | ChromaDB + nomic-embed | ChromaDB + nomic-embed | SQLite-vec + nomic-embed |