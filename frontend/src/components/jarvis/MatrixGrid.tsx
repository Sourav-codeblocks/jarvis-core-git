import { useEffect, useRef } from "react";

/**
 * Sparse fixed-ish nodes with occasional straight-line "handshake"
 * connections. Color follows theme (uses --jv-cyan-alt2 / --jv-cyan-alt).
 */

function hexToRgb(hex: string): string {
  const h = (hex || "#7fb8d4").replace("#", "").trim();
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full || "7fb8d4", 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

type Node = { x: number; y: number; pulse: number; phase: number };
type Link = {
  a: number;
  b: number;
  start: number; // ms
  duration: number; // ms
};

export function MatrixGrid({ nodeCount = 8 }: { nodeCount?: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const nodesRef = useRef<Node[]>([]);
  const linksRef = useRef<Link[]>([]);
  const rafRef = useRef<number | null>(null);
  const nextLinkAtRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, DPR = 1;

    const layout = () => {
      // Place nodes in outer-mid ring: avoid inner ellipse (r<0.28) and outer (r>0.55)
      const nodes: Node[] = [];
      let safety = 0;
      while (nodes.length < nodeCount && safety < nodeCount * 60) {
        safety++;
        const x = Math.random();
        const y = Math.random();
        const nx = (x - 0.5) * 2;
        const ny = (y - 0.5) * 2;
        const d2 = nx * nx + ny * ny;
        if (d2 < 0.32 * 0.32 || d2 > 0.62 * 0.62) continue;
        // don't crowd
        if (nodes.some((n) => Math.hypot(n.x - x, n.y - y) < 0.14)) continue;
        nodes.push({
          x,
          y,
          pulse: 3 + Math.random() * 5,
          phase: Math.random() * Math.PI * 2,
        });
      }
      nodesRef.current = nodes;
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = rect.width; H = rect.height;
      canvas.width = W * DPR; canvas.height = H * DPR;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    layout();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const scheduleNextLink = (now: number) => {
      // 4–9s pauses between handshakes
      nextLinkAtRef.current = now + 4000 + Math.random() * 5000;
    };
    scheduleNextLink(performance.now());

    const spawnLink = (now: number) => {
      const nodes = nodesRef.current;
      if (nodes.length < 2) return;
      // pick a node, find nearby partner
      const i = Math.floor(Math.random() * nodes.length);
      const candidates: { j: number; d: number }[] = [];
      for (let j = 0; j < nodes.length; j++) {
        if (j === i) continue;
        const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (d < 0.35) candidates.push({ j, d });
      }
      if (!candidates.length) return;
      const pick = candidates[Math.floor(Math.random() * candidates.length)];
      linksRef.current.push({
        a: i,
        b: pick.j,
        start: now,
        duration: 1200 + Math.random() * 900,
      });
    };

    let prev = performance.now();
    const loop = (now: number) => {
      const dt = Math.min(0.06, (now - prev) / 1000);
      prev = now;

      const cs = getComputedStyle(canvas);
      const GREEN = hexToRgb(cs.getPropertyValue("--jv-cyan-alt").trim());

      // maybe spawn a link
      if (now >= nextLinkAtRef.current && linksRef.current.length < 2) {
        spawnLink(now);
        scheduleNextLink(now);
      }

      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";

      // links first (under nodes)
      const stillLinks: Link[] = [];
      for (const l of linksRef.current) {
        const t = (now - l.start) / l.duration;
        if (t >= 1) continue;
        // fade in then out
        const env = t < 0.2 ? t / 0.2 : t > 0.7 ? (1 - t) / 0.3 : 1;
        const alpha = 0.22 * env;
        const na = nodesRef.current[l.a];
        const nb = nodesRef.current[l.b];
        if (!na || !nb) continue;
        const ax = na.x * W, ay = na.y * H;
        const bx = nb.x * W, by = nb.y * H;
        ctx.strokeStyle = `rgba(${GREEN},${alpha})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
        // traveling pulse along the line
        const p = Math.min(1, Math.max(0, (t - 0.15) / 0.6));
        const px = ax + (bx - ax) * p;
        const py = ay + (by - ay) * p;
        const g = ctx.createRadialGradient(px, py, 0, px, py, 6);
        g.addColorStop(0, `rgba(${GREEN},${0.5 * env})`);
        g.addColorStop(1, `rgba(${GREEN},0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fill();
        stillLinks.push(l);
      }
      linksRef.current = stillLinks;

      // nodes
      for (const n of nodesRef.current) {
        n.phase += dt / n.pulse;
        const pulse = 0.5 + 0.5 * Math.sin(n.phase * Math.PI * 2);
        const alpha = 0.15 + pulse * 0.10;
        const px = n.x * W;
        const py = n.y * H;
        const grad = ctx.createRadialGradient(px, py, 0, px, py, 6);
        grad.addColorStop(0, `rgba(${GREEN},${alpha})`);
        grad.addColorStop(1, `rgba(${GREEN},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = `rgba(${GREEN},${Math.min(0.35, alpha + 0.1)})`;
        ctx.beginPath();
        ctx.arc(px, py, 1.4, 0, Math.PI * 2);
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
  }, [nodeCount]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 h-full w-full"
      style={{ zIndex: 2 }}
      aria-hidden
    />
  );
}
