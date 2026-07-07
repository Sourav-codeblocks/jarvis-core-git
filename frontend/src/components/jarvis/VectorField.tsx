import { useEffect, useRef } from "react";

/**
 * Outer ambient "vector field" — sparse drifting points suggesting an
 * abstract multi-dimensional data space. Sits behind the nucleus (low z)
 * at very low opacity. Confined to the outer margin of the viewport so
 * it never overlaps the core.
 */

type Dot = {
  x: number; // 0..1 across screen
  y: number;
  vx: number; // small drift
  vy: number;
  size: number;
  pulse: number;
  phase: number;
};

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function VectorField({ count = 90 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dotsRef = useRef<Dot[]>([]);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, DPR = 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = rect.width; H = rect.height;
      canvas.width = W * DPR; canvas.height = H * DPR;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // Only place dots in the outer band — avoid the central 45% ellipse.
    const dots: Dot[] = [];
    let safety = 0;
    while (dots.length < count && safety < count * 40) {
      safety++;
      const x = Math.random();
      const y = Math.random();
      const nx = (x - 0.5) * 2;
      const ny = (y - 0.5) * 2;
      // outside inner ellipse
      if (nx * nx + ny * ny < 0.55 * 0.55) continue;
      dots.push({
        x, y,
        vx: (Math.random() - 0.5) * 0.004,
        vy: (Math.random() - 0.5) * 0.004,
        size: 0.6 + Math.random() * 1.4,
        pulse: 2 + Math.random() * 4,
        phase: Math.random() * Math.PI * 2,
      });
    }
    dotsRef.current = dots;

    let prev = performance.now();
    const loop = (now: number) => {
      const dt = Math.min(0.06, (now - prev) / 1000);
      prev = now;

      const cs = getComputedStyle(canvas);
      const accent = cs.getPropertyValue("--jv-cyan").trim() || "#4361ee";
      // Desaturate + dim — mix accent with a neutral grey and drop alpha.
      const [ar, ag, ab] = hexToRgb(accent);
      const gr = 140, gg = 150, gb = 170;
      const mix = 0.55; // 0 = grey, 1 = accent
      const rr = Math.round(ar * mix + gr * (1 - mix));
      const gG = Math.round(ag * mix + gg * (1 - mix));
      const bb = Math.round(ab * mix + gb * (1 - mix));

      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";

      for (const d of dotsRef.current) {
        d.x += d.vx * dt;
        d.y += d.vy * dt;
        // wrap softly
        if (d.x < -0.02) d.x = 1.02;
        if (d.x > 1.02) d.x = -0.02;
        if (d.y < -0.02) d.y = 1.02;
        if (d.y > 1.02) d.y = -0.02;

        d.phase += dt / d.pulse;
        const pulse = 0.5 + 0.5 * Math.sin(d.phase * Math.PI * 2);
        // final alpha stays in the 8–20% target range
        const alpha = 0.08 + pulse * 0.10;

        const px = d.x * W;
        const py = d.y * H;
        const rad = d.size;

        // soft glow
        const grad = ctx.createRadialGradient(px, py, 0, px, py, rad * 4);
        grad.addColorStop(0, `rgba(${rr},${gG},${bb},${alpha})`);
        grad.addColorStop(1, `rgba(${rr},${gG},${bb},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(px, py, rad * 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(${rr},${gG},${bb},${Math.min(0.22, alpha + 0.05)})`;
        ctx.beginPath();
        ctx.arc(px, py, rad, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [count]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 h-full w-full"
      style={{ zIndex: 1 }}
      aria-hidden
    />
  );
}
