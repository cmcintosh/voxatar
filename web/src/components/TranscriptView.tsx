import { useRef, useEffect } from "react";

interface TranscriptViewProps {
  transcript: Array<{
    role: "user" | "assistant";
    text: string;
    timestamp: number;
  }>;
}

export default function TranscriptView({ transcript }: TranscriptViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when transcript changes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  if (transcript.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white rounded-xl shadow-sm border border-gray-200 min-h-[400px]">
        <div className="text-center text-gray-400">
          <span className="text-4xl block mb-2">💬</span>
          <p className="text-sm">
            Start a call to see the live transcript here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 p-4 overflow-y-auto min-h-[400px] max-h-[600px]"
    >
      <div className="space-y-3">
        {transcript.map((entry, i) => (
          <TranscriptItem key={i} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function TranscriptItem({
  entry,
}: {
  entry: { role: "user" | "assistant"; text: string; timestamp: number };
}) {
  const time = new Date(entry.timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  const isUser = entry.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fadeIn`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
          isUser ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium opacity-70">
            {isUser ? "You" : "Agent"}
          </span>
          <span className="text-[10px] opacity-50">{time}</span>
        </div>
        <p className="text-sm leading-relaxed">{entry.text}</p>
      </div>
    </div>
  );
}