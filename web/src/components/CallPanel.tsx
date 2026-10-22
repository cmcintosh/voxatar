import type { AgentInfo } from "../types";

interface CallPanelProps {
  agentInfo: AgentInfo | null;
  consented: boolean;
  onConsent: () => void;
}

export default function CallPanel({
  agentInfo,
  consented,
  onConsent,
}: CallPanelProps) {
  const needsConsent = agentInfo?.require_consent && !consented;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      {/* Agent identity */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center text-xl text-white">
          🤖
        </div>
        <div>
          <h2 className="text-base font-bold text-gray-900">
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
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-3">
            <span className="text-lg">⚠️</span>
            <div>
              <p className="text-sm font-medium text-amber-900">Consent Required</p>
              <p className="text-sm text-amber-700 mt-1">
                {agentInfo?.consent_message ||
                  "This call may be recorded and transcribed. By continuing, you consent to audio recording and AI processing."}
              </p>
              <button
                onClick={onConsent}
                className="mt-2 px-3 py-1.5 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition-colors"
              >
                I Consent
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Objectives */}
      {agentInfo?.objectives && agentInfo.objectives.length > 0 && (
        <div className="mb-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Conversation Objectives
          </h3>
          <ul className="space-y-1">
            {agentInfo.objectives.map((obj, i) => (
              <li
                key={i}
                className="text-sm text-gray-600 flex items-start gap-2"
              >
                <span className="text-indigo-500 mt-0.5">◆</span>
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
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Suggested Questions
            </h3>
            <div className="space-y-1.5">
              {agentInfo.predefined_questions.map((q, i) => (
                <div
                  key={i}
                  className="text-sm text-gray-600 p-2.5 bg-gray-50 rounded-lg border border-gray-100"
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