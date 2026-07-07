import { useEffect } from "react";
import { X } from "lucide-react";
import { BarReadout, type BarDatum } from "./readouts/BarReadout";
import { GaugeReadout } from "./readouts/GaugeReadout";
import { TimeseriesReadout, type SeriesPoint } from "./readouts/TimeseriesReadout";
import { TableReadout, type TableRow } from "./readouts/TableReadout";

export type OverlayPayload =
  | { type: "chart"; label: string; freshness: "LIVE" | "ARCHIVED"; content: { data: BarDatum[]; unit?: string } }
  | { type: "gauge"; label: string; freshness: "LIVE" | "ARCHIVED"; content: { value: number; sublabel?: string; tone?: "cyan" | "amber" | "green" | "red"; unit?: string } }
  | { type: "timeseries"; label: string; freshness: "LIVE" | "ARCHIVED"; content: { data: SeriesPoint[]; unit?: string } }
  | { type: "table"; label: string; freshness: "LIVE" | "ARCHIVED"; content: { columns: string[]; rows: TableRow[] } };

export function DataOverlay({ payload, onClose }: { payload: OverlayPayload; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center px-6"
      onClick={onClose}
      style={{ animation: "jv-fade-slide-in 300ms ease-out both" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="jv-panel relative w-full max-w-3xl rounded-lg p-8"
        style={{ animation: "jv-scan-in 550ms cubic-bezier(0.2,0.9,0.3,1) both" }}
      >
        {/* Corner brackets */}
        <CornerBrackets />

        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-6">
          <div>
            <div className="font-mono text-[10px] tracking-[0.3em] text-white/40">
              READOUT · {payload.type.toUpperCase()}
            </div>
            <h2 className="mt-1 font-display text-2xl font-bold jv-tracking jv-glow-cyan">
              {payload.label}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded border px-2 py-1 font-mono text-[10px] tracking-[0.25em] ${
                payload.freshness === "LIVE"
                  ? "border-[color:var(--jv-green)]/40 text-[color:var(--jv-green)]"
                  : "border-[color:var(--jv-amber)]/40 text-[color:var(--jv-amber)]"
              }`}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: payload.freshness === "LIVE" ? "var(--jv-green)" : "var(--jv-amber)",
                  boxShadow: `0 0 8px ${payload.freshness === "LIVE" ? "var(--jv-green)" : "var(--jv-amber)"}`,
                  animation: "jv-blink 1.4s ease-in-out infinite",
                }}
              />
              {payload.freshness === "LIVE" ? "LIVE READOUT" : "ARCHIVED"}
            </span>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-full border border-[color:var(--jv-cyan)]/30 text-[color:var(--jv-cyan)] hover:bg-[color:var(--jv-cyan)]/10"
              aria-label="Close overlay"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="min-h-[280px]">
          {payload.type === "chart" && <BarReadout data={payload.content.data} unit={payload.content.unit} />}
          {payload.type === "gauge" && (
            <GaugeReadout
              value={payload.content.value}
              label={payload.content.sublabel}
              tone={payload.content.tone}
              unit={payload.content.unit}
            />
          )}
          {payload.type === "timeseries" && (
            <TimeseriesReadout data={payload.content.data} unit={payload.content.unit} />
          )}
          {payload.type === "table" && (
            <TableReadout columns={payload.content.columns} rows={payload.content.rows} />
          )}
        </div>

        {/* Footer hint */}
        <div className="mt-6 flex items-center justify-between font-mono text-[10px] tracking-[0.3em] text-white/35">
          <span>◤ READ-ONLY ◢</span>
          <span className="rounded border border-white/15 px-2 py-1">✕ ESC · CLICK OUTSIDE TO CLOSE</span>
        </div>
      </div>
    </div>
  );
}

function CornerBrackets() {
  const common = "absolute h-4 w-4 border-[color:var(--jv-cyan)]";
  return (
    <>
      <span className={`${common} left-0 top-0 border-l-2 border-t-2`} />
      <span className={`${common} right-0 top-0 border-r-2 border-t-2`} />
      <span className={`${common} bottom-0 left-0 border-b-2 border-l-2`} />
      <span className={`${common} bottom-0 right-0 border-b-2 border-r-2`} />
    </>
  );
}
