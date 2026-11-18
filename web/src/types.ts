export interface TranscriptEntry {
  type: "user" | "agent" | "system";
  text: string;
  timestamp: number;
  isPartial?: boolean;
}

export interface AgentInfo {
  name: string;
  role: string;
  organization: string;
  objectives: string[];
  predefined_questions: string[];
  require_consent: boolean;
  consent_message: string;
  max_duration: number;
  tts_voice: string | null;
  available_voices: { id: string; name: string; language: string }[];
}

export interface CallRecord {
  id: string;
  agent: string;
  started_at: string;
  duration_seconds: number;
  summary: string;
  status: "completed" | "failed" | "in_progress";
}

export interface CallDetail extends CallRecord {
  objectives: { objective: string; status: "met" | "not_met" | "partial"; notes: string }[];
  action_items: { id: string; text: string; done: boolean }[];
  scorecard: { objective: string; status: "met" | "not_met" | "partial"; notes: string }[];
}

export interface TranscriptLine {
  speaker: "user" | "agent";
  text: string;
  timestamp: string;
}

export interface KnowledgeDocument {
  id: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}