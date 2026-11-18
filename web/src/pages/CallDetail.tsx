import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  FileJson,
  FileText,
  CheckCircle2,
  Circle,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import type { CallDetail, TranscriptLine } from "../types";

export default function CallDetail() {
  const { id } = useParams<{ id: string }>();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionItems, setActionItems] = useState<
    { id: string; text: string; done: boolean }[]
  >([]);

  useEffect(() => {
    if (!id) return;

    Promise.all([
      fetch(`/api/calls/${id}`).then((r) => {
        if (!r.ok) throw new Error("Failed to fetch call");
        return r.json();
      }),
      fetch(`/api/calls/${id}/transcript`).then((r) => {
        if (!r.ok) throw new Error("Failed to fetch transcript");
        return r.json();
      }),
    ])
      .then(([callData, transcriptData]) => {
        setCall(callData);
        setTranscript(transcriptData.lines ?? []);
        setActionItems(callData.action_items ?? []);
      })
      .catch((err) => {
        console.error("Call detail fetch error:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [id]);

  const toggleActionItem = (itemId: string) => {
    setActionItems((prev) =>
      prev.map((item) =>
        item.id === itemId ? { ...item, done: !item.done } : item
      )
    );
  };

  const downloadMarkdown = () => {
    if (!call) return;
    const md = buildMarkdown(call, transcript, actionItems);
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `call-${call.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadJSON = () => {
    if (!call) return;
    const blob = new Blob(
      [JSON.stringify({ call, transcript, action_items: actionItems }, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `call-${call.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Loading call details...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300">
        <p>Error: {error}</p>
        <Link
          to="/dashboard"
          className="mt-3 inline-flex items-center gap-2 text-sm text-red-400 hover:text-red-300"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>
      </div>
    );
  }

  if (!call) return null;

  return (
    <div className="space-y-6">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">
            Call: {call.agent}
          </h1>
          <div className="flex items-center gap-4 mt-2 text-sm text-slate-400">
            <span>{format(parseISO(call.started_at), "MMM d, yyyy HH:mm")}</span>
            <span>
              {Math.floor(call.duration_seconds / 60)}m{" "}
              {call.duration_seconds % 60}s
            </span>
            <StatusBadge status={call.status} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={downloadMarkdown}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600 text-sm font-medium transition-colors"
          >
            <FileText className="w-4 h-4" />
            Markdown
          </button>
          <button
            onClick={downloadJSON}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600 text-sm font-medium transition-colors"
          >
            <FileJson className="w-4 h-4" />
            JSON
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="dark-card rounded-xl p-6 border">
        <h2 className="text-lg font-semibold text-slate-100 mb-3">Summary</h2>
        <p className="text-slate-300 leading-relaxed">{call.summary || "No summary available."}</p>
      </div>

      {/* Action Items */}
      {actionItems.length > 0 && (
        <div className="dark-card rounded-xl p-6 border">
          <h2 className="text-lg font-semibold text-slate-100 mb-3">Action Items</h2>
          <ul className="space-y-2">
            {actionItems.map((item) => (
              <li
                key={item.id}
                onClick={() => toggleActionItem(item.id)}
                className="flex items-center gap-3 cursor-pointer group"
              >
                {item.done ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                ) : (
                  <Circle className="w-5 h-5 text-slate-500 flex-shrink-0 group-hover:text-slate-400" />
                )}
                <span
                  className={`text-sm ${
                    item.done ? "line-through text-slate-500" : "text-slate-300"
                  }`}
                >
                  {item.text}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Scorecard */}
      {call.scorecard && call.scorecard.length > 0 && (
        <div className="dark-card rounded-xl border overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-700">
            <h2 className="text-lg font-semibold text-slate-100">Scorecard</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-left">
                <th className="px-6 py-3 font-medium">Objective</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {call.scorecard.map((item, i) => (
                <tr
                  key={i}
                  className="border-b border-slate-700/50"
                >
                  <td className="px-6 py-3 text-slate-300">{item.objective}</td>
                  <td className="px-6 py-3">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-6 py-3 text-slate-400">{item.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Transcript */}
      <div className="dark-card rounded-xl p-6 border">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Transcript</h2>
        {transcript.length === 0 ? (
          <p className="text-slate-400">No transcript available.</p>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {transcript.map((line, i) => (
              <div key={i} className="flex gap-3">
                <span
                  className={`text-xs font-medium flex-shrink-0 w-16 ${
                    line.speaker === "user" ? "text-indigo-400" : "text-emerald-400"
                  }`}
                >
                  {line.speaker === "user" ? "You" : "Agent"}
                </span>
                <span className="text-xs text-slate-500 flex-shrink-0 w-20">
                  {line.timestamp}
                </span>
                <span className="text-sm text-slate-300">{line.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    met: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    failed: "bg-red-500/20 text-red-400 border-red-500/30",
    not_met: "bg-red-500/20 text-red-400 border-red-500/30",
    in_progress: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    partial: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  };
  const cls = colors[status] || colors.completed;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function buildMarkdown(
  call: CallDetail,
  transcript: TranscriptLine[],
  actionItems: { id: string; text: string; done: boolean }[]
): string {
  const lines: string[] = [];
  lines.push(`# Call: ${call.agent}`);
  lines.push("");
  lines.push(`**Date:** ${call.started_at}`);
  lines.push(`**Duration:** ${Math.floor(call.duration_seconds / 60)}m ${call.duration_seconds % 60}s`);
  lines.push(`**Status:** ${call.status}`);
  lines.push("");
  lines.push("## Summary");
  lines.push(call.summary || "No summary available.");
  lines.push("");
  if (actionItems.length > 0) {
    lines.push("## Action Items");
    actionItems.forEach((item) => {
      lines.push(`- [${item.done ? "x" : " "}] ${item.text}`);
    });
    lines.push("");
  }
  if (call.scorecard && call.scorecard.length > 0) {
    lines.push("## Scorecard");
    lines.push("| Objective | Status | Notes |");
    lines.push("|-----------|--------|-------|");
    call.scorecard.forEach((s) => {
      lines.push(`| ${s.objective} | ${s.status} | ${s.notes} |`);
    });
    lines.push("");
  }
  if (transcript.length > 0) {
    lines.push("## Transcript");
    transcript.forEach((line) => {
      lines.push(`**${line.speaker === "user" ? "You" : "Agent"}** (${line.timestamp}): ${line.text}`);
    });
  }
  return lines.join("\n");
}