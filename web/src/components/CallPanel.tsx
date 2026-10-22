import type { AgentInfo } from "../types";
import type { ConnectionState } from "../hooks/useWebRTC";

interface CallPanelProps {
  agentInfo: AgentInfo | null;
  connectionState: ConnectionState;
  consented: boolean;
  onConsent: () => void;
}

export default function CallPanel({
  agentInfo,
  connectionState,
  consented,
  onConsent,
}: CallPanelProps) {
  const needsConsent = agentInfo?.require_consent && !consented;
  const inCall = connectionState === "connected";

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      {/* Agent identity */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-voxatar-500 to-voxatar-700 flex items-center justify-center text-2xl text-white">
          🤖
        </div>
        <div>
          <h2 className="text-lg font-bold text-gray-900">
            {agentInfo?.name || "Voxatar Agent"}
          </h2>
          <p className="text-sm text-gray-500">
            {agentInfo?.role || "Assistant"}
            {agentInfo?.organization ? ` · ${agentInfo.organization}` : ""}
          </p>
        </div>
      </div>

      {/* Consent banner */}
      {needsConsent && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-3">
            <span className="text-xl">⚠️</span>
            <div>
              <p className="text-sm font-medium text-amber-900">Consent Required</p>
              <p className="text-sm text-amber-700 mt-1">
                {agentInfo?.consent_message ||
                  "This call may be recorded and transcribed. By continuing, you consent to audio recording and AI processing."}
              </p>
              <button
                onClick={onConsent}
                className="mt-3 px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700"
              >
                I Consent
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Call status */}
      {inCall && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-medium text-green-900">
            Call in progress
          </span>
        </div>
      )}

      {/* Objectives */}
      {agentInfo?.objectives && agentInfo.objectives.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">
            Conversation Objectives
          </h3>
          <ul className="space-y-1">
            {agentInfo.objectives.map((obj, i) => (
              <li
                key={i}
                className="text-sm text-gray-600 flex items-start gap-2"
              >
                <span className="text-voxatar-500 mt-0.5">◆</span>
                {obj}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggested questions */}
      {agentInfo?.predefined_questions &&
        agentInfo.predefined_questions.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Suggested Questions
            </h3>
            <div className="space-y-2">
              {agentInfo.predefined_questions.map((q, i) => (
                <div
                  key={i}
                  className="text-sm text-gray-600 p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  {q}
                </div>
              ))}
            </div>
          </div>
        )}
    </div>
  );
}