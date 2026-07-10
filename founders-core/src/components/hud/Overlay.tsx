import { useEffect } from "react";
import type { OverlayPayload } from "@/lib/dataAdapter";

interface Props {
  payload: OverlayPayload | null;
  onClose: () => void;
}

export function Overlay({ payload, onClose }: Props) {
  useEffect(() => {
    if (!payload) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [payload, onClose]);

  if (!payload) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-hud-fade"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-[min(760px,92vw)] max-h-[80vh] overflow-hidden rounded-lg border border-hud-cyan/40 bg-hud-panel/80 backdrop-blur-md animate-hud-scale-in"
        style={{
          boxShadow:
            "0 0 40px hsla(190, 100%, 55%, 0.25), inset 0 0 40px hsla(190, 100%, 55%, 0.08)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-hud-cyan/25 px-5 py-3">
          <div className="font-orbitron text-[11px] tracking-[0.35em] text-hud-cyan">
            {payload.title}
          </div>
          <button
            onClick={onClose}
            className="font-mono text-[10px] tracking-widest text-hud-cyan/70 hover:text-hud-cyan"
          >
            [ ESC ]
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-6">
          {payload.kind === "chart" && payload.chart && <BarChart data={payload.chart} />}
          {payload.kind === "gauge" && payload.gauges && <Gauges data={payload.gauges} />}
          {payload.kind === "table" && payload.table && (
            <DataTable columns={payload.table.columns} rows={payload.table.rows} />
          )}
          {payload.kind === "report" && payload.report && <Report lines={payload.report} />}
        </div>
      </div>
    </div>
  );
}

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((d) => d.value));
  const W = 620;
  const H = 220;
  const bw = W / data.length - 14;
  return (
    <svg viewBox={`0 0 ${W} ${H + 40}`} className="w-full">
      {data.map((d, i) => {
        const h = (d.value / max) * H;
        const x = i * (bw + 14) + 7;
        return (
          <g key={i}>
            <rect
              x={x}
              y={H - h + 10}
              width={bw}
              height={h}
              fill="url(#barGrad)"
              style={{ filter: "drop-shadow(0 0 6px hsl(190 100% 55%))" }}
            />
            <text
              x={x + bw / 2}
              y={H + 28}
              textAnchor="middle"
              className="fill-hud-cyan/60 font-mono"
              fontSize="10"
              letterSpacing="2"
            >
              {d.label}
            </text>
            <text
              x={x + bw / 2}
              y={H - h + 2}
              textAnchor="middle"
              className="fill-hud-cyan font-mono"
              fontSize="10"
            >
              {d.value}
            </text>
          </g>
        );
      })}
      <defs>
        <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="hsl(190 100% 70%)" />
          <stop offset="100%" stopColor="hsl(210 100% 40%)" />
        </linearGradient>
      </defs>
    </svg>
  );
}

function Gauges({ data }: { data: { label: string; value: number; max: number; unit?: string }[] }) {
  return (
    <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
      {data.map((g, i) => {
        const pct = g.value / g.max;
        const r = 40;
        const c = 2 * Math.PI * r * 0.75;
        return (
          <div key={i} className="flex flex-col items-center">
            <svg width="110" height="110" viewBox="0 0 110 110">
              <circle
                cx="55"
                cy="55"
                r={r}
                fill="none"
                stroke="hsl(190 60% 25%)"
                strokeWidth="6"
                strokeDasharray={`${c} 999`}
                strokeDashoffset="0"
                transform="rotate(135 55 55)"
                strokeLinecap="round"
              />
              <circle
                cx="55"
                cy="55"
                r={r}
                fill="none"
                stroke="hsl(190 100% 60%)"
                strokeWidth="6"
                strokeDasharray={`${c * pct} 999`}
                transform="rotate(135 55 55)"
                strokeLinecap="round"
                style={{ filter: "drop-shadow(0 0 6px hsl(190 100% 60%))" }}
              />
              <text
                x="55"
                y="58"
                textAnchor="middle"
                className="fill-hud-cyan font-orbitron"
                fontSize="18"
              >
                {g.value}
                <tspan fontSize="10" className="fill-hud-cyan/60">
                  {g.unit || ""}
                </tspan>
              </text>
            </svg>
            <div className="mt-1 font-mono text-[10px] tracking-[0.3em] text-hud-cyan/70">
              {g.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: { status: "pending" | "urgent" | "resolved"; cells: string[] }[];
}) {
  const color = {
    urgent: "text-hud-red border-l-hud-red",
    pending: "text-hud-amber border-l-hud-amber",
    resolved: "text-hud-green border-l-hud-green",
  };
  return (
    <table className="w-full font-mono text-[12px]">
      <thead>
        <tr className="text-hud-cyan/60">
          {columns.map((c) => (
            <th key={c} className="px-3 py-2 text-left tracking-[0.2em]">
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr
            key={i}
            className={`border-l-2 ${color[r.status]} border-b border-hud-cyan/10 hover:bg-hud-cyan/5`}
          >
            {r.cells.map((cell, j) => (
              <td key={j} className="px-3 py-2">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Report({ lines }: { lines: string[] }) {
  return (
    <div className="space-y-2 font-mono text-[12px] text-hud-cyan/90">
      {lines.map((l, i) => (
        <div
          key={i}
          className="animate-hud-fade border-l border-hud-cyan/30 pl-3"
          style={{ animationDelay: `${i * 80}ms` }}
        >
          {l}
        </div>
      ))}
    </div>
  );
}
