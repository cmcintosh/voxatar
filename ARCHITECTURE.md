# Architecture

## Overview

Voxatar is a real-time voice agent system that combines speech-to-text (STT), large language model (LLM) reasoning, text-to-speech (TTS) with voice cloning, and AI avatar video generation — all running locally on your own infrastructure.

The system is designed as a pipeline: audio comes in from a browser client via WebRTC, gets transcribed, reasoned about by an LLM, converted back to speech (optionally with a cloned voice), and optionally rendered as avatar video — all streamed back to the client in real-time.

## System Diagram

```
                         ┌──────────────────┐
                         │  Browser Client   │
                         │  (React/WebRTC)   │
                         └────────┬─────────┘
                                  │ WebRTC (audio + video)
                                  │
                         ┌────────▼─────────┐
                         │ Signaling Server  │
                         │ (WebSocket + SDP) │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │  Agent Pipeline   │
                         │  (Orchestrator)   │
                         └────────┬─────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
     ┌────────▼────────┐ ┌───────▼───────┐ ┌────────▼────────┐
     │   STT Engine     │ │  LLM Engine   │ │   TTS Engine    │
     │                  │ │               │ │                 │
     │ • Whisper.cpp    │ │ • Ollama      │ │ • XTTS v2       │
     │ • FunASR         │ │ • vLLM        │ │ • F5-TTS        │
     │ • Moonshine      │ │ • OpenAI API  │ │ • Kokoro        │
     │ • Piper          │ │ • Any compat  │ │ • Piper         │
     └────────┬────────┘ └───────┬───────┘ └────────┬────────┘
              │                   │                   │
              │           ┌───────▼───────┐           │
              │           │ Knowledge Base │           │
              │           │ (RAG / Vector) │           │
              │           │ • Local docs   │           │
              │           │ • FAQs         │           │
              │           │ • Embeddings   │           │
              │           └───────────────┘           │
              │                                        │
              │              ┌─────────────────────────┘
              │              │
              │     ┌────────▼────────┐
              │     │  Avatar Engine   │
              │     │                  │
              │     │ • MuseTalk       │
              │     │ • SadTalker      │
              │     │ • LatentSync     │
              │     │ • LivePortrait   │
              │     └────────┬────────┘
              │              │
              │     ┌────────▼────────┐
              │     │  Video Renderer  │
              │     │  (frame → WebRTC)│
              │     └────────┬────────┘
              │              │
              └──────────────┘
                             
Post-call:
  Audio recording → Whisper transcription → LLM summarization → Export (JSON, markdown, PDF)
```

## Component Specifications

### 1. STT (Speech-to-Text)

**Purpose:** Convert incoming audio stream to text in real-time.

**Requirements:**
- Streaming/chunked processing (not batch)
- Low latency (< 300ms ideal)
- Multi-language support
- Local inference (no cloud API calls)

**Recommended: Whisper (whisper.cpp)**
- C++ implementation of OpenAI's Whisper model
- Quantized models (ggml) for CPU/GPU inference
- Streaming mode via VAD (Voice Activity Detection) + chunking
- 90+ language support
- MIT license

**Adapter Pattern:**
```python
class STTEngine(ABC):
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Stream audio in, get text chunks out."""
        pass
```

**Alternatives:**
| Engine | Latency | Languages | License | Notes |
|--------|---------|-----------|--------|-------|
| Whisper.cpp | Medium | 90+ | MIT | Best all-rounder |
| FunASR | Low | CN + EN | Apache 2.0 | Fastest for Chinese |
| Moonshine | Low | EN | Apache 2.0 | Lightweight, fast |
| Piper | Very Low | 20+ | GPL | Fastest, limited accuracy |

### 2. LLM (Conversation Brain)

**Purpose:** Generate conversational responses based on transcript, system prompt, and knowledge base.

**Requirements:**
- Streaming output (token-by-token for low TTS latency)
- System prompt support (agent personality, instructions)
- Context window (conversation history + knowledge base chunks)
- Tool/function calling (for actions like scheduling, lookups)
- Local inference preferred

**Recommended: Ollama**
- Easy local model management (`ollama pull llama3.1`)
- OpenAI-compatible API (`http://localhost:11434/v1`)
- Streaming support via SSE
- Supports Llama, Qwen, GLM, Mistral, and more
- MIT licensed

**Conversation Management:**
```python
class LLMEngine(ABC):
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str,
        knowledge_context: str | None = None,
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM."""
        pass
```

**System Prompt Structure:**
```
You are {agent_name}, a {role} for {organization}.

Your objectives:
{objectives}

Questions to ask:
{predefined_questions}

Knowledge base context:
{rag_context}

Conversation guidelines:
- Keep responses concise (1-3 sentences for voice)
- Ask follow-up questions based on responses
- Be natural and conversational
- Reference knowledge base when relevant
```

### 3. TTS (Text-to-Speech + Voice Cloning)

**Purpose:** Convert LLM text output to natural-sounding speech, optionally using a cloned voice.

**Requirements:**
- Low latency (< 500ms to first audio)
- Voice cloning from short sample (6-10 seconds)
- Multi-language support
- Streaming output (audio chunks as text arrives)
- Emotion/prosody control (nice to have)

**Recommended: XTTS v2 (Coqui)**
- 6-second voice cloning
- 17 languages
- Streaming support
- ⚠️ CPML license (non-commercial only) — see decision ticket

**Commercial Alternative: Kokoro-82M**
- Apache 2.0 license
- 82M parameters (very fast)
- No voice cloning (built-in voices only)
- Best for commercial deployments

**Adapter Pattern:**
```python
class TTSEngine(ABC):
    @abstractmethod
    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice_id: str | None = None,
        language: str = "en",
    ) -> AsyncIterator[bytes]:
        """Stream text in, get audio chunks out."""
        pass
    
    @abstractmethod
    async def clone_voice(self, audio_sample: bytes, name: str) -> str:
        """Clone a voice from an audio sample. Returns voice_id."""
        pass
```

### 4. Avatar (Lip-Sync Video Generation)

**Purpose:** Generate video frames of an AI avatar speaking the TTS audio, with accurate lip synchronization.

**Requirements:**
- Real-time generation (30 FPS target)
- Audio-driven (input: face image + audio → output: video frames)
- Commercial-friendly license preferred
- Consistent identity across frames

**Recommended: MuseTalk (Tencent)**
- 30+ FPS real-time lip sync
- MIT license (commercial OK)
- Audio-driven facial animation
- Works with single reference image
- Good quality at 256x256 resolution

**Pipeline:**
```
Input: reference_image (photo) + audio_stream
  → MuseTalk inference
  → Video frames (30 FPS)
  → WebRTC video track
```

**Alternatives:**
| Engine | FPS | License | Input | Quality |
|--------|-----|---------|-------|---------|
| MuseTalk | 30+ | MIT | Image + Audio | Good |
| SadTalker | 15-20 | Apache 2.0 | Image + Audio | Good (head movement) |
| LatentSync | 20-25 | Apache 2.0 | Image + Audio | High (diffusion) |
| LivePortrait | 30+ | MIT | Image + Audio | High (expressive) |
| Wav2Lip | 25-30 | Non-commercial | Image + Audio | Medium |

### 5. Transport (WebRTC)

**Purpose:** Stream audio and video between browser client and the agent pipeline in real-time.

**Recommended: Pipecat framework**
- Built on WebRTC + WebSocket
- Handles SDP negotiation, ICE candidates
- Audio/video track management
- Interrupt handling (barge-in)
- Multi-agent support

**Connection Flow:**
1. Browser opens page → connects to signaling server via WebSocket
2. Browser creates peer connection → sends SDP offer
3. Server responds with SDP answer
4. ICE candidate exchange completes
5. Audio flows: browser → server (STT input)
6. Audio flows: server → browser (TTS output)
7. Video flows: server → browser (avatar output)

### 6. Knowledge Base / RAG

**Purpose:** Give the agent context from local documents, FAQs, and structured data.

**Architecture:**
```
Documents (PDF, TXT, MD, DOCX)
  → Chunking (512-1024 tokens, overlap 100)
  → Embedding (nomic-embed-text via Ollama)
  → Vector store (ChromaDB / FAISS / SQLite-vec)
  → Retrieval at conversation time
  → Injected into LLM system prompt
```

**Supported sources:**
- Plain text / Markdown
- PDF documents
- Web URLs (fetched and parsed)
- Structured FAQs (JSON/YAML)
- Pre-existing embeddings

### 7. Post-Call Processing

**Purpose:** After the call ends, generate transcripts, summaries, and actionable outputs.

**Pipeline:**
```
Call recording (audio)
  → Full Whisper transcription (high accuracy mode)
  → LLM summarization
  → Action item extraction
  → Scorecard generation (if structured interview)
  → Export: JSON, Markdown, PDF
  → Optional: email recap, CRM sync
```

**Outputs:**
- Full transcript with timestamps
- Executive summary (2-3 paragraphs)
- Action items (checkbox list)
- Key insights / sentiment analysis
- Scorecard (for structured interviews)

## Data Flow

### Real-time Conversation Flow

```
1. User speaks → Browser captures audio via WebRTC
2. Audio stream → STT engine (streaming transcription)
3. Partial/final transcripts → Conversation manager
4. Conversation manager → LLM (with context, system prompt, RAG)
5. LLM tokens → TTS engine (streaming synthesis)
6. Audio output → Avatar engine (lip-sync frame generation)
7. Audio + Video → WebRTC tracks → Browser
8. Browser plays audio + renders video

Latency budget: < 1.5s end-to-end (ideally < 800ms)
```

### Interruption Handling

```
1. User starts speaking while agent is talking
2. STT detects speech → signals interruption
3. TTS output immediately stopped
4. Avatar animation stopped
5. New user utterance processed
6. Agent responds to new input
```

## Configuration

Voxatar uses YAML configuration for agent definitions:

```yaml
# example-agent.yaml
agent:
  name: "Interview Bot"
  role: "Technical Recruiter"
  organization: "Acme Corp"
  
  voice:
    engine: xtts
    voice_id: "cloned_voice_1"  # or built-in voice name
    language: "en"
  
  avatar:
    engine: musetalk
    reference_image: "./avatars/recruiter.png"
    
  llm:
    engine: ollama
    model: "llama3.1:8b"
    temperature: 0.7
    max_tokens: 150  # keep responses short for voice
    
  stt:
    engine: whisper
    model: "base"  # tiny, base, small, medium, large
    language: "en"
    
  knowledge_base:
    sources:
      - "./docs/product-faq.md"
      - "./docs/company-info.pdf"
    chunk_size: 512
    overlap: 100
    
  conversation:
    objectives:
      - "Screen candidate for technical skills"
      - "Assess cultural fit"
    predefined_questions:
      - "Tell me about your experience with Python."
      - "Describe a challenging project you worked on."
      - "What are your salary expectations?"
    max_duration: 1800  # 30 minutes
    
  post_call:
    generate_summary: true
    extract_action_items: true
    generate_scorecard: true
    export_format: "markdown"
```

## Deployment

### Docker (Recommended)

```dockerfile
# docker/Dockerfile
FROM python:3.11-slim

# System deps for audio/video
RUN apt-get update && apt-get install -y \
    ffmpeg portaudio19-dev libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY . /app
WORKDIR /app
RUN pip install -e .

EXPOSE 8080
CMD ["voxatar", "serve", "--host", "0.0.0.0", "--port", "8080"]
```

### Requirements

- **GPU:** NVIDIA GPU with 8GB+ VRAM (for Whisper + LLM + TTS + Avatar)
- **CPU fallback:** Possible but significantly higher latency
- **RAM:** 16GB minimum, 32GB recommended
- **Storage:** 10GB for models, more for knowledge base
- **Network:** Local network for browser access

### Model Sizes

| Component | Model | Size |
|-----------|-------|------|
| STT | Whisper base | ~150MB |
| STT | Whisper medium | ~1.5GB |
| LLM | Llama 3.1 8B | ~5GB |
| LLM | Qwen 2.5 7B | ~4.5GB |
| TTS | XTTS v2 | ~1.8GB |
| Avatar | MuseTalk | ~500MB |
| Embeddings | nomic-embed-text | ~140MB |

## Security Considerations

- **Voice cloning consent:** Require explicit consent before cloning a voice
- **Data handling:** All data stays local by default — no cloud transmission
- **Access control:** WebRTC connections should be authenticated
- **Recording consent:** Inform participants when calls are recorded
- **Model safety:** LLM output should be filtered for harmful content

## Extensibility

Voxatar uses an adapter pattern for all components. To add a new STT engine:

```python
from voxatar.stt import STTEngine

class MyCustomSTT(STTEngine):
    async def transcribe_stream(self, audio_stream):
        async for chunk in audio_stream:
            text = my_custom_inference(chunk)
            yield text
```

Register it:
```python
from voxatar import registry
registry.register_stt("my-custom", MyCustomSTT)
```

## Performance Targets

| Metric | Target | Ideal |
|--------|--------|-------|
| End-to-end latency | < 1.5s | < 800ms |
| STT latency | < 300ms | < 150ms |
| LLM first token | < 500ms | < 200ms |
| TTS first audio | < 400ms | < 200ms |
| Avatar FPS | 30 | 30 |
| Concurrent agents | 1 (MVP) | 10+ |

## References

- [Pipecat Documentation](https://docs.pipecat.ai)
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
- [Ollama](https://ollama.ai)
- [XTTS v2](https://github.com/coqui-ai/TTS)
- [MuseTalk](https://github.com/TMElyralab/MuseTalk)