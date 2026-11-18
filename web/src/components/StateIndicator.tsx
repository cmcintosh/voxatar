interface StateIndicatorProps {
  state: string; // idle | listening | thinking | speaking
  connectionState: string; // idle | connecting | connected | failed | ended
}

const stateMap: Record<string, { color: string; bg: string; label: string; pulse: boolean }> = {
  idle: {
    color: "bg-green-500",
    bg: "bg-green-50 border-green-200",
    label: "Ready — Click Start to begin",
    pulse: false,
  },
  listening: {
    color: "bg-red-500",
    bg: "bg-red-50 border-red-200",
    label: "Listening…",
    pulse: true,
  },
  thinking: {
    color: "bg-yellow-500",
    bg: "bg-yellow-50 border-yellow-200",
    label: "Thinking…",
    pulse: true,
  },
  speaking: {
    color: "bg-blue-500",
    bg: "bg-blue-50 border-blue-200",
    label: "Speaking…",
    pulse: true,
  },
};

const connectionMap: Record<string, { color: string; label: string }> = {
  idle: { color: "bg-gray-400", label: "Disconnected" },
  connecting: { color: "bg-yellow-400", label: "Connecting…" },
  connected: { color: "bg-green-400", label: "Connected" },
  failed: { color: "bg-red-400", label: "Connection Failed" },
  ended: { color: "bg-gray-400", label: "Disconnected" },
};

export default function StateIndicator({ state, connectionState }: StateIndicatorProps) {
  const s = stateMap[state] || stateMap.idle;
  const c = connectionMap[connectionState] || connectionMap.idle;

  return (
    <div className="flex flex-col gap-2 w-full max-w-md">
      {/* Main pipeline state badge */}
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${s.bg} transition-all duration-300`}
      >
        <span className="relative flex h-3.5 w-3.5">
          {s.pulse && (
            <span
              className={`absolute inline-flex h-full w-full rounded-full ${s.color} opacity-75 animate-ping`}
            />
          )}
          <span className={`relative inline-flex rounded-full h-3.5 w-3.5 ${s.color}`} />
        </span>
        <span className="text-sm font-medium text-gray-700">{s.label}</span>
      </div>

      {/* Connection status (smaller) */}
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200">
        <span className={`relative flex h-2.5 w-2.5`}>
          {connectionState === "connecting" && (
            <span
              className={`absolute inline-flex h-full w-full rounded-full ${c.color} opacity-75 animate-ping`}
            />
          )}
          <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${c.color}`} />
        </span>
        <span className="text-xs text-gray-500">{c.label}</span>
      </div>
    </div>
  );
}