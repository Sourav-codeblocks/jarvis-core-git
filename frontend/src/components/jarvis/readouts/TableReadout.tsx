export type TableRow = {
  id: string;
  status: "pending" | "fulfilled" | "urgent";
  cells: string[];
};

export function TableReadout({ columns, rows }: { columns: string[]; rows: TableRow[] }) {
  const tone = (s: TableRow["status"]) =>
    s === "urgent" ? "var(--jv-red)" : s === "pending" ? "var(--jv-amber)" : "var(--jv-green)";
  const label = (s: TableRow["status"]) =>
    s === "urgent" ? "OVERDUE" : s === "pending" ? "PENDING" : "FULFILLED";

  return (
    <div className="w-full">
      <div
        className="grid gap-3 border-b border-[color:var(--jv-cyan)]/20 pb-2 font-mono text-[10px] tracking-[0.25em] text-white/40"
        style={{ gridTemplateColumns: `84px repeat(${columns.length}, minmax(0,1fr))` }}
      >
        <span>STATUS</span>
        {columns.map((c) => (
          <span key={c}>{c}</span>
        ))}
      </div>
      <div className="mt-2 flex flex-col">
        {rows.map((r, i) => {
          const c = tone(r.status);
          return (
            <div
              key={r.id}
              className="grid items-center gap-3 border-l-2 py-2 pl-3 pr-2 hover:bg-white/[0.02]"
              style={{
                gridTemplateColumns: `84px repeat(${columns.length}, minmax(0,1fr))`,
                borderLeftColor: c,
                animation: `jv-fade-slide-in 380ms ease-out ${i * 40}ms both`,
              }}
            >
              <span
                className="font-mono text-[10px] font-bold tracking-[0.2em]"
                style={{ color: c, textShadow: `0 0 8px ${c}` }}
              >
                {label(r.status)}
              </span>
              {r.cells.map((cell, j) => (
                <span key={j} className="font-mono text-xs text-white/80 truncate">
                  {cell}
                </span>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
