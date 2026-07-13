import { useEffect, useRef, useState } from "react";
import type { HudState } from "./types";

interface Props {
  state: HudState;
  compact?: boolean;
  onSpin?: () => void;
  children?: React.ReactNode;
}

const BASE_COLORS: Record<HudState, { hue: number; sat: number }> = {
  standby: { hue: 195, sat: 55 },
  listening: { hue: 205, sat: 100 },
  call: { hue: 138, sat: 100 },
  thinking: { hue: 265, sat: 90 },
  typing: { hue: 40, sat: 100 },
};

// Standby cycles through an alien palette every few seconds.
const STANDBY_CYCLE = [195, 175, 220, 270, 300, 160];

export function Ring({ state, compact, onSpin, children }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const spinBoostRef = useRef(0); // decays each frame
  const [cycleIdx, setCycleIdx] = useState(0);
  const [spinning, setSpinning] = useState(false);

  // Cycle standby hue slowly
  useEffect(() => {
    if (state !== "standby") return;
    const id = setInterval(() => setCycleIdx((i) => (i + 1) % STANDBY_CYCLE.length), 5200);
    return () => clearInterval(id);
  }, [state]);

  const base = BASE_COLORS[state];
  const hue = state === "standby" ? STANDBY_CYCLE[cycleIdx] : base.hue;
  const sat = base.sat;

  const handleClick = () => {
    spinBoostRef.current = 0.35; // strong initial angular velocity
    setSpinning(true);
    setTimeout(() => setSpinning(false), 1400);
    onSpin?.();
  };

  // 3D dotted sphere inside the ring
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const size = compact ? 140 : 440;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cx = size / 2;
    const cy = size / 2;
    const R = size * 0.30;

    const N = 520;
    const dots: { theta: number; phi: number }[] = [];
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2;
      const goldenAngle = Math.PI * (3 - Math.sqrt(5));
      dots.push({ theta: goldenAngle * i, phi: Math.acos(y) });
    }

    let t = 0;
    const render = () => {
      const baseSpeed =
        state === "standby" ? 0.004 : state === "thinking" ? 0.014 : 0.009;
      t += baseSpeed + spinBoostRef.current;
      // decay spin boost
      spinBoostRef.current *= 0.94;
      if (spinBoostRef.current < 0.0005) spinBoostRef.current = 0;

      ctx.clearRect(0, 0, size, size);
      const activeBoost = state === "standby" ? 0.55 : 1;

      for (const d of dots) {
        const sinP = Math.sin(d.phi);
        const cosP = Math.cos(d.phi);
        const a = d.theta + t;
        const x3 = sinP * Math.cos(a);
        const z3 = sinP * Math.sin(a);
        const y3 = cosP;
        const depth = (z3 + 1) / 2;
        const px = cx + x3 * R;
        const py = cy + y3 * R;
        const size2 = 0.4 + depth * 1.9;
        const alpha = (0.08 + depth * 0.85) * activeBoost;
        ctx.beginPath();
        ctx.arc(px, py, size2, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue}, ${sat}%, ${55 + depth * 25}%, ${alpha})`;
        ctx.fill();
      }
      rafRef.current = requestAnimationFrame(render);
    };
    render();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [state, compact, hue, sat]);

  const size = compact ? 140 : 440;
  const active = state !== "standby";
  const glowStrength = state === "standby" ? 22 : state === "thinking" ? 45 : 75;

  return (
    <div
      aria-label="Assistant ring"
      className="group relative"
      style={{ width: size, height: size }}
    >
      {/* Outer bleed glow */}
      <div
        aria-hidden
        className="absolute inset-0 rounded-full transition-[opacity,filter] duration-[800ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{
          background: `radial-gradient(circle, hsla(${hue}, ${sat}%, 55%, ${
            active ? 0.6 : 0.28
          }) 0%, transparent 62%)`,
          filter: `blur(${active ? 32 : 18}px)`,
          opacity: active ? 1 : 0.8,
          transition: "background 1200ms ease, filter 800ms ease",
        }}
      />
      {/* Breathing wrapper */}
      <div className="absolute inset-0 animate-hud-breathe">
        {/* Forged metal ring */}
        <div
          className="absolute inset-[3%] rounded-full"
          style={{
            padding: size * 0.045,
            transition:
              "background 1200ms ease, box-shadow 800ms ease, transform 1400ms cubic-bezier(0.22,1,0.36,1)",
            transform: spinning ? "rotate(720deg)" : "rotate(0deg)",
            background: `conic-gradient(from 220deg,
              hsl(${hue}, ${sat}%, 8%),
              hsl(${hue}, ${sat}%, ${active ? 72 : 45}%),
              hsl(${hue}, 20%, 92%),
              hsl(${hue}, ${sat}%, ${active ? 55 : 30}%),
              hsl(${hue}, ${sat}%, 6%),
              hsl(${hue}, ${sat}%, ${active ? 68 : 42}%),
              hsl(${hue}, ${sat}%, 10%))`,
            boxShadow: `
              0 0 ${glowStrength}px hsla(${hue}, ${sat}%, 60%, ${active ? 0.9 : 0.45}),
              0 0 ${glowStrength * 1.8}px hsla(${hue}, ${sat}%, 55%, ${active ? 0.5 : 0.2}),
              inset 0 4px 12px hsla(0, 0%, 100%, 0.35),
              inset 0 -6px 14px hsla(0, 0%, 0%, 0.55),
              inset 0 0 2px hsla(${hue}, ${sat}%, 95%, 0.9)`,
            borderRadius: "50%",
          }}
        >
          {/* Alien texture etched into the metal — glyph ring + noise */}
          <AlienEtch hue={hue} sat={sat} />

          {/* Inner cavity */}
          <div
            className="relative h-full w-full overflow-hidden rounded-full cursor-pointer"
            onClick={handleClick}
            role="button"
            aria-label="Pulse ring"
            style={{
              background: `radial-gradient(circle at 40% 38%,
                hsla(${hue}, ${sat}%, ${active ? 18 : 8}%, 0.95),
                hsla(0, 0%, 0%, 0.98) 78%)`,
              boxShadow: `
                inset 0 6px 18px hsla(0, 0%, 0%, 0.85),
                inset 0 0 ${active ? 70 : 40}px hsla(${hue}, ${sat}%, 45%, ${
                  active ? 0.7 : 0.35
                })`,
              transition: "background 1200ms ease, box-shadow 800ms ease",
            }}
          >
            <canvas
              ref={canvasRef}
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 mix-blend-screen"
            />
            <div
              aria-hidden
              className="absolute inset-0 rounded-full pointer-events-none"
              style={{
                background: `radial-gradient(circle at 30% 25%, hsla(0,0%,100%,0.08), transparent 45%)`,
              }}
            />
          </div>
        </div>

        {active && (
          <>
            <span
              aria-hidden
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full animate-hud-flare"
              style={{
                width: size * 1.05,
                height: size * 1.05,
                background: `radial-gradient(circle, hsla(${hue}, ${sat}%, 65%, 0.3), transparent 55%)`,
                filter: "blur(20px)",
              }}
            />
            <span
              aria-hidden
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full animate-hud-flare-slow"
              style={{
                width: size * 0.94,
                height: size * 0.94,
                border: `1px solid hsla(${hue}, ${sat}%, 78%, 0.3)`,
              }}
            />
          </>
        )}
      </div>

      {children && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="pointer-events-auto">{children}</div>
        </div>
      )}
    </div>
  );
}

// Alien-glyph etching that lives on the ring's metal face.
function AlienEtch({ hue, sat }: { hue: number; sat: number }) {
  // Deterministic glyph marks around the ring
  const marks = Array.from({ length: 48 }, (_, i) => i);
  return (
    <svg
      aria-hidden
      viewBox="0 0 100 100"
      className="pointer-events-none absolute inset-0 h-full w-full animate-hud-etch-spin"
      style={{ mixBlendMode: "screen" }}
    >
      <defs>
        <radialGradient id="etchMask" cx="50%" cy="50%" r="50%">
          <stop offset="70%" stopColor="white" stopOpacity="0" />
          <stop offset="82%" stopColor="white" stopOpacity="1" />
          <stop offset="94%" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id="ringMask">
          <rect width="100" height="100" fill="url(#etchMask)" />
        </mask>
      </defs>
      <g mask="url(#ringMask)" stroke={`hsla(${hue}, ${sat}%, 90%, 0.55)`} strokeWidth="0.18" fill="none">
        {/* concentric hairlines */}
        <circle cx="50" cy="50" r="43" />
        <circle cx="50" cy="50" r="46" strokeDasharray="0.6 1.2" />
        <circle cx="50" cy="50" r="40" strokeDasharray="0.3 3" />
        {/* radial glyph ticks */}
        {marks.map((i) => {
          const a = (i / marks.length) * Math.PI * 2;
          const r1 = 41 + (i % 3) * 0.8;
          const r2 = i % 4 === 0 ? 46 : 44.5;
          const x1 = 50 + Math.cos(a) * r1;
          const y1 = 50 + Math.sin(a) * r1;
          const x2 = 50 + Math.cos(a) * r2;
          const y2 = 50 + Math.sin(a) * r2;
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />;
        })}
        {/* stray alien runes */}
        {[0, 90, 180, 270].map((deg, i) => (
          <g key={i} transform={`rotate(${deg} 50 50) translate(50 8)`}>
            <path d="M -2 0 L 0 -1.2 L 2 0 L 0 1.2 Z" />
            <circle cx="0" cy="0" r="0.4" />
          </g>
        ))}
      </g>
    </svg>
  );
}
