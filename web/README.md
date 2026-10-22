# Voxatar Web Client

This directory contains the frontend web client for Voxatar voice agents.

## Planned Stack

- **React 18+** with Vite for build tooling
- **WebRTC** for real-time audio/video
- **TailwindCSS** for styling
- **TypeScript** for type safety

## Features (Planned)

- Microphone capture and WebRTC audio streaming
- Avatar video display with real-time lip-sync
- Live transcript view
- Call controls (start, stop, mute, end)
- Agent configuration interface
- Voice cloning upload UI
- Knowledge base management
- Shareable agent links

## Structure (Planned)

```
web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── AvatarView.tsx
│   │   ├── TranscriptView.tsx
│   │   ├── CallControls.tsx
│   │   └── AgentConfig.tsx
│   ├── hooks/
│   │   └── useWebRTC.ts
│   ├── lib/
│   │   ├── signaling.ts
│   │   └── api.ts
│   └── styles/
│       └── global.css
└── public/
    └── avatar-placeholder.png
```

## Status

🚧 **Not yet implemented** — Frontend development begins in Phase 2 of the roadmap.