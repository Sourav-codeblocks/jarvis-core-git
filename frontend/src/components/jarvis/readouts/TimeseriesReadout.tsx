import { useMemo } from "react";

export type SeriesPoint = { label: string; value: number };

export function TimeseriesReadout({ data, unit }: { data: SeriesPoint[]; unit?: string }) {
  const { path, area, points, max, len } = useMemo(() => {
    const W = 560, H = 220, P = 24;
    const max = Math.max(...data.map((d) => d.value), 1);
    const step = (W - P * 2) / Math.max(1, data.length - 1);
    const pts = data.map((d, i) => ({
      x: P + i * step,
      y: H - P - (d.value / max) * (H - P * 2),
      label: d.label,
      value: d.value,
    }));
    const path = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const area = `${path} L ${pts[pts.length - 1].x} ${H - P} L ${pts[0].x} ${H - P} Z`;
    // rough path length estimate
    let len = 0;
    for (let i = 1; i < pts.length; i++) {
      len += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    }
    return { path, area, points: pts, max, len };
  }, [data]);

  return (
    <div className="relative w-full">
      <svg viewBox="0 0 560 220" className="w-full">
        <defs>
          <linearGradient id="ts-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--jv-cyan)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--jv-cyan)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="ts-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--jv-cyan)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="var(--jv-cyan)" stopOpacity="1" />
          </linearGradient>
        </defs>

        {/* faint horizontal ticks (no solid axis) */}
        {[0.25, 0.5, 0.75].map((t) => (
          <g key={t}>
            <line
              x1="24"
              x2="536"
              y1={24 + (220 - 48) * (1 - t)}
              y2={24 + (220 - 48) * (1 - t)}
              stroke="var(--jv-cyan)"
              strokeOpacity="0.08"
              strokeDasharray="2 6"
            />
            <text x="12" y={24 + (220 - 48) * (1 - t) + 3} fill="rgba(255,255,255,0.35)" fontSize="8" fontFamily="JetBrains Mono">
              {Math.round(max * t)}
            </text>
          </g>
        ))}

        <path d={area} fill="url(#ts-area)" />
        <path
          d={path}
          fill="none"
          stroke="url(#ts-line)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            filter: "drop-shadow(0 0 6px var(--jv-cyan))",
            strokeDasharray: len,
            // @ts-expect-error css var
            "--path-len": len,
            animation: "jv-comet 1100ms cubic-bezier(0.2,0.9,0.3,1) both",
          }}
        />
        {points.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="2.5" fill="var(--jv-cyan)" style={{ filter: "drop-shadow(0 0 6px var(--jv-cyan))" }} />
            <text
              x={p.x}
              y={210}
              textAnchor="middle"
              fill="rgba(255,255,255,0.5)"
              fontSize="9"
              fontFamily="JetBrains Mono"
              letterSpacing="1"
            >
              {p.label}
            </text>
          </g>
        ))}
      </svg>
      {unit && (
        <div className="absolute right-2 top-2 font-mono text-[10px] tracking-widest text-white/40">
          UNIT · {unit}
        </div>
      )}
    </div>
  );
}
