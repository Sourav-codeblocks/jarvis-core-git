import { useEffect, useRef, useState } from "react";
import { config } from "@/config";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (text: string) => void;
}

export function TypeChat({ open, onClose, onSubmit }: Props) {
  const [val, setVal] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setVal("");
    const t = setTimeout(() => inputRef.current?.focus(), 80);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-hud-fade"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[min(560px,90vw)] rounded-lg border border-hud-cyan/40 bg-hud-panel/85 p-5 backdrop-blur-md animate-hud-scale-in"
        style={{
          boxShadow: "0 0 40px hsla(190, 100%, 55%, 0.3), inset 0 0 30px hsla(190, 100%, 55%, 0.08)",
        }}
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="font-orbitron text-[11px] tracking-[0.35em] text-hud-cyan">
            {config.hints.typeMode}
          </div>
          <div className="font-mono text-[10px] tracking-widest text-hud-cyan/60">
            {config.hints.esc}
          </div>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!val.trim()) return;
            onSubmit(val.trim());
          }}
          className="flex items-center gap-3 border-b border-hud-cyan/40 pb-2"
        >
          <span className="font-mono text-hud-cyan">&gt;</span>
          <input
            ref={inputRef}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            placeholder="ask anything…"
            className="w-full bg-transparent font-mono text-sm text-hud-cyan placeholder:text-hud-cyan/30 outline-none"
            style={{ textShadow: "0 0 8px hsla(190, 100%, 60%, 0.6)" }}
          />
        </form>
      </div>
    </div>
  );
}
