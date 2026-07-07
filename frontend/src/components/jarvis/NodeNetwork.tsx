import { useEffect, useRef } from "react";

/**
 * Proton/electron-style particle system orbiting the nucleus.
 * Canvas-based for smoothness. Reads --jv-cyan (and its dim variant)
 * from the parent so it re-tints when the theme changes.
 */
type Particle = {
  // polar position relative to center
  r: number;
  theta: number;
  // angular velocity (rad/s), radial velocity (px/s)
  omega: number;
  vr: number;
  size: number;
  life: number; // seconds alive
  ttl: number;
  // orbital hold — if >0, particle briefly locks radial velocity
  holdUntil: number;
  // trail buffer of previous xy positions
  trail: { x: number; y: number }[];
  trailMax: number;
  hueShift: number; // 0..1 blend between accent and accentAlt
};

const MIN_R = 90;
const MAX_R = 320;

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function NodeNetwork({
  intensity = 1,
  brightness = 0.6,
}: {
  intensity?: number;
  brightness?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef<number | null>(null);
  const lastSpawnRef = useRef(0);
  const cfgRef = useRef({ intensity, brightness });
  cfgRef.current = { intensity, brightness };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement!;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, CX = 0, CY = 0, DPR = 1;

    const resize = () => {
      const rect = parent.getBoundingClientRect();
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = rect.width;
      H = rect.height;
      CX = W / 2;
      CY = H / 2;
      canvas.width = W * DPR;
      canvas.height = H * DPR;
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(parent);

    const spawn = () => {
      const theta = Math.random() * Math.PI * 2;
      const r = MAX_R + Math.random() * 40;
      const speed = 0.4 + Math.random() * 0.9; // radial inward
      const omega = (Math.random() < 0.5 ? 1 : -1) * (0.25 + Math.random() * 0.8);
      const size = 1 + Math.random() * 1.8;
      const ttl = 4 + Math.random() * 4;
      const willOrbit = Math.random() < 0.35;
      const trailMax = Math.round(10 + speed * 22);
      particlesRef.current.push({
        r,
        theta,
        omega,
        vr: -speed * 60, // inward
        size,
        life: 0,
        ttl,
        holdUntil: willOrbit ? 1 + Math.random() * 2 : 0,
        trail: [],
        trailMax,
        hueShift: Math.random(),
      });
    };

    let prev = performance.now();
    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;

      // Resolve accents from CSS vars (cheap read once per frame)
      const cs = getComputedStyle(canvas);
      const accent = cs.getPropertyValue("--jv-cyan").trim() || "#4361ee";
      const accentAlt = cs.getPropertyValue("--jv-cyan-alt").trim() || accent;
      const [ar, ag, ab] = hexToRgb(accent);
      const [br, bg, bb] = hexToRgb(accentAlt);

      // Spawn control
      const { intensity: I, brightness: B } = cfgRef.current;
      const target = Math.round(3 + I * 5); // total particles target (reduced ~half)
      lastSpawnRef.current += dt;
      const spawnEvery = 0.12 / Math.max(0.4, I);
      while (
        particlesRef.current.length < target &&
        lastSpawnRef.current > spawnEvery
      ) {
        lastSpawnRef.current -= spawnEvery;
        spawn();
      }

      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";

      const survivors: Particle[] = [];
      for (const p of particlesRef.current) {
        p.life += dt;

        // update radial: if in "hold" window and close-in, damp vr
        if (p.holdUntil > 0 && p.r < 160) {
          p.vr *= Math.max(0, 1 - dt * 1.6);
          p.holdUntil -= dt;
        } else {
          // slight inward acceleration then outward past nucleus
          if (p.r < 40) p.vr = Math.abs(p.vr) * 0.9; // bounce through
        }
        p.r += p.vr * dt * (0.6 + 0.4 * cfgRef.current.intensity);
        p.theta += p.omega * dt;

        const x = CX + Math.cos(p.theta) * p.r;
        const y = CY + Math.sin(p.theta) * p.r;

        p.trail.push({ x, y });
        if (p.trail.length > p.trailMax) p.trail.shift();

        // lifecycle: kill when out of bounds or ttl
        const fade =
          p.life < 0.5
            ? p.life / 0.5
            : p.life > p.ttl - 0.6
              ? Math.max(0, (p.ttl - p.life) / 0.6)
              : 1;
        if (p.life > p.ttl || p.r > MAX_R + 160 || p.r < 5) {
          continue;
        }

        // blend colors
        const t = p.hueShift;
        const rr = Math.round(ar * (1 - t) + br * t);
        const gg = Math.round(ag * (1 - t) + bg * t);
        const bbc = Math.round(ab * (1 - t) + bb * t);
        const col = (a: number) => `rgba(${rr},${gg},${bbc},${a * B * fade})`;

        // draw trail as a stroked polyline with tapering alpha
        if (p.trail.length > 2) {
          for (let i = 1; i < p.trail.length; i++) {
            const a0 = (i / p.trail.length) * 0.6;
            ctx.strokeStyle = col(a0);
            ctx.lineWidth = p.size * (i / p.trail.length) * 1.4;
            ctx.beginPath();
            ctx.moveTo(p.trail[i - 1].x, p.trail[i - 1].y);
            ctx.lineTo(p.trail[i].x, p.trail[i].y);
            ctx.stroke();
          }
        }

        // head glow
        const grad = ctx.createRadialGradient(x, y, 0, x, y, p.size * 6);
        grad.addColorStop(0, col(1));
        grad.addColorStop(0.4, col(0.5));
        grad.addColorStop(1, col(0));
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(x, y, p.size * 6, 0, Math.PI * 2);
        ctx.fill();

        // sharp core
        ctx.fillStyle = col(1);
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();

        survivors.push(p);
      }
      particlesRef.current = survivors;
      ctx.globalCompositeOperation = "source-over";

      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0 h-full w-full"
      aria-hidden
    />
  );
}
