import { useEffect, useState } from "react";

export function Waveform({ active }: { active: boolean }) {
  const [bars, setBars] = useState<number[]>(() => Array.from({ length: 48 }, () => 0.2));

  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => {
      setBars((prev) => prev.map(() => 0.15 + Math.random() * 0.85));
    }, 90);
    return () => window.clearInterval(id);
  }, [active]);

  return (
    <div className="flex h-14 items-center gap-[3px]">
      {bars.map((v, i) => (
        <span
          key={i}
          className="w-[3px] rounded-full transition-[height] duration-100"
          style={{
            height: `${active ? v * 100 : 12}%`,
            background: "var(--jv-cyan)",
            boxShadow: active ? "0 0 8px var(--jv-cyan)" : "none",
            opacity: active ? 0.9 : 0.25,
          }}
        />
      ))}
    </div>
  );
}
