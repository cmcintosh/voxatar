import { useEffect, useRef, useState } from "react";

interface AvatarViewProps {
  pipelineState: string;
  analyser: AnalyserNode | null;
  avatarImage?: string;
}

const stateConfig: Record<string, { label: string; emoji: string; color: string }> = {
  idle: { label: "Ready", emoji: "🟢", color: "text-green-500" },
  listening: { label: "Listening", emoji: "🔴", color: "text-red-500" },
  thinking: { label: "Thinking", emoji: "🟡", color: "text-yellow-500" },
  speaking: { label: "Speaking", emoji: "🔵", color: "text-blue-500" },
};

export default function AvatarView({
  pipelineState,
  analyser,
  avatarImage = "/avatar-default.png",
}: AvatarViewProps) {
  const [mouthScale, setMouthScale] = useState(1.0);
  const animationRef = useRef<number | null>(null);
  const freqDataRef = useRef<Uint8Array<ArrayBuffer> | null>(null);

  // ── Speaking animation: read analyser amplitude and scale mouth overlay ─
  useEffect(() => {
    if (pipelineState !== "speaking" || !analyser) {
      setMouthScale(1.0);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      return;
    }

    const bufferLength = analyser.frequencyBinCount;
    freqDataRef.current = new Uint8Array(new ArrayBuffer(bufferLength));

    const animate = () => {
      if (!analyser || !freqDataRef.current) return;

      analyser.getByteFrequencyData(freqDataRef.current);

      // Compute average amplitude from lower frequency bins (voice range)
      const voiceBins = Math.min(bufferLength, 32);
      let sum = 0;
      for (let i = 0; i < voiceBins; i++) {
        sum += freqDataRef.current[i];
      }
      const avg = sum / voiceBins;
      // Map 0–255 → 0.8 – 2.5 scale
      const scale = 0.8 + (avg / 255) * 1.7;
      setMouthScale(scale);

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    };
  }, [pipelineState, analyser]);

  const config = stateConfig[pipelineState] || stateConfig.idle;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Avatar container */}
      <div className="relative" style={{ width: 200, height: 200 }}>
        {/* Pulsing ring for listening state */}
        {pipelineState === "listening" && (
          <div
            className="absolute inset-0 rounded-full border-4 border-blue-400"
            style={{
              animation: "avatarPulse 1.5s ease-in-out infinite",
            }}
          />
        )}

        {/* Main avatar image with breathing animation when idle */}
        <div
          className="rounded-full overflow-hidden bg-slate-100"
          style={{
            width: 200,
            height: 200,
            animation:
              pipelineState === "idle"
                ? "avatarBreathe 4s ease-in-out infinite"
                : "none",
          }}
        >
          <img
            src={avatarImage}
            alt="Avatar"
            className="w-full h-full object-cover"
            draggable={false}
          />
        </div>

        {/* Thinking dots overlay */}
        {pipelineState === "thinking" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-full">
            <div className="flex gap-2 items-center">
              <span
                className="w-3 h-3 rounded-full bg-white"
                style={{ animation: "thinkDot 1.4s ease-in-out infinite", animationDelay: "0s" }}
              />
              <span
                className="w-3 h-3 rounded-full bg-white"
                style={{ animation: "thinkDot 1.4s ease-in-out infinite", animationDelay: "0.2s" }}
              />
              <span
                className="w-3 h-3 rounded-full bg-white"
                style={{ animation: "thinkDot 1.4s ease-in-out infinite", animationDelay: "0.4s" }}
              />
            </div>
          </div>
        )}

        {/* Speaking mouth overlay */}
        {pipelineState === "speaking" && (
          <div
            className="absolute left-1/2 rounded-full bg-blue-400/40 border border-blue-300/50"
            style={{
              width: 50,
              height: 30 * mouthScale,
              bottom: 45,
              transform: "translateX(-50%)",
              transition: "height 60ms linear",
            }}
          />
        )}

        {/* Position-based glow */}
        <div
          className="absolute inset-0 rounded-full pointer-events-none"
          style={{
            boxShadow:
              pipelineState === "speaking"
                ? "0 0 30px rgba(59, 130, 246, 0.4)"
                : pipelineState === "listening"
                ? "0 0 20px rgba(239, 68, 68, 0.3)"
                : "none",
          }}
        />
      </div>

      {/* State badge */}
      <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-800/80 backdrop-blur">
        <span className="text-lg">{config.emoji}</span>
        <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
      </div>

      {/* Keyframe styles */}
      <style>{`
        @keyframes avatarBreathe {
          0%, 100% { transform: scale(1.0); }
          50% { transform: scale(1.02); }
        }
        @keyframes avatarPulse {
          0%, 100% {
            transform: scale(1);
            opacity: 0.7;
          }
          50% {
            transform: scale(1.08);
            opacity: 0.3;
          }
        }
        @keyframes thinkDot {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-8px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}