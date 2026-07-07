import { useEffect, useRef } from "react";

/**
 * Dynamic radiating line system — circuit/PCB-style traces that draw
 * outward from the core center, hold briefly, then retract or fade.
 * Straight segments only, occasional right-angle bends.
 * Uses --jv-cyan / --jv-cyan-alt so themes flow through.
 */
type Phase = "draw" | "hold" | "retract";
type Line = {
  angle: number;
  length: number;      // final radial length (px)
  bendAt: number | null; // 0..1 along the length where a right-angle bend starts
  bendDir: 1 | -1;       // bend clockwise or counter
  bendLen: number;       // length of the bent segment
  branch: boolean;       // if true, briefly branches into two mid-way
  thickness: number;
  tipDot: boolean;
  midDot: boolean;
  drawDur: number;       // seconds
  holdDur: number;
  retractDur: number;
  t: number;             // seconds into current phase
  phase: Phase;
  hueShift: number;      // 0..1 blend accent<->accentAlt
};

const MAX_TOTAL = 22;

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function RadiatingLines({ intensity = 1 }: { intensity?: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const linesRef = useRef<Line[]>([]);
  const rafRef = useRef<number | null>(null);
  const cfgRef = useRef({ intensity });
  cfgRef.current = { intensity };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement!;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, CX = 0, CY = 0, DPR = 1;

    const resize = () => {
      const rect = parent.getBoundingClientRect();
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = rect.width; H = rect.height;
      CX = W / 2; CY = H / 2;
      canvas.width = W * DPR; canvas.height = H * DPR;
      canvas.style.width = W + "px"; canvas.style.height = H + "px";
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(parent);

    const spawn = () => {
      const I = cfgRef.current.intensity;
      const maxReach = Math.min(W, H) * 0.48;
      const minReach = Math.min(W, H) * 0.18;
      const length = minReach + Math.random() * (maxReach - minReach);
      const withBend = Math.random() < 0.45;
      const withBranch = !withBend && Math.random() < 0.18;
      // horizontal-only: left or right ± small natural variance
      const side = Math.random() < 0.5 ? 0 : Math.PI;
      const jitter = (Math.random() - 0.5) * 0.28; // ~±8°
      linesRef.current.push({
        angle: side + jitter,
        length,
        bendAt: withBend ? 0.45 + Math.random() * 0.35 : null,
        bendDir: Math.random() < 0.5 ? 1 : -1,
        bendLen: 20 + Math.random() * 60,
        branch: withBranch,
        thickness: 0.4 + Math.random() * 1.3,
        tipDot: Math.random() < 0.55,
        midDot: Math.random() < 0.25,
        drawDur: (0.4 + Math.random() * 0.4) / Math.max(0.7, I * 0.85),
        holdDur: 1 + Math.random() * 3,
        retractDur: (0.4 + Math.random() * 0.5) / Math.max(0.7, I * 0.85),
        t: 0,
        phase: "draw",
        hueShift: Math.random(),
      });
    };

    let prev = performance.now();
    let spawnCooldown = 0;

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;

      const cs = getComputedStyle(canvas);
      const accent = cs.getPropertyValue("--jv-cyan").trim() || "#4361ee";
      const accentAlt = cs.getPropertyValue("--jv-cyan-alt").trim() || accent;
      const [ar, ag, ab] = hexToRgb(accent);
      const [br, bg, bb] = hexToRgb(accentAlt);

      const I = cfgRef.current.intensity;
      // active target scales with intensity: standby ~4, listening ~9, thinking ~14
      const target = Math.round(3 + I * 4);
      spawnCooldown -= dt;
      const spawnEvery = 0.35 / Math.max(0.6, I);
      while (linesRef.current.length < Math.min(MAX_TOTAL, target) && spawnCooldown <= 0) {
        spawn();
        spawnCooldown += spawnEvery * (0.6 + Math.random() * 0.9);
      }

      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";
      ctx.lineCap = "round";

      const survivors: Line[] = [];
      for (const L of linesRef.current) {
        L.t += dt;
        // phase progression
        if (L.phase === "draw" && L.t >= L.drawDur) { L.phase = "hold"; L.t = 0; }
        else if (L.phase === "hold" && L.t >= L.holdDur) { L.phase = "retract"; L.t = 0; }
        else if (L.phase === "retract" && L.t >= L.retractDur) { continue; }

        // 0..1 head progress along length
        let head = 1, tail = 0;
        if (L.phase === "draw") head = L.t / L.drawDur;
        else if (L.phase === "retract") tail = L.t / L.retractDur;

        // theme blend
        const t = L.hueShift;
        const rr = Math.round(ar * (1 - t) + br * t);
        const gg = Math.round(ag * (1 - t) + bg * t);
        const bbc = Math.round(ab * (1 - t) + bb * t);
        const col = (a: number) => `rgba(${rr},${gg},${bbc},${a})`;

        const cosA = Math.cos(L.angle);
        const sinA = Math.sin(L.angle);
        const startR = 60; // start just outside the pupil area
        const x0 = CX + cosA * startR;
        const y0 = CY + sinA * startR;

        const totalLen = L.length - startR;
        // main segment endpoints in [startR .. length]
        const segStart = startR + tail * totalLen;
        const segEnd = startR + head * totalLen;
        if (segEnd <= segStart) continue;

        // Break main segment at bendAt if applicable
        const bendR = L.bendAt !== null ? startR + L.bendAt * totalLen : null;

        // Draw main straight portion (up to bend or full)
        const drawStraight = (r1: number, r2: number, alphaBoost = 1) => {
          const xa = CX + cosA * r1, ya = CY + sinA * r1;
          const xb = CX + cosA * r2, yb = CY + sinA * r2;
          // gradient: dim near center, bright toward head
          const grad = ctx.createLinearGradient(xa, ya, xb, yb);
          grad.addColorStop(0, col(0.05 * alphaBoost));
          grad.addColorStop(0.6, col(0.35 * alphaBoost));
          grad.addColorStop(1, col(0.75 * alphaBoost));
          ctx.strokeStyle = grad;
          ctx.lineWidth = L.thickness;
          ctx.beginPath();
          ctx.moveTo(xa, ya);
          ctx.lineTo(xb, yb);
          ctx.stroke();
        };

        if (bendR !== null && segEnd > bendR) {
          drawStraight(segStart, Math.min(bendR, segEnd));
          // bent right-angle piece from bend point
          const bx = CX + cosA * bendR;
          const by = CY + sinA * bendR;
          const perpX = -sinA * L.bendDir;
          const perpY = cosA * L.bendDir;
          const bendProgress = Math.max(0, Math.min(1, (segEnd - bendR) / Math.max(1, L.bendLen)));
          const ex = bx + perpX * L.bendLen * bendProgress;
          const ey = by + perpY * L.bendLen * bendProgress;
          const grad = ctx.createLinearGradient(bx, by, ex, ey);
          grad.addColorStop(0, col(0.35));
          grad.addColorStop(1, col(0.75));
          ctx.strokeStyle = grad;
          ctx.lineWidth = L.thickness;
          ctx.beginPath();
          ctx.moveTo(bx, by);
          ctx.lineTo(ex, ey);
          ctx.stroke();
          if (L.tipDot && bendProgress > 0.85) {
            const g2 = ctx.createRadialGradient(ex, ey, 0, ex, ey, 6);
            g2.addColorStop(0, col(1));
            g2.addColorStop(1, col(0));
            ctx.fillStyle = g2;
            ctx.beginPath(); ctx.arc(ex, ey, 6, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = col(1);
            ctx.beginPath(); ctx.arc(ex, ey, 1.4, 0, Math.PI * 2); ctx.fill();
          }
        } else {
          drawStraight(segStart, segEnd);
          // tip dot on the main line's leading end
          if (L.tipDot && L.phase !== "retract" && head > 0.9) {
            const ex = CX + cosA * segEnd;
            const ey = CY + sinA * segEnd;
            const g2 = ctx.createRadialGradient(ex, ey, 0, ex, ey, 7);
            g2.addColorStop(0, col(1));
            g2.addColorStop(1, col(0));
            ctx.fillStyle = g2;
            ctx.beginPath(); ctx.arc(ex, ey, 7, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = col(1);
            ctx.beginPath(); ctx.arc(ex, ey, 1.6, 0, Math.PI * 2); ctx.fill();
          }
        }

        // Optional branch: short perpendicular offshoot near midpoint
        if (L.branch && L.phase !== "retract") {
          const midR = startR + totalLen * 0.55;
          if (segEnd > midR) {
            const mx = CX + cosA * midR;
            const my = CY + sinA * midR;
            const perpX = -sinA;
            const perpY = cosA;
            const bl = 24;
            const ex = mx + perpX * bl;
            const ey = my + perpY * bl;
            ctx.strokeStyle = col(0.45);
            ctx.lineWidth = L.thickness * 0.8;
            ctx.beginPath();
            ctx.moveTo(mx, my);
            ctx.lineTo(ex, ey);
            ctx.stroke();
            ctx.fillStyle = col(0.9);
            ctx.beginPath(); ctx.arc(ex, ey, 1.2, 0, Math.PI * 2); ctx.fill();
          }
        }

        // mid-junction dot
        if (L.midDot) {
          const mr = startR + totalLen * 0.5;
          if (segEnd > mr && segStart < mr) {
            const mx = CX + cosA * mr;
            const my = CY + sinA * mr;
            ctx.fillStyle = col(0.85);
            ctx.beginPath(); ctx.arc(mx, my, 1.4, 0, Math.PI * 2); ctx.fill();
          }
        }

        survivors.push(L);
      }
      linesRef.current = survivors;
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
