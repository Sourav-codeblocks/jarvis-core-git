import { useEffect, useRef } from "react";

/**
 * Colorful drifting clouds + streaming connections emitted from the
 * core outward into space. Rendered on a full-viewport canvas, kept
 * subtle so overlaying UI (mic, call, text) stays perfectly legible.
 */
export function CloudTendrils({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const activeRef = useRef(active);
  activeRef.current = active;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    type Puff = {
      x: number; y: number; vx: number; vy: number;
      life: number; max: number; r: number; hue: number;
    };
    type Streamer = {
      x: number; y: number; vx: number; vy: number;
      life: number; max: number; hue: number; trail: { x: number; y: number }[];
    };
    const puffs: Puff[] = [];
    const streams: Streamer[] = [];

    // Cassiopeia-like hues: pink/magenta, teal, violet, warm amber
    const HUES = [325, 300, 265, 190, 175, 30];

    const spawnPuff = () => {
      const cx = w / 2, cy = h / 2;
      const ang = Math.random() * Math.PI * 2;
      const speed = 0.15 + Math.random() * 0.35;
      puffs.push({
        x: cx + Math.cos(ang) * 30,
        y: cy + Math.sin(ang) * 30,
        vx: Math.cos(ang) * speed,
        vy: Math.sin(ang) * speed,
        life: 0,
        max: 260 + Math.random() * 180,
        r: 60 + Math.random() * 120,
        hue: HUES[(Math.random() * HUES.length) | 0],
      });
    };

    const spawnStream = () => {
      const cx = w / 2, cy = h / 2;
      const ang = Math.random() * Math.PI * 2;
      const speed = 1.2 + Math.random() * 1.6;
      streams.push({
        x: cx, y: cy,
        vx: Math.cos(ang) * speed,
        vy: Math.sin(ang) * speed,
        life: 0,
        max: 140 + Math.random() * 80,
        hue: HUES[(Math.random() * HUES.length) | 0],
        trail: [],
      });
    };

    let frame = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      frame++;
      // fade out gracefully when inactive
      const on = activeRef.current;

      // clear (transparent)
      ctx.clearRect(0, 0, w, h);

      // spawn rates
      if (on) {
        if (frame % 3 === 0) spawnPuff();
        if (frame % 4 === 0) spawnStream();
      }

      const cx = w / 2, cy = h / 2;
      const maxDist = Math.hypot(w, h) / 2;

      // Draw puffs (soft colorful clouds) — additive, low alpha
      ctx.globalCompositeOperation = "lighter";
      for (let i = puffs.length - 1; i >= 0; i--) {
        const p = puffs[i];
        p.life++;
        p.x += p.vx;
        p.y += p.vy;
        // gentle drift/curl
        p.vx += (Math.random() - 0.5) * 0.02;
        p.vy += (Math.random() - 0.5) * 0.02;
        const t = p.life / p.max;
        if (t >= 1) { puffs.splice(i, 1); continue; }

        // radial visibility: hide near center (so core is clean) and near edges
        const d = Math.hypot(p.x - cx, p.y - cy);
        const near = Math.min(1, d / 180);       // fade in past core
        const far = 1 - Math.min(1, d / maxDist); // fade out toward edges
        const life = Math.sin(Math.PI * t);       // 0->1->0
        const alpha = 0.12 * life * near * far;
        if (alpha <= 0.002) continue;

        const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
        grd.addColorStop(0, `hsla(${p.hue},85%,62%,${alpha})`);
        grd.addColorStop(0.6, `hsla(${p.hue},85%,55%,${alpha * 0.35})`);
        grd.addColorStop(1, `hsla(${p.hue},85%,45%,0)`);
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw streamers (connections leaving the core)
      ctx.lineCap = "round";
      for (let i = streams.length - 1; i >= 0; i--) {
        const s = streams[i];
        s.life++;
        s.x += s.vx;
        s.y += s.vy;
        // slight curl
        const perp = 0.03;
        const nx = -s.vy, ny = s.vx;
        s.vx += nx * perp * (Math.random() - 0.5);
        s.vy += ny * perp * (Math.random() - 0.5);
        s.trail.push({ x: s.x, y: s.y });
        if (s.trail.length > 22) s.trail.shift();

        const t = s.life / s.max;
        if (t >= 1) { streams.splice(i, 1); continue; }

        const d = Math.hypot(s.x - cx, s.y - cy);
        const near = Math.min(1, d / 120);
        const far = 1 - Math.min(1, d / maxDist);
        const life = Math.sin(Math.PI * t);
        const a = 0.55 * life * near * far;
        if (a <= 0.01) continue;

        for (let k = 1; k < s.trail.length; k++) {
          const p0 = s.trail[k - 1], p1 = s.trail[k];
          const kk = k / s.trail.length;
          ctx.strokeStyle = `hsla(${s.hue},90%,70%,${a * kk})`;
          ctx.lineWidth = 1.1 * kk + 0.2;
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.stroke();
        }
        // head
        ctx.fillStyle = `hsla(${s.hue},95%,80%,${a})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, 1.4, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={`pointer-events-none fixed inset-0 z-0 transition-opacity duration-[1200ms] ease-out ${
        active ? "opacity-100" : "opacity-0"
      }`}
      style={{
        // Radial mask: hide near center (protect core) and near edges (protect UI)
        WebkitMaskImage:
          "radial-gradient(ellipse at center, transparent 0%, black 22%, black 55%, transparent 92%)",
        maskImage:
          "radial-gradient(ellipse at center, transparent 0%, black 22%, black 55%, transparent 92%)",
        mixBlendMode: "screen",
      }}
    />
  );
}
