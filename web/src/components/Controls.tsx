import type { ConnectionState } from "../hooks/useAudioSocket";

interface ControlsProps {
  connectionState: ConnectionState;
  isMuted: boolean;
  onStartCall: () => void;
  onEndCall: () => void;
  onMute: () => void;
}

const STATUS_TEXT: Record<ConnectionState, string> = {
  idle: "Ready to start a call",
  connecting: "Connecting...",
  connected: "Connected — speak to the agent",
  failed: "Connection failed — try again",
  ended: "Call ended",
};

const STATUS_DOT: Record<ConnectionState, string> = {
  idle: "bg-gray-400",
  connecting: "bg-yellow-400 animate-pulse",
  connected: "bg-green-500",
  failed: "bg-red-500",
  ended: "bg-gray-400",
};

export default function Controls({
  connectionState,
  isMuted,
  onStartCall,
  onEndCall,
  onMute,
}: ControlsProps) {
  const inCall =
    connectionState === "connected" || connectionState === "connecting";

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      {/* Buttons */}
      <div className="flex items-center justify-center gap-3">
        {/* Start / End call button */}
        {!inCall ? (
          <button
            onClick={onStartCall}
            disabled={false}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white font-medium rounded-xl hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
              />
            </svg>
            Start Call
          </button>
        ) : (
          <button
            onClick={onEndCall}
            className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white font-medium rounded-xl hover:bg-red-700 transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
              />
            </svg>
            End Call
          </button>
        )}

        {/* Mute button */}
        {inCall && (
          <button
            onClick={onMute}
            className={`p-3 rounded-xl border transition-colors ${
              isMuted
                ? "bg-red-50 border-red-200 text-red-600"
                : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100"
            }`}
            title={isMuted ? "Unmute" : "Mute"}
          >
            {isMuted ? (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15zM17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                />
              </svg>
            )}
          </button>
        )}
      </div>

      {/* Connection status */}
      <div className="mt-4 flex items-center justify-center gap-2">
        <div
          className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[connectionState]}`}
        />
        <p className="text-xs text-gray-500">{STATUS_TEXT[connectionState]}</p>
      </div>
    </div>
  );
}