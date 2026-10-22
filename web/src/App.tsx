import { useState, useCallback, useRef, useEffect } from "react";
import { useWebRTC, ConnectionState } from "./hooks/useWebRTC";
import CallPanel from "./components/CallPanel";
import TranscriptView from "./components/TranscriptView";
import Controls from "./components/Controls";

export interface TranscriptEntry {
  type: "user" | "agent" | "system";
  text: string;
  timestamp: number;
  isPartial?: boolean;
}

export interface AgentInfo {
  name: string;
  role: string;
  organization: string;
  objectives: string[];
  predefined_questions: string[];
  require_consent: boolean;
  consent_message: string;
  max_duration: number;
  tts_voice: string | null;
  available_voices: { id: string; name: string; language: string }[];
}

export default function App() {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [consented, setConsented] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const onTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscript((prev) => [...prev, entry]);
  }, []);

  const { connectionState, startCall, endCall, toggleMute } = useWebRTC({
    onTranscript,
  });

  // Fetch agent config on mount
  useEffect(() => {
    fetch("/api/agent")
      .then((res) => res.json())
      .then((data) => setAgentInfo(data))
      .catch((err) => console.error("Failed to fetch agent config:", err));
  }, []);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const handleStartCall = useCallback(async () => {
    if (agentInfo?.require_consent && !consented) {
      setConsented(true);
    }
    await startCall();
  }, [startCall, agentInfo, consented]);

  const handleEndCall = useCallback(async () => {
    await endCall();
    setTranscript([]);
  }, [endCall]);

  const handleMute = useCallback(async () => {
    await toggleMute();
    setIsMuted((prev) => !prev);
  }, [toggleMute]);

  const handleBargeIn = useCallback(() => {
    // Send barge-in via WebSocket
    const ws = (window as any).__voxatar_ws as WebSocket | undefined;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "barge_in" }));
    }
  }, []);

  const inCall = connectionState === "connected";

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎙️</span>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Voxatar</h1>
              <p className="text-sm text-gray-500">
                {agentInfo?.name || "AI Voice Agent"}
                {agentInfo?.role ? ` · ${agentInfo.role}` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                inCall ? "bg-green-500 animate-pulse" : "bg-gray-300"
              }`}
            />
            <span className="text-sm text-gray-600">
              {inCall ? "Connected" : "Idle"}
            </span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left: Call panel + controls */}
        <div className="flex flex-col gap-6">
          <CallPanel
            agentInfo={agentInfo}
            connectionState={connectionState}
            consented={consented}
            onConsent={() => setConsented(true)}
          />
          <Controls
            connectionState={connectionState}
            isMuted={isMuted}
            onStartCall={handleStartCall}
            onEndCall={handleEndCall}
            onMute={handleMute}
            onBargeIn={handleBargeIn}
          />
        </div>

        {/* Right: Transcript */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Live Transcript
            </h2>
            {transcript.length > 0 && (
              <button
                onClick={() => setTranscript([])}
                className="text-sm text-gray-400 hover:text-gray-600"
              >
                Clear
              </button>
            )}
          </div>
          <TranscriptView transcript={transcript} />
          <div ref={transcriptEndRef} />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto text-center text-sm text-gray-400">
          Voxatar — Open-source AI voice agents ·{" "}
          <a
            href="https://github.com/cmcintosh/voxatar"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-600"
          >
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}