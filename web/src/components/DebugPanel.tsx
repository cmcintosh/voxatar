import { useState, useEffect, useRef } from "react";

interface DebugMessage {
  type: string;
  data: string;
  timestamp: number;
}

interface DebugPanelProps {
  messages: DebugMessage[];
  connectionState: string;
  pipelineState: string;
  audioBufferSize: number;
}

export default function DebugPanel({
  messages,
  connectionState,
  pipelineState,
  audioBufferSize,
}: DebugPanelProps) {
  const [collapsed, setCollapsed] = useState(true);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (!collapsed && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, collapsed]);

  const last10 = messages.slice(-10);

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Determine direction from message type prefix
  const getDirection = (type: string): string => {
    if (type.startsWith("sent_")) return "→";
    if (type.startsWith("recv_")) return "←";
    return "·";
  };

  const getTypeLabel = (type: string): string => {
    return type.replace(/^(sent_|recv_)/, "");
  };

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
      {/* Header / toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-slate-800/50 transition-colors"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-slate-300">
          <span className="text-xs">{collapsed ? "▸" : "▾"}</span>
          Debug Panel
        </span>
        <span className="flex items-center gap-3 text-xs text-slate-500">
          <span>WS: {connectionState}</span>
          <span>Pipeline: {pipelineState}</span>
        </span>
      </button>

      {/* Expanded content */}
      {!collapsed && (
        <div className="border-t border-slate-700 px-4 py-3 space-y-3">
          {/* Status grid */}
          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">WebSocket</span>
              <span
                className={
                  connectionState === "connected"
                    ? "text-green-400"
                    : connectionState === "failed"
                    ? "text-red-400"
                    : "text-yellow-400"
                }
              >
                {connectionState}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Pipeline</span>
              <span className="text-blue-400">{pipelineState}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Audio Buffer</span>
              <span className="text-slate-300">{formatSize(audioBufferSize)}</span>
            </div>
          </div>

          {/* Message log */}
          <div>
            <div className="text-xs text-slate-500 mb-1.5">Last {last10.length} messages</div>
            <div
              ref={scrollRef}
              className="max-h-48 overflow-y-auto rounded bg-slate-950/50 border border-slate-800 p-2 font-mono text-xs space-y-1"
            >
              {last10.length === 0 && (
                <div className="text-slate-600 italic">No messages yet…</div>
              )}
              {last10.map((msg, i) => (
                <div key={i} className="flex gap-2 text-slate-300 leading-tight">
                  <span className="text-slate-600 shrink-0">{formatTime(msg.timestamp)}</span>
                  <span
                    className={`shrink-0 ${
                      getDirection(msg.type) === "→"
                        ? "text-blue-400"
                        : getDirection(msg.type) === "←"
                        ? "text-green-400"
                        : "text-slate-500"
                    }`}
                  >
                    {getDirection(msg.type)}
                  </span>
                  <span className="text-purple-400 shrink-0">{getTypeLabel(msg.type)}</span>
                  <span className="text-slate-400 truncate">
                    {msg.data.length > 80 ? msg.data.substring(0, 80) + "…" : msg.data}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}