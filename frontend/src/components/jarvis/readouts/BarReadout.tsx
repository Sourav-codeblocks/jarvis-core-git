export type BarDatum = { label: string; value: number; max?: number; tone?: "cyan" | "amber" | "red" | "green" };

export function BarReadout({ data, unit }: { data: BarDatum[]; unit?: string }) {
  const overallMax = Math.max(...data.map((d) => d.max ?? d.value), 1);
  const toneColor = (t: BarDatum["tone"]) =>
    t === "amber" ? "var(--jv-amber)" : t === "red" ? "var(--jv-red)" : t === "green" ? "var(--jv-green)" : "var(--jv-cyan)";

  return (
    <div className="relative h-72 w-full">
      {/* grid */}
      <div className="absolute inset-0 flex flex-col justify-between">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="font-mono text-[9px] text-white/25 w-8 text-right">
              {Math.round(((4 - i) / 4) * overallMax)}
            </span>
            <div className="h-px flex-1 bg-[color:var(--jv-cyan)]/10" />
          </div>
        ))}
      </div>

      {/* bars */}
      <div className="absolute inset-0 pl-10 flex items-end justify-around gap-3 pb-6">
        {data.map((d, i) => {
          const c = toneColor(d.tone);
          const pct = Math.min(1, d.value / overallMax);
          return (
            <div key={i} className="relative flex h-full flex-1 flex-col items-center justify-end">
              <div
                className="relative w-full max-w-[52px] rounded-t-sm origin-bottom"
                style={{
                  height: `${pct * 100}%`,
                  background: `linear-gradient(180deg, ${c} 0%, color-mix(in oklab, ${c} 30%, transparent) 100%)`,
                  boxShadow: `0 -8px 24px -2px ${c}, inset 0 0 12px color-mix(in oklab, ${c} 50%, transparent)`,
                  animation: `jv-bar-rise 700ms cubic-bezier(0.2,0.9,0.3,1) ${i * 80}ms both`,
                }}
              >
                <span
                  className="absolute -top-6 left-1/2 -translate-x-1/2 font-mono text-[11px] font-bold"
                  style={{ color: c, textShadow: `0 0 8px ${c}` }}
                >
                  {d.value}
                  {unit ?? ""}
                </span>
                {/* top bleed */}
                <span
                  className="absolute -top-1 left-0 h-1 w-full"
                  style={{ background: c, boxShadow: `0 0 14px ${c}` }}
                />
              </div>
              <span className="mt-2 font-mono text-[10px] tracking-widest text-white/60 truncate max-w-full">
                {d.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
