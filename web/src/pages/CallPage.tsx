import { useState, useCallback, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useAudioSocket } from "../hooks/useAudioSocket";
import type { TranscriptEntry } from "../hooks/useAudioSocket";
import AvatarView from "../components/AvatarView";
import StateIndicator from "../components/StateIndicator";
import DebugPanel from "../components/DebugPanel";
import TranscriptView from "../components/TranscriptView";
import Controls from "../components/Controls";
import CallPanel from "../components/CallPanel";
import type { AgentInfo } from "../types";

export default function CallPage() {
  const { slug } = useParams<{ slug?: string }>();

  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
  const [consented, setConsented] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const onTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscript((prev) => [...prev, entry]);
  }, []);

  const {
    connectionState,
    pipelineState,
    analyser,
    isMuted,
    startCall,
    endCall,
    toggleMute,
  } = useAudioSocket({ onTranscript });

  // Fetch agent config on mount — use slug endpoint if slug is present
  useEffect(() => {
    const url = slug ? `/api/agents/${slug}` : "/api/agent";
    fetch(url)
      .then((res) => res.json())
      .then((data) => setAgentInfo(data))
      .catch((err) => {
        console.error("Failed to fetch agent config:", err);
        setErrorMsg("Failed to load agent configuration.");
      });
  }, [slug]);

  // Auto-clear error after 5 seconds
  useEffect(() => {
    if (errorMsg) {
      const timer = setTimeout(() => setErrorMsg(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [errorMsg]);

  const handleStartCall = useCallback(async () => {
    if (agentInfo?.require_consent && !consented) {
      setConsented(true);
    }
    setErrorMsg(null);
    try {
      await startCall();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to start call.");
    }
  }, [startCall, agentInfo, consented]);

  const handleEndCall = useCallback(() => {
    endCall();
    setTranscript([]);
  }, [endCall]);

  const handleMute = useCallback(() => {
    toggleMute();
  }, [toggleMute]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎙️</span>
            <h1 className="text-lg font-bold text-gray-900">Voxatar</h1>
          </div>
          <nav className="flex items-center gap-1">
            <Link
              to="/dashboard"
              className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Dashboard
            </Link>
            <Link
              to="/kb"
              className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Knowledge Base
            </Link>
          </nav>
        </div>
      </header>

      {/* Error banner */}
      {errorMsg && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-2">
          <div className="max-w-6xl mx-auto flex items-center gap-2 text-sm text-red-700">
            <span>⚠️</span>
            <span>{errorMsg}</span>
            <button
              onClick={() => setErrorMsg(null)}
              className="ml-auto text-red-400 hover:text-red-600"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Avatar + State + Controls */}
          <div className="flex flex-col gap-4">
            {/* Avatar view */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 flex flex-col items-center justify-center min-h-[320px]">
              <AvatarView
                pipelineState={pipelineState}
                analyser={analyser}
              />
              <div className="mt-3 w-full flex justify-center">
                <StateIndicator
                  state={pipelineState}
                  connectionState={connectionState}
                />
              </div>
            </div>

            {/* Agent info & consent */}
            <CallPanel
              agentInfo={agentInfo}
              consented={consented}
              onConsent={() => setConsented(true)}
            />

            {/* Controls */}
            <Controls
              connectionState={connectionState}
              isMuted={isMuted}
              onStartCall={handleStartCall}
              onEndCall={handleEndCall}
              onMute={handleMute}
            />
          </div>

          {/* Right: Transcript */}
          <div className="flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                Transcript
              </h2>
              {transcript.length > 0 && (
                <button
                  onClick={() => setTranscript([])}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  Clear
                </button>
              )}
            </div>
            <TranscriptView transcript={transcript as any} />
          </div>
        </div>

        {/* Debug panel */}
        <div className="mt-4">
          <DebugPanel
            messages={[]}
            connectionState={connectionState}
            pipelineState={pipelineState}
            audioBufferSize={0}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 px-6 py-3">
        <div className="max-w-6xl mx-auto text-center text-xs text-gray-400">
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