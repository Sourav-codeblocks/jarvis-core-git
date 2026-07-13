import { useEffect, useState } from "react";
import { subscribeCaption } from "@/lib/voice";

export function Caption() {
  const [full, setFull] = useState("");
  const [shown, setShown] = useState("");
  const [visible, setVisible] = useState(false);

  useEffect(() => subscribeCaption((t) => {
    setFull(t);
    setShown("");
    setVisible(true);
  }), []);

  // Typewriter reveal
  useEffect(() => {
    if (!full) return;
    let i = 0;
    const id = window.setInterval(() => {
      i++;
      setShown(full.slice(0, i));
      if (i >= full.length) window.clearInterval(id);
    }, 28);
    return () => window.clearInterval(id);
  }, [full]);

  // Auto-hide
  useEffect(() => {
    if (!visible || !full) return;
    const id = window.setTimeout(() => setVisible(false), 5500 + full.length * 30);
    return () => window.clearTimeout(id);
  }, [visible, full, shown]);

  if (!full) return null;

  return (
    <div
      className={`pointer-events-none fixed left-1/2 top-24 z-40 -translate-x-1/2 transition-opacity duration-500 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
    >
      <div
        className="max-w-xl px-6 py-3 text-center font-mono text-[13px] leading-relaxed tracking-[0.12em] text-hud-cyan"
        style={{
          textShadow: "0 0 12px hsla(190, 100%, 60%, 0.7), 0 0 24px hsla(190, 100%, 60%, 0.35)",
        }}
      >
        {shown}
        <span className="ml-0.5 inline-block h-3 w-1.5 animate-hud-blink bg-hud-cyan align-middle" />
      </div>
    </div>
  );
}
