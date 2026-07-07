export function GaugeReadout({
  value,
  label,
  tone = "cyan",
  unit = "%",
}: {
  value: number;
  label?: string;
  tone?: "cyan" | "amber" | "green" | "red";
  unit?: string;
}) {
  const color =
    tone === "amber" ? "var(--jv-amber)" : tone === "green" ? "var(--jv-green)" : tone === "red" ? "var(--jv-red)" : "var(--jv-cyan)";
  const pct = Math.max(0, Math.min(100, value));
  const R = 100;
  const START = 135;
  const END = 405;
  const sweep = END - START; // 270deg
  const arcLen = (2 * Math.PI * R * sweep) / 360;
  const target = arcLen * (1 - pct / 100);

  return (
    <div className="relative mx-auto flex h-72 w-72 items-center justify-center">
      <svg viewBox="-120 -120 240 240" className="h-full w-full -rotate-[135deg]">
        <defs>
          <linearGradient id="gauge-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={color} stopOpacity="0.2" />
            <stop offset="100%" stopColor={color} stopOpacity="1" />
          </linearGradient>
        </defs>
        {/* track */}
        <circle
          r={R}
          fill="none"
          stroke={color}
          strokeOpacity="0.12"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${arcLen} ${2 * Math.PI * R}`}
        />
        {/* value */}
        <circle
          r={R}
          fill="none"
          stroke="url(#gauge-grad)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${arcLen} ${2 * Math.PI * R}`}
          strokeDashoffset={target}
          style={{
            filter: `drop-shadow(0 0 10px ${color})`,
            // @ts-expect-error css var
            "--arc-len": `${arcLen}`,
            "--arc-target": `${target}`,
            animation: "jv-arc-sweep 900ms cubic-bezier(0.2,0.9,0.3,1) both",
          }}
        />
        {/* tick marks */}
        {Array.from({ length: 28 }).map((_, i) => {
          const a = (START + (i / 27) * sweep) * (Math.PI / 180);
          const inner = 82;
          const outer = i % 4 === 0 ? 70 : 76;
          return (
            <line
              key={i}
              x1={Math.cos(a) * outer}
              y1={Math.sin(a) * outer}
              x2={Math.cos(a) * inner}
              y2={Math.sin(a) * inner}
              stroke={color}
              strokeOpacity={i % 4 === 0 ? 0.6 : 0.2}
              strokeWidth="1"
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div
          className="font-display text-5xl font-black jv-tracking"
          style={{ color, textShadow: `0 0 20px ${color}` }}
        >
          {pct.toFixed(0)}
          <span className="text-2xl">{unit}</span>
        </div>
        {label && (
          <div className="mt-1 font-mono text-[10px] tracking-[0.3em] text-white/50">
            {label}
          </div>
        )}
      </div>
    </div>
  );
}
