import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Phone, PhoneOff, Keyboard, LayoutGrid } from "lucide-react";
import { config } from "@/config";
import {
  fetchJarvisResponse,
  type FounderReport,
  type OverlayPayload,
} from "@/lib/dataAdapter";
import { speak, startVoiceSession } from "@/lib/voice";
import { Ring } from "./Ring";
import { NodeLines } from "./NodeLines";
import { Caption } from "./Caption";
import { Overlay } from "./Overlay";
import { TypeChat } from "./TypeChat";
import { ReportsBanner } from "./ReportsBanner";
import type { HudState } from "./types";

const HUE_BY_STATE: Record<HudState, number> = {
  standby: 195,
  listening: 205,
  call: 138,
  thinking: 265,
  typing: 40,
};

export function Hud() {
  const [state, setState] = useState<HudState>("standby");
  const [processing, setProcessing] = useState(false);
  const [overlay, setOverlay] = useState<OverlayPayload | null>(null);
  const [typeOpen, setTypeOpen] = useState(false);
  const [reportsOpen, setReportsOpen] = useState(false);
  const [greeted, setGreeted] = useState(false);

  useEffect(() => {
    if (greeted) return;
    const t = setTimeout(() => {
      speak(config.greeting);
      setGreeted(true);
    }, 900);
    return () => clearTimeout(t);
  }, [greeted]);

  const runQuery = useCallback(async (q: string) => {
    setProcessing(true);
    setState("thinking");
    try {
      const res = await fetchJarvisResponse(q);
      speak(res.spokenAnswer);
      if (res.overlay) setOverlay(res.overlay);
    } catch (err) {
      // Gateway unreachable, timed out, or dropped mid-query — surface it
      // as a spoken/caption line instead of leaving the HUD stuck on
      // "PROCESSING" forever.
      console.error("fetchJarvisResponse failed:", err);
      speak("I couldn't reach the core. Check that the gateway is running.");
    } finally {
      setTimeout(() => {
        setProcessing(false);
        setState("standby");
      }, 900);
    }
  }, []);

  const stopVoiceRef = useRef<(() => void) | null>(null);

  const toggleMic = useCallback(async () => {
    if (state === "listening") {
      // Second tap = stop listening. If a session is running, tear it down;
      // the response (if one arrives) resets state on its own via onResponse.
      stopVoiceRef.current?.();
      stopVoiceRef.current = null;
      setState("standby");
      return;
    }
    if (processing || state === "call") return;

    setState("listening");
    try {
      stopVoiceRef.current = await startVoiceSession({
        onResponse: (res) => {
          stopVoiceRef.current?.();
          stopVoiceRef.current = null;
          setProcessing(true);
          setState("thinking");
          speak(res.spokenAnswer);
          if (res.overlay) setOverlay(res.overlay);
          setTimeout(() => {
            setProcessing(false);
            setState("standby");
          }, 900);
        },
        onError: (err) => {
          console.error("Voice session error:", err);
          stopVoiceRef.current?.();
          stopVoiceRef.current = null;
          speak("I couldn't reach the voice bridge. Check that the gateway is running.");
          setState("standby");
        },
      });
    } catch (err) {
      // getUserMedia rejected — no mic permission, no device, or blocked by browser.
      console.error("Could not start microphone:", err);
      speak("I need microphone access to listen.");
      setState("standby");
    }
  }, [state, processing]);

  const stopCallRef = useRef<(() => void) | null>(null);

  const toggleCall = useCallback(async () => {
    if (state === "call") {
      // Hang up.
      stopCallRef.current?.();
      stopCallRef.current = null;
      setState("standby");
      return;
    }
    if (processing || state === "listening") return; // don't collide with one-shot mic mode

    setState("call");
    try {
      stopCallRef.current = await startVoiceSession({
        onResponse: (res) => {
          // Deliberately don't stop the session or reset state here —
          // that's the whole difference from tap-to-ask mic mode. The
          // backend (voice_bridge.py) keeps listening on this same
          // connection, so we just speak the answer and stay in "call".
          speak(res.spokenAnswer);
          if (res.overlay) setOverlay(res.overlay);
        },
        onError: (err) => {
          console.error("Call session error:", err);
          stopCallRef.current?.();
          stopCallRef.current = null;
          speak("I lost the connection to the voice bridge.");
          setState("standby");
        },
      });
    } catch (err) {
      console.error("Could not start call session:", err);
      speak("I need microphone access for a call.");
      setState("standby");
    }
  }, [state, processing]);

  const handleActivateTypeMode = useCallback(() => {
    setTypeOpen(true);
    setState("typing");
  }, []);

  const handlePickReport = useCallback((r: FounderReport) => {
    setReportsOpen(false);
    speak(r.spokenAnswer);
    setOverlay(r.overlay);
  }, []);

  const hotState: HudState = processing ? "thinking" : state;

  return (
    <div className="relative min-h-screen w-full overflow-y-auto bg-hud-bg text-hud-cyan">
      <div className="pointer-events-none absolute inset-0 bg-hud-grid opacity-[0.06]" />
      <div className="pointer-events-none absolute inset-0 bg-hud-scanline opacity-[0.05] mix-blend-screen" />
      <div className="pointer-events-none absolute inset-0 animate-hud-vignette bg-radial-vignette" />

      <header className="relative z-10 flex items-center justify-between px-8 pt-6 font-orbitron">
        <div className="flex items-center gap-3">
          <span className="inline-block h-2 w-2 animate-hud-blink rounded-full bg-hud-cyan" />
          <span className="text-[11px] tracking-[0.45em] text-hud-cyan/80">
            {config.assistantName}
          </span>
          <span className="hidden sm:inline text-[10px] tracking-[0.3em] text-hud-cyan/40">
            // {config.tagline}
          </span>
        </div>
        <div className="hidden md:flex items-center gap-6 font-mono text-[10px] tracking-[0.25em] text-hud-cyan/60">
          <Telem label={config.labels.uplink} value="98%" />
          <Telem label={config.labels.coreTemp} value="72°" />
          <Telem label={config.labels.signal} value="STRONG" />
          <Telem label={config.labels.latency} value="12ms" />
        </div>
      </header>

      <main className="relative z-10 flex min-h-[calc(100vh-140px)] items-center justify-center">
        <div
          className="pointer-events-none absolute inset-0 transition-opacity duration-700"
          style={{ opacity: processing ? 0.55 : 0 }}
        >
          <NodeLines state={hotState} hue={HUE_BY_STATE[hotState]} />
        </div>

        <div className="relative flex flex-col items-center">
          <Ring state={hotState}>
            <MicButton
              state={hotState}
              processing={processing}
              onClick={toggleMic}
            />
          </Ring>

          <div className="mt-8 font-orbitron text-[10px] tracking-[0.5em] text-hud-cyan/70">
            {processing ? config.status.thinking : config.status[state]}
          </div>
          <div className="mt-1 font-mono text-[10px] tracking-[0.25em] text-hud-cyan/40">
            {processing
              ? "Working…"
              : state === "listening"
              ? config.hints.micActive
              : state === "call"
              ? config.hints.callActive
              : config.hints.micIdle}
          </div>
        </div>

        <Caption />
      </main>

      <MoonButton
        active={state === "call"}
        onClick={toggleCall}
        label={state === "call" ? "End Call" : "Call"}
      />

      {/* Utility rail — bottom left */}
      <div className="absolute bottom-6 left-6 z-20 flex items-center gap-3">
        <IconChip onClick={handleActivateTypeMode} title="Type mode">
          <Keyboard className="h-4 w-4" />
        </IconChip>
      </div>

      {/* Reports pull-tab — bottom center */}
      <button
        type="button"
        onClick={() => setReportsOpen((o) => !o)}
        title={reportsOpen ? "Close reports" : "Open reports"}
        aria-label="Reports"
        className="absolute bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 rounded-full border border-hud-cyan/40 bg-hud-panel/70 px-4 py-2 font-orbitron text-[10px] tracking-[0.35em] text-hud-cyan/85 backdrop-blur transition-all hover:border-hud-cyan hover:text-hud-cyan"
        style={{
          boxShadow: reportsOpen
            ? "0 0 24px hsla(190, 100%, 55%, 0.5)"
            : "0 0 12px hsla(190, 100%, 55%, 0.2)",
        }}
      >
        <LayoutGrid className="h-3.5 w-3.5" />
        {reportsOpen ? "HIDE REPORTS" : "REPORTS"}
      </button>

      <ReportsBanner
        open={reportsOpen}
        onClose={() => setReportsOpen(false)}
        onPick={handlePickReport}
      />

      <Overlay payload={overlay} onClose={() => setOverlay(null)} />
      <TypeChat
        open={typeOpen}
        onClose={() => {
          setTypeOpen(false);
          setState("standby");
        }}
        onSubmit={(text) => {
          setTypeOpen(false);
          runQuery(text);
        }}
      />
    </div>
  );
}

function Telem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-hud-cyan/40">{label}</span>
      <span className="text-hud-cyan">{value}</span>
    </div>
  );
}

function MicButton({
  state,
  processing,
  onClick,
}: {
  state: HudState;
  processing: boolean;
  onClick: () => void;
}) {
  const listening = state === "listening";
  const hue = listening ? 205 : processing ? 265 : 195;
  const Icon = listening ? Mic : MicOff;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      aria-label={listening ? "Mute microphone" : "Activate microphone"}
      className="group relative grid h-16 w-16 place-items-center rounded-full transition-all duration-500"
      style={{
        background: `radial-gradient(circle at 35% 30%,
          hsla(${hue}, 100%, 65%, ${listening ? 0.35 : 0.15}),
          hsla(${hue}, 100%, 10%, 0.85) 75%)`,
        border: `1px solid hsla(${hue}, 100%, 70%, ${listening ? 0.9 : 0.45})`,
        boxShadow: listening
          ? `0 0 24px hsla(${hue}, 100%, 60%, 0.85), inset 0 0 18px hsla(${hue}, 100%, 65%, 0.5)`
          : `0 0 12px hsla(${hue}, 100%, 55%, 0.4), inset 0 0 10px hsla(${hue}, 100%, 55%, 0.25)`,
      }}
    >
      <Icon
        className="h-6 w-6"
        style={{
          color: `hsl(${hue}, 100%, ${listening ? 82 : 70}%)`,
          filter: `drop-shadow(0 0 6px hsla(${hue}, 100%, 70%, 0.9))`,
        }}
      />
      {listening && (
        <span
          aria-hidden
          className="absolute inset-0 rounded-full animate-hud-flare"
          style={{
            border: `1px solid hsla(${hue}, 100%, 75%, 0.5)`,
          }}
        />
      )}
    </button>
  );
}

function MoonButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  const hue = 138;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="group absolute bottom-8 right-8 z-20 transition-transform duration-500 hover:scale-105"
    >
      <span
        aria-hidden
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, hsla(${hue}, 100%, 55%, ${
            active ? 0.7 : 0.35
          }), transparent 65%)`,
          filter: "blur(18px)",
          transform: "scale(1.4)",
        }}
      />
      <span
        className="relative grid h-20 w-20 place-items-center rounded-full"
        style={{
          background: `radial-gradient(circle at 32% 28%,
            hsl(${hue}, 100%, 88%),
            hsl(${hue}, 90%, 55%) 45%,
            hsl(${hue}, 90%, 18%) 85%,
            hsl(${hue}, 80%, 8%) 100%)`,
          boxShadow: `
            0 0 30px hsla(${hue}, 100%, 55%, ${active ? 0.9 : 0.5}),
            inset -6px -8px 20px hsla(0,0%,0%,0.55),
            inset 4px 6px 14px hsla(0,0%,100%,0.35)`,
        }}
      >
        <span
          aria-hidden
          className="absolute inset-0 rounded-full opacity-40 mix-blend-overlay"
          style={{
            background:
              "radial-gradient(circle at 60% 40%, hsla(0,0%,0%,0.4) 0 6%, transparent 7%)," +
              "radial-gradient(circle at 30% 65%, hsla(0,0%,0%,0.35) 0 4%, transparent 5%)," +
              "radial-gradient(circle at 70% 70%, hsla(0,0%,0%,0.3) 0 3%, transparent 4%)",
          }}
        />
        {active ? (
          <PhoneOff
            className="relative h-7 w-7"
            style={{
              color: "hsl(0, 0%, 8%)",
              filter: "drop-shadow(0 1px 1px hsla(0,0%,100%,0.4))",
            }}
          />
        ) : (
          <Phone
            className="relative h-7 w-7"
            style={{
              color: "hsl(0, 0%, 8%)",
              filter: "drop-shadow(0 1px 1px hsla(0,0%,100%,0.4))",
            }}
          />
        )}
      </span>
    </button>
  );
}

function IconChip({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className="grid h-10 w-10 place-items-center rounded-full border border-hud-cyan/25 bg-hud-cyan/[0.04] text-hud-cyan/70 transition-colors hover:border-hud-cyan/60 hover:text-hud-cyan"
    >
      {children}
    </button>
  );
}
