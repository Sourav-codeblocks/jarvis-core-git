import { FOUNDER_REPORTS, type FounderReport } from "@/lib/dataAdapter";

interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (r: FounderReport) => void;
}

export function ReportsBanner({ open, onClose, onPick }: Props) {
  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-24 transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
      style={{
        transform: open ? "translateY(0)" : "translateY(120%)",
        opacity: open ? 1 : 0,
      }}
      aria-hidden={!open}
    >
      <div
        className="pointer-events-auto w-full max-w-4xl rounded-lg border border-hud-cyan/40 bg-hud-panel/80 p-4 backdrop-blur-md"
        style={{
          boxShadow:
            "0 0 40px hsla(190, 100%, 55%, 0.25), inset 0 0 40px hsla(190, 100%, 55%, 0.06)",
        }}
      >
        <div className="mb-3 flex items-center justify-between px-1">
          <div className="font-orbitron text-[10px] tracking-[0.4em] text-hud-cyan/80">
            REPORTS · {FOUNDER_REPORTS.length} AVAILABLE
          </div>
          <button
            onClick={onClose}
            className="font-mono text-[10px] tracking-widest text-hud-cyan/60 hover:text-hud-cyan"
          >
            [ CLOSE ]
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {FOUNDER_REPORTS.map((r) => (
            <button
              key={r.id}
              onClick={() => onPick(r)}
              className="group relative overflow-hidden rounded-md border border-hud-cyan/25 bg-hud-cyan/[0.03] p-3 text-left transition-all hover:-translate-y-0.5 hover:border-hud-cyan/70 hover:bg-hud-cyan/[0.08]"
            >
              <div className="font-orbitron text-[11px] tracking-[0.3em] text-hud-cyan">
                {r.label}
              </div>
              <div className="mt-1 font-mono text-[10px] tracking-widest text-hud-cyan/50">
                {r.hint}
              </div>
              <span
                aria-hidden
                className="absolute inset-x-0 bottom-0 h-[2px] origin-left scale-x-0 bg-hud-cyan transition-transform duration-300 group-hover:scale-x-100"
              />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
