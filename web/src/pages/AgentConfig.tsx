import { useState, useEffect, useCallback } from "react";
import { Save, Plus, Trash2, AlertCircle, CheckCircle2 } from "lucide-react";
import type { AgentInfo } from "../types";

interface AgentFormData {
  name: string;
  role: string;
  organization: string;
  objectives: string[];
  system_prompt: string;
  tts_voice: string;
  available_voices: { id: string; name: string; language: string }[];
}

export default function AgentConfig() {
  const [formData, setFormData] = useState<AgentFormData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newObjective, setNewObjective] = useState("");

  useEffect(() => {
    fetch("/api/agent")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch agent config");
        return res.json();
      })
      .then((data: AgentInfo) => {
        setFormData({
          name: data.name || "",
          role: data.role || "",
          organization: data.organization || "",
          objectives: data.objectives || [],
          system_prompt: (data as any).system_prompt || "",
          tts_voice: data.tts_voice || "",
          available_voices: data.available_voices || [],
        });
      })
      .catch((err) => {
        console.error("Agent config fetch error:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = useCallback(async () => {
    if (!formData) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (!res.ok) throw new Error("Failed to save agent config");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }, [formData]);

  const addObjective = useCallback(() => {
    if (!newObjective.trim() || !formData) return;
    setFormData({
      ...formData,
      objectives: [...formData.objectives, newObjective.trim()],
    });
    setNewObjective("");
  }, [newObjective, formData]);

  const removeObjective = useCallback((index: number) => {
    if (!formData) return;
    setFormData({
      ...formData,
      objectives: formData.objectives.filter((_, i) => i !== index),
    });
  }, [formData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Loading agent configuration...</p>
      </div>
    );
  }

  if (error && !formData) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300">
        <p>Error: {error}</p>
      </div>
    );
  }

  if (!formData) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Agent Configuration</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 text-sm font-medium transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {saved && (
        <div className="bg-emerald-900/20 border border-emerald-800 rounded-lg p-4 text-emerald-300 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5" />
          <p>Configuration saved successfully!</p>
        </div>
      )}

      {/* Basic info */}
      <div className="dark-card rounded-xl p-6 border space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Basic Information</h2>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Name
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) =>
              setFormData({ ...formData, name: e.target.value })
            }
            className="dark-input w-full px-3 py-2 rounded-lg border text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Role
          </label>
          <input
            type="text"
            value={formData.role}
            onChange={(e) =>
              setFormData({ ...formData, role: e.target.value })
            }
            className="dark-input w-full px-3 py-2 rounded-lg border text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Organization
          </label>
          <input
            type="text"
            value={formData.organization}
            onChange={(e) =>
              setFormData({ ...formData, organization: e.target.value })
            }
            className="dark-input w-full px-3 py-2 rounded-lg border text-sm"
          />
        </div>
      </div>

      {/* Objectives */}
      <div className="dark-card rounded-xl p-6 border space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Objectives</h2>
        <ul className="space-y-2">
          {formData.objectives.map((obj, i) => (
            <li
              key={i}
              className="flex items-center justify-between bg-slate-700/50 rounded-lg px-3 py-2"
            >
              <span className="text-sm text-slate-300">{obj}</span>
              <button
                onClick={() => removeObjective(i)}
                className="text-red-400 hover:text-red-300 p-1"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <input
            type="text"
            value={newObjective}
            onChange={(e) => setNewObjective(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addObjective();
              }
            }}
            placeholder="Add an objective..."
            className="dark-input flex-1 px-3 py-2 rounded-lg border text-sm"
          />
          <button
            onClick={addObjective}
            className="inline-flex items-center gap-1 px-3 py-2 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600 text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
      </div>

      {/* System prompt */}
      <div className="dark-card rounded-xl p-6 border space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">System Prompt</h2>
        <textarea
          value={formData.system_prompt}
          onChange={(e) =>
            setFormData({ ...formData, system_prompt: e.target.value })
          }
          rows={8}
          className="dark-input w-full px-3 py-2 rounded-lg border text-sm font-mono resize-y"
          placeholder="Enter the system prompt for the AI agent..."
        />
      </div>

      {/* Voice selection */}
      <div className="dark-card rounded-xl p-6 border space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Voice</h2>
        <select
          value={formData.tts_voice}
          onChange={(e) =>
            setFormData({ ...formData, tts_voice: e.target.value })
          }
          className="dark-input w-full px-3 py-2 rounded-lg border text-sm"
        >
          <option value="">Default</option>
          {formData.available_voices.map((voice) => (
            <option key={voice.id} value={voice.id}>
              {voice.name} ({voice.language})
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}