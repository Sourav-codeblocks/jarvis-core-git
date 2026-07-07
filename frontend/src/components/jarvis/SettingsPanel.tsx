import { X, Settings2 } from "lucide-react";
import { THEME_PRESETS, type ThemePreset } from "./config";

export function SettingsButton({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      aria-label="Open settings"
      className="fixed top-4 right-4 z-30 rounded-full border border-[color:var(--jv-cyan)]/25 bg-black/30 p-2 text-[color:var(--jv-cyan)]/60 backdrop-blur hover:border-[color:var(--jv-cyan)]/80 hover:text-[color:var(--jv-cyan)]"
      style={{ marginTop: 56 }}
    >
      <Settings2 size={14} />
    </button>
  );
}

export function SettingsPanel({
  open,
  onClose,
  assistantName,
  tagline,
  themeId,
  onAssistantName,
  onTagline,
  onThemeId,
}: {
  open: boolean;
  onClose: () => void;
  assistantName: string;
  tagline: string;
  themeId: string;
  onAssistantName: (v: string) => void;
  onTagline: (v: string) => void;
  onThemeId: (id: string) => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-end p-6">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="jv-panel relative z-10 w-[360px] rounded-lg p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="font-display text-xs font-bold jv-tracking jv-glow-cyan">
            ◆ INTERFACE CONFIG ◆
          </div>
          <button
            onClick={onClose}
            className="text-white/50 hover:text-white"
            aria-label="Close settings"
          >
            <X size={14} />
          </button>
        </div>

        <label className="mb-3 block">
          <span className="mb-1 block font-mono text-[10px] tracking-[0.25em] text-white/50">
            ASSISTANT NAME
          </span>
          <input
            value={assistantName}
            onChange={(e) => onAssistantName(e.target.value)}
            className="w-full rounded border border-[color:var(--jv-cyan)]/30 bg-black/40 px-3 py-2 font-display text-sm tracking-[0.2em] text-white/90 focus:border-[color:var(--jv-cyan)] focus:outline-none"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block font-mono text-[10px] tracking-[0.25em] text-white/50">
            TAGLINE
          </span>
          <input
            value={tagline}
            onChange={(e) => onTagline(e.target.value)}
            className="w-full rounded border border-[color:var(--jv-cyan)]/30 bg-black/40 px-3 py-2 font-mono text-xs tracking-widest text-white/80 focus:border-[color:var(--jv-cyan)] focus:outline-none"
          />
        </label>

        <div>
          <div className="mb-2 font-mono text-[10px] tracking-[0.25em] text-white/50">
            ACCENT THEME
          </div>
          <div className="grid grid-cols-2 gap-2">
            {THEME_PRESETS.map((t) => (
              <ThemeSwatch
                key={t.id}
                theme={t}
                active={t.id === themeId}
                onClick={() => onThemeId(t.id)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ThemeSwatch({
  theme,
  active,
  onClick,
}: {
  theme: ThemePreset;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 rounded border bg-black/30 px-2 py-2 text-left transition"
      style={{
        borderColor: active ? theme.accent : "rgba(255,255,255,0.1)",
        boxShadow: active ? `0 0 14px ${theme.accent}55, inset 0 0 12px ${theme.accent}22` : "none",
      }}
    >
      <span
        className="inline-block h-5 w-5 rounded-full"
        style={{
          background: `radial-gradient(circle at 35% 35%, ${theme.accent}, ${theme.accentDim} 70%, #000 100%)`,
          boxShadow: `0 0 10px ${theme.accent}aa`,
        }}
      />
      <span
        className="font-mono text-[10px] tracking-[0.2em]"
        style={{ color: active ? theme.accent : "rgba(255,255,255,0.65)" }}
      >
        {theme.label.toUpperCase()}
      </span>
    </button>
  );
}
