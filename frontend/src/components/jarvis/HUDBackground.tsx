import { useEffect, useRef, useState } from "react";

export function HUDBackground() {
  return (
    <>
      {/* deep universe radial base */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse at center, color-mix(in oklab, var(--jv-cyan-dim) 22%, #030308) 0%, #050510 45%, #010104 100%)",
        }}
      />
      {/* faint distant nebula wash — complements, doesn't compete */}
      <div
        className="pointer-events-none fixed inset-0 z-0 opacity-[0.35]"
        style={{
          background: `
            radial-gradient(600px 400px at 12% 18%, color-mix(in oklab, var(--jv-cyan-alt) 18%, transparent), transparent 70%),
            radial-gradient(700px 500px at 88% 82%, color-mix(in oklab, var(--jv-cyan-alt2) 14%, transparent), transparent 70%),
            radial-gradient(500px 500px at 82% 20%, color-mix(in oklab, var(--jv-cyan) 10%, transparent), transparent 70%)
          `,
          filter: "blur(20px)",
        }}
      />
      {/* animated starfield */}
      <Starfield />
      {/* corner telemetry */}
      <TelemetryCorners />
    </>
  );
}

function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, DPR = 1, raf = 0;
    type Star = { x: number; y: number; r: number; base: number; twk: number; phase: number };
    let stars: Star[] = [];

    const resize = () => {
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth; H = window.innerHeight;
      canvas.width = W * DPR; canvas.height = H * DPR;
      canvas.style.width = W + "px"; canvas.style.height = H + "px";
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      const count = Math.floor((W * H) / 5200);
      stars = Array.from({ length: count }).map(() => ({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() < 0.92 ? Math.random() * 0.9 + 0.2 : Math.random() * 1.6 + 0.9,
        base: 0.3 + Math.random() * 0.6,
        twk: 0.6 + Math.random() * 2.4,
        phase: Math.random() * Math.PI * 2,
      }));
    };
    resize();
    window.addEventListener("resize", resize);

    const start = performance.now();
    const loop = (now: number) => {
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, W, H);
      for (const s of stars) {
        const a = s.base * (0.55 + 0.45 * Math.sin(t * s.twk + s.phase));
        ctx.fillStyle = `rgba(230,238,255,${a})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);
  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0"
      aria-hidden
    />
  );
}

function TelemetryCorners() {
  const [ts, setTs] = useState("—");
  useEffect(() => {
    const tick = () => setTs(new Date().toISOString().replace("T", " ").slice(0, 19));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);
  const items = [
    { pos: "top-4 left-4", lines: ["J.A.R.V.I.S // v4.17.2", "NODE 07 · SEC · UPLINK OK", `T+ ${ts}`] },
    { pos: "top-4 right-4 text-right", lines: ["LAT 40.7128° N", "LON 74.0060° W", "SIG ▮▮▮▮▯"] },
    { pos: "bottom-4 left-4", lines: ["PWR 98.4%", "CPU 12% · MEM 42%", "CH.03 ENCRYPTED"] },
    { pos: "bottom-4 right-4 text-right", lines: ["OWNER CLEARANCE · Ω", "STREAM 01–07 SYNC", "◉ REC LIVE"] },
  ];
  return (
    <>
      {items.map((it, i) => (
        <div
          key={i}
          className={`pointer-events-none fixed ${it.pos} z-10 font-mono text-[10px] tracking-widest text-[color:var(--jv-cyan)]/50`}
        >
          {it.lines.map((l, j) => (
            <div key={j}>{l}</div>
          ))}
        </div>
      ))}
    </>
  );
}
