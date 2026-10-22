import { useState, useRef, useCallback, useEffect } from "react";

export type ConnectionState = "idle" | "connecting" | "connected" | "failed" | "ended";
export type PipelineState = "idle" | "listening" | "thinking" | "speaking";

export interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: number;
}

interface UseAudioSocketOptions {
  onTranscript?: (entry: TranscriptEntry) => void;
  onStateChange?: (state: PipelineState) => void;
  onAudioReceived?: (pcmBuffer: Float32Array) => void;
}

interface UseAudioSocketReturn {
  connectionState: ConnectionState;
  pipelineState: PipelineState;
  startCall: () => Promise<void>;
  endCall: () => void;
  toggleMute: () => void;
  bargeIn: () => void;
  analyser: AnalyserNode | null;
  audioContext: AudioContext | null;
  isMuted: boolean;
}

const SAMPLE_RATE = 16000;

export function useAudioSocket(options: UseAudioSocketOptions = {}): UseAudioSocketReturn {
  const { onTranscript, onStateChange, onAudioReceived } = options;

  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [pipelineState, setPipelineState] = useState<PipelineState>("idle");
  const [isMuted, setIsMuted] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioNodeRef = useRef<AudioWorkletNode | null>(null);
  const isMutedRef = useRef(false);
  const onTranscriptRef = useRef(onTranscript);
  const onStateChangeRef = useRef(onStateChange);
  const onAudioReceivedRef = useRef(onAudioReceived);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
    onStateChangeRef.current = onStateChange;
    onAudioReceivedRef.current = onAudioReceived;
  }, [onTranscript, onStateChange, onAudioReceived]);

  // ── Audio playback setup ──────────────────────────────────────────────
  const ensureAudioContext = useCallback((): AudioContext => {
    if (!audioContextRef.current || audioContextRef.current.state === "closed") {
      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.6;
      analyser.connect(ctx.destination);
      analyserRef.current = analyser;

      console.log("[AudioSocket] AudioContext created", {
        sampleRate: ctx.sampleRate,
        baseLatency: ctx.baseLatency,
      });
    }
    return audioContextRef.current;
  }, []);

  // ── Play received PCM binary frame ────────────────────────────────────
  const playAudioFrame = useCallback((data: ArrayBuffer) => {
    const ctx = audioContextRef.current;
    const analyser = analyserRef.current;
    if (!ctx || !analyser) {
      console.warn("[AudioSocket] No AudioContext to play audio frame");
      return;
    }

    try {
      const inputBytes = new Uint8Array(data);
      const sampleCount = Math.floor(inputBytes.length / 2);
      const float32 = new Float32Array(sampleCount);

      const view = new DataView(data);
      for (let i = 0; i < sampleCount; i++) {
        const int16 = view.getInt16(i * 2, true);
        float32[i] = int16 / 32768.0;
      }

      if (onAudioReceivedRef.current) {
        onAudioReceivedRef.current(float32);
      }

      const audioBuffer = ctx.createBuffer(1, sampleCount, SAMPLE_RATE);
      audioBuffer.copyToChannel(float32, 0, 0);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(analyser);
      source.start();

      console.log(`[AudioSocket] Playing audio frame: ${sampleCount} samples (${(sampleCount / SAMPLE_RATE * 1000).toFixed(0)}ms)`);
    } catch (err) {
      console.error("[AudioSocket] Error playing audio frame:", err);
    }
  }, []);

  // ── Handle text (JSON) messages from server ──────────────────────────
  const handleTextMessage = useCallback((text: string) => {
    let msg: any;
    try {
      msg = JSON.parse(text);
    } catch (err) {
      console.error("[AudioSocket] Failed to parse JSON message:", text, err);
      return;
    }

    console.log("[AudioSocket] Text message:", msg);

    switch (msg.type) {
      case "transcript":
        if (onTranscriptRef.current) {
          const speaker = msg.speaker || msg.event?.type || msg.role || "assistant";
          const t = msg.text || msg.event?.text || "";
          onTranscriptRef.current({
            role: speaker === "agent" ? "assistant" : speaker,
            text: t,
            timestamp: msg.timestamp || Date.now(),
          });
        }
        break;

      case "state":
        const newState = (msg.state as PipelineState) || "idle";
        if (["idle", "listening", "thinking", "speaking"].includes(newState)) {
          setPipelineState(newState);
          if (onStateChangeRef.current) {
            onStateChangeRef.current(newState);
          }
          console.log("[AudioSocket] Pipeline state →", newState);
        }
        break;

      case "end":
        console.log("[AudioSocket] Server sent end event");
        setConnectionState("ended");
        setPipelineState("idle");
        break;

      case "error":
        console.error("[AudioSocket] Server error:", msg.message || msg);
        break;

      default:
        console.log("[AudioSocket] Unhandled message type:", msg.type, msg);
    }
  }, []);

  // ── Start call ────────────────────────────────────────────────────────
  const startCall = useCallback(async () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.warn("[AudioSocket] Call already in progress");
      return;
    }

    console.log("[AudioSocket] Starting call…");
    setConnectionState("connecting");

    // 1. Set up AudioContext for playback + capture
    const ctx = ensureAudioContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
      console.log("[AudioSocket] AudioContext resumed");
    }

    // 2. Load AudioWorklet module
    try {
      await ctx.audioWorklet.addModule("/audio-processor.js");
      console.log("[AudioSocket] AudioWorklet module loaded");
    } catch (err) {
      console.error("[AudioSocket] Failed to load AudioWorklet module:", err);
      setConnectionState("failed");
      return;
    }

    // 3. Capture microphone at 16kHz
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: SAMPLE_RATE,
        },
      });
      localStreamRef.current = stream;
      console.log("[AudioSocket] Microphone access granted", {
        tracks: stream.getAudioTracks().length,
        settings: stream.getAudioTracks()[0]?.getSettings(),
      });

      // 4. Create AudioWorkletNode for capture
      const sourceNode = ctx.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(ctx, "audio-capture-processor", {
        processorOptions: { bufferSize: 3200 }, // 100ms at 16kHz
      });
      audioNodeRef.current = workletNode;

      // Connect: source → worklet (but NOT to destination — we don't want to hear ourselves)
      sourceNode.connect(workletNode);

      // Listen for PCM data from the worklet
      workletNode.port.onmessage = (event) => {
        if (wsRef.current?.readyState === WebSocket.OPEN && !isMutedRef.current) {
          // Send raw PCM ArrayBuffer as binary WS frame
          wsRef.current.send(event.data);
        }
      };

      console.log("[AudioSocket] AudioWorklet capture pipeline started");
    } catch (err) {
      console.error("[AudioSocket] Failed to set up audio capture:", err);
      setConnectionState("failed");
      return;
    }

    // 5. Connect WebSocket
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/audio`;
    console.log("[AudioSocket] Connecting WebSocket to", wsUrl);

    const ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[AudioSocket] ✅ WebSocket connected");
      setConnectionState("connected");
      setPipelineState("listening");
      if (onStateChangeRef.current) {
        onStateChangeRef.current("listening");
      }
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        playAudioFrame(event.data);
      } else if (typeof event.data === "string") {
        handleTextMessage(event.data);
      } else {
        console.warn("[AudioSocket] Unknown message format:", typeof event.data);
      }
    };

    ws.onerror = (event) => {
      console.error("[AudioSocket] WebSocket error:", event);
      setConnectionState("failed");
    };

    ws.onclose = (event) => {
      console.log("[AudioSocket] WebSocket closed", { code: event.code, reason: event.reason });
      setConnectionState("ended");
      setPipelineState("idle");
    };
  }, [ensureAudioContext, playAudioFrame, handleTextMessage]);

  // ── End call ──────────────────────────────────────────────────────────
  const endCall = useCallback(() => {
    console.log("[AudioSocket] Ending call…");

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: "end_session" }));
      } catch (err) {
        console.error("[AudioSocket] Error sending end_session:", err);
      }
    }

    // Disconnect AudioWorkletNode
    if (audioNodeRef.current) {
      audioNodeRef.current.disconnect();
      audioNodeRef.current = null;
    }

    // Stop mic tracks
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        track.stop();
        console.log("[AudioSocket] Stopped track:", track.kind, track.label);
      });
      localStreamRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close(1000, "Client ended call");
      wsRef.current = null;
    }

    setConnectionState("ended");
    setPipelineState("idle");
    setIsMuted(false);
    isMutedRef.current = false;
  }, []);

  // ── Toggle mute ───────────────────────────────────────────────────────
  const toggleMute = useCallback(() => {
    const newMuted = !isMutedRef.current;
    isMutedRef.current = newMuted;
    setIsMuted(newMuted);

    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !newMuted;
        console.log("[AudioSocket] Mic", newMuted ? "MUTED" : "UNMUTED");
      }
    }
  }, []);

  // ── Barge in ──────────────────────────────────────────────────────────
  const bargeIn = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "barge_in" }));
      console.log("[AudioSocket] Sent barge_in");
      setPipelineState("listening");
      if (onStateChangeRef.current) {
        onStateChangeRef.current("listening");
      }
    }
  }, []);

  // ── Cleanup on unmount ────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (audioNodeRef.current) {
        audioNodeRef.current.disconnect();
      }
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounted");
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close();
      }
      console.log("[AudioSocket] Cleanup complete");
    };
  }, []);

  return {
    connectionState,
    pipelineState,
    startCall,
    endCall,
    toggleMute,
    bargeIn,
    analyser: analyserRef.current,
    audioContext: audioContextRef.current,
    isMuted,
  };
}