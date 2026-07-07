import type { CoreMode } from "./Core";

const LABELS: Record<CoreMode, string> = {
  idle: "STANDBY",
  listening: "LISTENING...",
  thinking: "PROCESSING...",
  call: "CALL ACTIVE",
  dimmed: "READOUT ACTIVE",
};

const COLORS: Record<CoreMode, string> = {
  idle: "jv-glow-cyan",
  listening: "jv-glow-cyan",
  thinking: "jv-glow-cyan",
  call: "jv-glow-green",
  dimmed: "jv-glow-cyan",
};

export function StatusText({ mode }: { mode: CoreMode }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={`font-display text-sm font-bold jv-tracking ${COLORS[mode]}`}
        style={{ animation: "jv-blink 2.4s ease-in-out infinite" }}
      >
        ◆ {LABELS[mode]} ◆
      </div>
      <div className="font-mono text-[10px] tracking-[0.3em] text-white/30">
        SESSION 0x7F3A · OWNER · SECURE CHANNEL
      </div>
    </div>
  );
}
