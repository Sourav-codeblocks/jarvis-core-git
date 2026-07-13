// Voice I/O seam.
// - speak(): drives the on-screen caption AND plays real TTS audio via
//   the gateway's /tts/founder route (see tts.py).
// - stopSpeaking(): interrupts whatever audio is currently playing —
//   this is the barge-in primitive, called automatically the instant
//   new speech is detected (see startVoiceSession's transcript handler).
// - startVoiceSession(): opens the mic, streams audio to the gateway's
//   voice bridge (see voice_bridge.py), and reports transcripts + the
//   final answer back to the caller. Returns a stop function. Works for
//   both one-shot mic-tap queries and continuous "Call" mode — the
//   backend already loops per connection, so continuous mode is just
//   "don't call stop() after the first response."

type Listener = (text: string) => void;
const listeners = new Set<Listener>();

export function subscribeCaption(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// --- Spoken output ----------------------------------------------------------

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000";
const TTS_URL = `${GATEWAY_URL}/tts/founder`;

let currentAudio: HTMLAudioElement | null = null;

/**
 * Barge-in primitive: immediately stops whatever Jarvis is currently
 * saying. Safe to call even if nothing is playing.
 */
export function stopSpeaking(): void {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
}

async function playSpokenAudio(text: string): Promise<void> {
  try {
    const resp = await fetch(TTS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!resp.ok) throw new Error(`TTS request failed: ${resp.status}`);

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
    };

    currentAudio = audio;

    // The very first speak() (startup greeting) fires with no prior user
    // gesture — browsers block autoplay in that case. That's expected and
    // harmless: the caption still shows, audio just stays silent until
    // the founder actually interacts (tap mic / submit query / call).
    await audio.play();
  } catch (err) {
    console.warn("TTS playback unavailable:", err);
  }
}

/**
 * Speak a line: updates the on-screen caption and plays real audio via
 * the gateway's TTS route. Caption and audio are independent — if TTS
 * fails (network hiccup, autoplay block), the caption still shows.
 */
export function speak(text: string): void {
  listeners.forEach((l) => l(text));
  void playSpokenAudio(text);
}

// --- Real-time voice input bridge -------------------------------------------
// Phase 0: keshri-pipes hardcoded — same seam as GATEWAY_WS_URL in
// dataAdapter.ts. Swap for a runtime tenant/session value once founder
// login exists.

const VOICE_WS_URL = `${GATEWAY_URL.replace(/^http/, "ws")}/ws/founder/keshri-pipes/voice`;

export interface VoiceSessionHandlers {
  /** Live transcript as Deepgram hears it — wire this to a caption/preview later. */
  onTranscript?: (text: string, isFinal: boolean) => void;
  /** Fires once the backend has routed a finished utterance and has an answer.
   * In continuous ("Call") mode, this can fire multiple times on one session —
   * the caller decides whether to keep listening or tear the session down. */
  onResponse: (res: { spokenAnswer: string; overlay: any }) => void;
  onError?: (err: Error) => void;
}

/**
 * Opens the mic, streams audio to the gateway, and reports results via
 * the given handlers. Resolves with a stop() function — call it to end
 * the session (tap-to-stop, hang up, unmount, etc).
 *
 * Barge-in is automatic: the moment any transcript event arrives (the
 * founder started talking), whatever audio is currently playing gets
 * cut off. This matters most in continuous "Call" mode, where Jarvis
 * might still be speaking when the founder starts their next question.
 */
export async function startVoiceSession(
  handlers: VoiceSessionHandlers
): Promise<() => void> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ws = new WebSocket(VOICE_WS_URL);
  const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });

  let stopped = false;

  const cleanup = () => {
    if (stopped) return;
    stopped = true;
    if (recorder.state !== "inactive") recorder.stop();
    stream.getTracks().forEach((t) => t.stop());
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  };

  ws.onopen = () => {
    recorder.start(250); // 250ms chunks — Deepgram's recommended range for low latency
  };

  recorder.ondataavailable = async (e: BlobEvent) => {
    if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
      ws.send(await e.data.arrayBuffer());
    }
  };

  ws.onmessage = (event) => {
    let msg: any;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }

    if (msg.type === "transcript") {
      // Barge-in: the founder is talking — whatever Jarvis was saying stops.
      if (msg.text) stopSpeaking();
      handlers.onTranscript?.(msg.text, msg.is_final);
    } else if (msg.type === "response") {
      handlers.onResponse({ spokenAnswer: msg.spokenAnswer, overlay: msg.overlay ?? null });
    }
  };

  ws.onerror = () => {
    handlers.onError?.(new Error("Could not reach the voice bridge."));
  };

  return cleanup;
}
