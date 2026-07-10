import { useEffect, useRef, useState } from "react";
import type { HudState } from "./types";

interface Line {
  id: number;
  angle: number; // radians from center
  segments: { dx: number; dy: number }[]; // right-angle trace
  totalLen: number;
  startedAt: number;
  duration: number; // extend duration
  hold: number;
  retract: number;
  color: string;
}

interface Props {
  state: HudState;
  hue: number;
}

// Build a right-angled circuit trace from origin outward.
function buildSegments(angle: number, reach: number) {
  const steps = 2 + Math.floor(Math.random() * 2);
  const segs: { dx: number; dy: number }[] = [];
  let remaining = reach;
  let dir = angle;
  for (let i = 0; i < steps; i++) {
    const len = i === steps - 1 ? remaining : remaining * (0.35 + Math.random() * 0.35);
    segs.push({ dx: Math.cos(dir) * len, dy: Math.sin(dir) * len });
    remaining -= len;
    // Snap to a right-angle-ish turn
    const turn = (Math.random() < 0.5 ? -1 : 1) * (Math.PI / 2) * (0.6 + Math.random() * 0.4);
    dir += turn;
  }
  const totalLen = segs.reduce((s, p) => s + Math.hypot(p.dx, p.dy), 0);
  return { segs, totalLen };
}

export function NodeLines({ state, hue }: Props) {
  const [lines, setLines] = useState<Line[]>([]);
  const idRef = useRef(0);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const active = state !== "standby";
    const target = active ? 6 : 3;
    const spawnInterval = active ? 550 : 1400;

    const tick = () => {
      setLines((prev) => {
        const now = performance.now();
        // prune finished
        const alive = prev.filter(
          (l) => now - l.startedAt < l.duration + l.hold + l.retract + 200,
        );
        if (alive.length >= target) return alive;
        const angle = Math.random() * Math.PI * 2;
        const reach = 180 + Math.random() * 220;
        const { segs, totalLen } = buildSegments(angle, reach);
        alive.push({
          id: ++idRef.current,
          angle,
          segments: segs,
          totalLen,
          startedAt: now,
          duration: 900 + Math.random() * 500,
          hold: active ? 700 + Math.random() * 500 : 1400 + Math.random() * 900,
          retract: 700 + Math.random() * 400,
          color: `hsl(${hue}, 100%, 65%)`,
        });
        return [...alive];
      });
    };

    tick();
    const id = window.setInterval(tick, spawnInterval);
    return () => window.clearInterval(id);
  }, [state, hue]);

  // Force re-render loop for animation progress
  const [, setTick] = useState(0);
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      setTick((t) => (t + 1) % 1e9);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      ref={containerRef}
      className="pointer-events-none absolute inset-0 flex items-center justify-center"
    >
      <svg width="900" height="900" viewBox="-450 -450 900 900" className="overflow-visible">
        {lines.map((l) => {
          const now = performance.now();
          const t = now - l.startedAt;
          let progress = 0;
          let opacity = 1;
          if (t < l.duration) {
            progress = ease(t / l.duration);
          } else if (t < l.duration + l.hold) {
            progress = 1;
          } else {
            const r = (t - l.duration - l.hold) / l.retract;
            progress = 1 - ease(Math.min(1, r));
            opacity = 1 - Math.min(1, r) * 0.6;
          }

          // Build a path with progress
          let cx = Math.cos(l.angle) * 90; // start at ring edge
          let cy = Math.sin(l.angle) * 90;
          const points: [number, number][] = [[cx, cy]];
          let remaining = progress * l.totalLen;
          for (const s of l.segments) {
            const segLen = Math.hypot(s.dx, s.dy);
            if (remaining <= 0) break;
            const take = Math.min(1, remaining / segLen);
            cx += s.dx * take;
            cy += s.dy * take;
            points.push([cx, cy]);
            remaining -= segLen * take;
          }
          const d = points.map((p, i) => (i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`)).join(" ");
          const [nx, ny] = points[points.length - 1];
          const showNode = progress > 0.98;

          return (
            <g key={l.id} style={{ opacity }}>
              <path
                d={d}
                stroke={l.color}
                strokeWidth={1.1}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ filter: `drop-shadow(0 0 4px ${l.color})` }}
              />
              {showNode && (
                <>
                  <circle cx={nx} cy={ny} r={3} fill={l.color} style={{ filter: `drop-shadow(0 0 6px ${l.color})` }} />
                  <circle cx={nx} cy={ny} r={6} fill="none" stroke={l.color} strokeOpacity={0.4} />
                </>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ease(x: number) {
  return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
}
