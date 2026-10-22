# Fireflies.ai Voice Agents — Reverse Engineering Analysis

## Overview

Fireflies.ai offers "AI Voice Agents" that conduct live, two-way voice calls on behalf of users. This document analyzes their publicly available features and infers the underlying technology stack.

## Feature Analysis

### 1. Live Two-Way Voice Calls
**What they do:** AI agent conducts a real-time voice conversation with a human participant.

**Inferred implementation:**
- WebRTC for audio transport (browser-to-browser or browser-to-server)
- Streaming STT for real-time transcription
- LLM for conversation management
- Streaming TTS for real-time speech synthesis
- Turn-taking detection (VAD + silence threshold)

### 2. Automatic Meeting Joining
**What they do:** Agent joins scheduled meetings (Zoom, Google Meet, Teams) or can be joined via direct link.

**Inferred implementation:**
- Meeting platform SDKs/bots for joining scheduled calls
- Direct link → WebRTC session for standalone calls
- Calendar integration for scheduling

### 3. Natural Conversation with Dynamic Follow-ups
**What they do:** Agent asks predefined questions, follows up based on responses, references uploaded knowledge base.

**Inferred implementation:**
- System prompt with predefined questions and objectives
- RAG (Retrieval-Augmented Generation) over uploaded documents
- Conversation state tracking for question flow
- LLM generates contextual follow-ups

### 4. Voice Cloning
**What they do:** Users can clone their voice from a 6-second sample or choose from 25+ built-in voices in 32+ languages.

**Inferred implementation:**
- Cloud TTS with voice cloning capability (likely ElevenLabs or custom model)
- Voice profile storage and management
- Voice sample validation (quality, duration, clarity)
- Multi-language TTS engine

### 5. AI Avatar with Lip-Sync
**What they do:** AI avatar presents a video feed with real-time lip-sync matching the spoken audio.

**Inferred implementation:**
- Audio-driven facial animation (audio → lip movement → video frames)
- Likely HeyGen-style or custom lip-sync model
- WebRTC video track for streaming to participant
- Pre-loaded avatar images or user-uploaded photos

### 6. Low Latency Real-Time Conversation
**What they do:** Conversation feels natural with minimal delay.

**Inferred implementation:**
- Streaming everything (STT chunks, LLM tokens, TTS audio)
- Early response triggering (start TTS before LLM finishes)
- VAD-based turn detection
- Optimized inference pipeline (GPU acceleration)

### 7. Post-Call Processing
**What they do:** Automatic transcripts, summaries, scorecards, action items, AI follow-ups.

**Inferred implementation:**
- Full recording → high-accuracy transcription (batch Whisper)
- LLM summarization with structured prompts
- Action item extraction (LLM with function calling or structured output)
- Scorecard generation (rubric-based LLM evaluation)
- Follow-up email generation

### 8. Integrations (AI Skills)
**What they do:** Sync to ATS, CRM, and other tools.

**Inferred implementation:**
- OAuth-based integrations with common platforms
- Webhook system for post-call events
- API connectors (Salesforce, HubSpot, Greenhouse, Lever)
- Custom skill definitions (API calls triggered by LLM)

### 9. Distribution
**What they do:** Shareable via link, embed code, QR code, calendar invite.

**Inferred implementation:**
- Unique URL per agent session
- Embeddable iframe widget
- QR code generation (standard library)
- Calendar invite with meeting link (ICS generation)

### 10. Session Management
**What they do:** 5-40 minute sessions, visibility/privacy controls, recap emails.

**Inferred implementation:**
- Session lifecycle management (start, monitor, end)
- Timeout handling
- Privacy controls (who can see recordings, transcripts)
- Automated recap email generation and sending

## Inferred Technology Stack

| Component | Likely Technology | Confidence |
|-----------|------------------|------------|
| STT | Whisper or Deepgram (streaming) | High |
| LLM | GPT-4-class model | High |
| TTS | ElevenLabs or custom voice cloning | Medium |
| Avatar | HeyGen-style or custom lip-sync | Medium |
| Transport | WebRTC | High |
| Backend | Cloud-based (AWS/GCP) orchestration | High |
| Storage | Cloud storage for recordings/transcripts | High |
| Frontend | React-based web app | High |

## Key Differentiators for Voxatar

Based on this analysis, Voxatar should prioritize:

1. **Full local inference** — no cloud dependencies for core pipeline
2. **Voice cloning** — match Fireflies' 6-second cloning capability
3. **Real-time avatar** — lip-sync video as a differentiator
4. **Knowledge base RAG** — local document ingestion
5. **Post-call processing** — transcripts, summaries, action items
6. **Browser-based client** — no app install required

## What We Can't Determine

- Exact latency numbers
- Specific model sizes/architectures
- How they handle interruptions/barge-in
- Quality of voice cloning vs. real voice
- Accuracy of transcription in noisy environments
- How conversation flow state is managed
- Whether LLM is fine-tuned for conversation or uses prompt engineering