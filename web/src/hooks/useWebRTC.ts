import { useState, useCallback, useRef } from "react";

export type ConnectionState = "idle" | "connecting" | "connected" | "failed" | "ended";

interface UseWebRTCOptions {
  onTranscript: (entry: {
    type: "user" | "agent" | "system";
    text: string;
    timestamp: number;
    isPartial?: boolean;
  }) => void;
}

interface UseWebRTCReturn {
  connectionState: ConnectionState;
  startCall: () => Promise<void>;
  endCall: () => Promise<void>;
  toggleMute: () => Promise<void>;
}

export function useWebRTC({ onTranscript }: UseWebRTCOptions): UseWebRTCReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  // audioContextRef removed — unused

  const startCall = useCallback(async () => {
    try {
      setConnectionState("connecting");

      // 1. Set up WebSocket for transcript streaming
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/transcript`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Store globally for barge-in
      (window as any).__voxatar_ws = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "transcript" && data.event) {
            onTranscript(data.event);
          }
        } catch (e) {
          console.error("WebSocket message parse error:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };

      // Wait for WS to connect
      await new Promise((resolve, reject) => {
        ws.onopen = resolve;
        ws.onerror = reject;
      });

      // 2. Get microphone access
      const localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
      localStreamRef.current = localStream;

      // 3. Create RTCPeerConnection
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      pcRef.current = pc;

      // Add local audio track
      localStream.getAudioTracks().forEach((track) => {
        pc.addTrack(track, localStream);
      });

      // Handle incoming audio (TTS output from server)
      pc.ontrack = (event) => {
        if (event.track.kind === "audio") {
          const audioElement = new Audio();
          audioElement.srcObject = event.streams[0];
          audioElement.autoplay = true;
          audioElement.play().catch((e) => {
            console.error("Audio playback failed:", e);
          });
        }
      };

      // Handle connection state changes
      pc.onconnectionstatechange = () => {
        const state = pc.connectionState;
        if (state === "connected") {
          setConnectionState("connected");
        } else if (state === "failed" || state === "disconnected") {
          setConnectionState("failed");
        } else if (state === "closed") {
          setConnectionState("ended");
        }
      };

      // 4. Create SDP offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Wait for ICE gathering to complete
      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === "complete") {
          resolve();
        } else {
          const checkState = () => {
            if (pc.iceGatheringState === "complete") {
              pc.removeEventListener("icegatheringstatechange", checkState);
              resolve();
            }
          };
          pc.addEventListener("icegatheringstatechange", checkState);

          // Timeout fallback (3 seconds)
          setTimeout(resolve, 3000);
        }
      });

      // 5. Send offer to server and get answer
      const response = await fetch("/api/webrtc/offer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sdp: pc.localDescription!.sdp,
          type: pc.localDescription!.type,
        }),
      });

      if (!response.ok) {
        throw new Error(`WebRTC offer failed: ${response.statusText}`);
      }

      const answer = await response.json();

      // 6. Set remote description
      await pc.setRemoteDescription(answer);

      console.log("WebRTC call started successfully");
    } catch (error) {
      console.error("Failed to start call:", error);
      setConnectionState("failed");

      // Cleanup on error
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((t) => t.stop());
        localStreamRef.current = null;
      }
    }
  }, [onTranscript]);

  const endCall = useCallback(async () => {
    // Close WebRTC connection
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }

    // Stop local tracks
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
      localStreamRef.current = null;
    }

    // Notify server
    try {
      await fetch("/api/session/end", { method: "POST" });
    } catch (e) {
      console.error("Failed to end session:", e);
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState("ended");
    console.log("WebRTC call ended");
  }, []);

  const toggleMute = useCallback(async () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        console.log(`Microphone ${audioTrack.enabled ? "unmuted" : "muted"}`);
      }
    }
  }, []);

  return {
    connectionState,
    startCall,
    endCall,
    toggleMute,
  };
}