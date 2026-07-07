import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SendHorizonal } from "lucide-react";

import { HUDBackground } from "@/components/jarvis/HUDBackground";
import { Core, type CoreMode } from "@/components/jarvis/Core";
import { StatusText } from "@/components/jarvis/StatusText";
import { SpokenCaption } from "@/components/jarvis/SpokenCaption";
import { MicButton, CallButton } from "@/components/jarvis/Buttons";
import { DataOverlay, type OverlayPayload } from "@/components/jarvis/DataOverlay";
import { SettingsButton, SettingsPanel } from "@/components/jarvis/SettingsPanel";
import { CloudTendrils } from "@/components/jarvis/CloudTendrils";

import {
  assistantName as DEFAULT_NAME,
  tagline as DEFAULT_TAGLINE,
  DEFAULT_THEME_ID,
  getPreset,
} from "@/components/jarvis/config";
import { handleOwnerQuery, getSuggestedQueries } from "@/components/jarvis/queryPipeline";
import { DEMOS } from "@/components/jarvis/demoPayloads";

export const Route = createFileRoute("/")({
  component: Jarvis,
});

function Jarvis() {
  const [listening, setListening] = useState(false);
  const [call, setCall] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [overlay, setOverlay] = useState<OverlayPayload | null>(null);
  const [caption, setCaption] = useState("");
  const [transcript, setTranscript] = useState("");
  const captionTimeout = useRef<number | null>(null);

  // ---------- Configurable identity + theme ----------
  const [assistantName, setAssistantName] = useState(DEFAULT_NAME);
  const [tagline, setTagline] = useState(DEFAULT_TAGLINE);
  const [themeId, setThemeId] = useState(DEFAULT_THEME_ID);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const preset = getPreset(themeId);
  const themeStyle = useMemo(
    () =>
      ({
        ["--jv-cyan" as const]: preset.accent,
        ["--jv-cyan-dim" as const]: preset.accentDim,
        ["--jv-cyan-alt" as const]: preset.accentAlt,
        ["--jv-cyan-alt2" as const]: preset.accent3,
        ["--jv-hot" as const]: preset.hot,
        // --jv-green now holds the theme's contrast color (green retired)
        ["--jv-green" as const]: preset.contrast,
      }) as React.CSSProperties,
    [preset]
  );
  const wordmark = assistantName
    .trim()
    .split("")
    .filter((c) => c !== " ")
    .join(" · ");
  const isBusy = thinking || listening;
  const netIntensity = thinking ? 2.4 : listening ? 1.7 : call ? 1.2 : 1;
  const netBrightness = isBusy ? 0.75 : 0.5;

  // Derive core mode
  const mode: CoreMode = overlay
    ? "dimmed"
    : thinking
    ? "thinking"
    : listening
    ? "listening"
    : call
    ? "call"
    : "idle";

  const [hint, setHint] = useState<string>("");
  const hintTimeout = useRef<number | null>(null);
  const flashHint = useCallback((msg: string) => {
    setHint(msg);
    if (hintTimeout.current) window.clearTimeout(hintTimeout.current);
    hintTimeout.current = window.setTimeout(() => setHint(""), 2200);
  }, []);

  const handleMicToggle = useCallback(() => {
    if (!listening && call) {
      flashHint("End the call before using the mic.");
      return;
    }
    setListening((v) => !v);
  }, [listening, call, flashHint]);

  const handleCallToggle = useCallback(() => {
    if (!call && listening) {
      flashHint("Turn off the mic before starting a call.");
      return;
    }
    setCall((v) => !v);
  }, [call, listening, flashHint]);

  const handleShowData = useCallback((payload: OverlayPayload) => {
    setOverlay(payload);
  }, []);

  const handleCloseOverlay = useCallback(() => {
    setOverlay(null);
  }, []);

  const submitQuery = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q) return;
      setListening(false);
      setThinking(true);
      setCaption("");
      if (captionTimeout.current) window.clearTimeout(captionTimeout.current);

      const res = await handleOwnerQuery(q);
      setThinking(false);
      setCaption(res.spokenAnswer);
      if (res.overlay) {
        // small beat so the caption starts typing first
        window.setTimeout(() => handleShowData(res.overlay!), 450);
      } else {
        captionTimeout.current = window.setTimeout(() => setCaption(""), 7000);
      }
      setTranscript("");
    },
    [handleShowData]
  );

  // ESC handled inside DataOverlay; here we also allow ESC to clear caption
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !overlay) setCaption("");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [overlay]);

  return (
    <main
      className="relative flex min-h-screen w-screen flex-col items-center justify-start pt-16 pb-6"
      style={themeStyle}
    >
      <HUDBackground />

      {/* Drifting colorful clouds + connections flowing out from the core.
          Active while mic/call are on. Center + edges are masked so the
          core, mic, call and text remain fully readable. */}
      <CloudTendrils active={call || listening} />




      <div className="pointer-events-none fixed left-1/2 top-4 z-10 -translate-x-1/2 text-center">
        <div className="font-display text-xs font-bold jv-tracking jv-glow-cyan">
          {wordmark || "J A R V I S"}
        </div>
        <div className="mt-1 font-mono text-[9px] tracking-[0.4em] text-white/30">
          {tagline}
        </div>
      </div>

      {/* Settings entry (top-right, under telemetry) */}
      <SettingsButton onOpen={() => setSettingsOpen(true)} />
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        assistantName={assistantName}
        tagline={tagline}
        themeId={themeId}
        onAssistantName={setAssistantName}
        onTagline={setTagline}
        onThemeId={setThemeId}
      />

      {/* Core cluster (only when no overlay) */}
      <div
        className={`relative z-10 flex flex-col items-center transition-all duration-500 ${
          overlay ? "pointer-events-none scale-0 opacity-0" : "scale-100 opacity-100"
        }`}
      >
        <div className="relative flex items-center justify-center" style={{ width: 600, height: 600 }}>
          <Core mode={mode} />
        </div>

        {/* Mic pulled up so both core and mic fit in one viewport frame */}
        <div className="-mt-28 flex flex-col items-center gap-1">
          <MicButton active={listening} onToggle={handleMicToggle} />
          <span className="font-mono text-[9px] tracking-[0.3em] text-white/40">MIC</span>
        </div>

        <div className="mt-3">
          <StatusText mode={mode} />
        </div>

        <div className="mt-2 min-h-[36px] w-full max-w-2xl">
          {caption ? (
            <SpokenCaption text={caption} />
          ) : (
            <p className="text-center font-mono text-[11px] tracking-[0.3em] text-white/25">
              {listening
                ? "◉ AWAITING VOICE INPUT"
                : thinking
                ? "◉ ROUTING QUERY · CLASSIFIER ACTIVE"
                : call
                ? "◉ VOICE CHANNEL OPEN"
                : "◉ READY · SPEAK OR TYPE A QUERY"}
            </p>
          )}
        </div>




        {/* Dev transcript input (simulates STT) */}
        <div className="mt-2 flex w-full max-w-xl items-center gap-2 rounded border border-[color:var(--jv-cyan)]/25 bg-black/30 px-3 py-2 backdrop-blur-md">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[color:var(--jv-cyan)]/70">
            &gt; TX
          </span>
          <input
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitQuery(transcript);
            }}
            placeholder="Simulate voice transcript · e.g. what's running low in stock"
            className="flex-1 bg-transparent font-mono text-xs tracking-wider text-white/90 placeholder:text-white/25 focus:outline-none"
          />
          <button
            onClick={() => submitQuery(transcript)}
            className="rounded-full border border-[color:var(--jv-cyan)]/40 p-1.5 text-[color:var(--jv-cyan)] hover:bg-[color:var(--jv-cyan)]/10"
            aria-label="Send query"
          >
            <SendHorizonal size={14} />
          </button>
        </div>

        {/* suggested queries */}
        <div className="flex flex-wrap justify-center gap-2">
          {getSuggestedQueries().map((q) => (
            <button
              key={q}
              onClick={() => submitQuery(q)}
              className="rounded-full border border-[color:var(--jv-cyan)]/20 bg-black/30 px-3 py-1 font-mono text-[10px] tracking-widest text-white/60 backdrop-blur hover:border-[color:var(--jv-cyan)]/60 hover:text-[color:var(--jv-cyan)]"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Call button — corner */}
      <div className="fixed bottom-8 right-8 z-20 flex flex-col items-center gap-2">
        <CallButton active={call} onToggle={handleCallToggle} />
        <span className="font-mono text-[9px] tracking-[0.3em] text-white/40">CALL</span>
      </div>

      {/* Dimmed core icon while overlay is open */}
      {overlay && (
        <div className="pointer-events-none fixed bottom-6 left-6 z-20 flex items-center gap-3">
          <Core mode="dimmed" />
          <div>
            <div className="font-display text-[10px] font-bold jv-tracking jv-glow-cyan">
              {assistantName || "JARVIS"}
            </div>
            <div className="font-mono text-[9px] tracking-[0.3em] text-white/40">
              READOUT ACTIVE
            </div>
          </div>
        </div>
      )}

      {/* Dev-only demo triggers */}
      <div className="fixed bottom-6 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2">
        <span className="font-mono text-[9px] tracking-[0.3em] text-white/25">
          DEV ·
        </span>
        {DEMOS.map((d) => (
          <button
            key={d.label}
            onClick={() => handleShowData(d.payload)}
            className="rounded border border-[color:var(--jv-cyan)]/25 bg-black/40 px-2 py-1 font-mono text-[9px] tracking-[0.25em] text-white/55 backdrop-blur hover:border-[color:var(--jv-cyan)]/70 hover:text-[color:var(--jv-cyan)]"
          >
            {d.label}
          </button>
        ))}
      </div>

      {/* Mutual-exclusion hint */}
      {hint && (
        <div
          className="pointer-events-none fixed bottom-28 right-8 z-30 rounded border border-[color:var(--jv-cyan)]/50 bg-black/70 px-3 py-2 font-mono text-[10px] tracking-[0.25em] text-[color:var(--jv-cyan)] backdrop-blur animate-fade-in"
          role="status"
        >
          ◆ {hint}
        </div>
      )}

      {/* Overlay */}
      {overlay && <DataOverlay payload={overlay} onClose={handleCloseOverlay} />}
    </main>
  );
}
