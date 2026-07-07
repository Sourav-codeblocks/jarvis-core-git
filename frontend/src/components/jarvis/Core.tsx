import { useEffect, useRef } from "react";

export type CoreMode = "idle" | "listening" | "thinking" | "call" | "dimmed";

/**
 * Nebula/supernova nucleus.
 * - Dense concentrated center (layered radial blobs biased at CX,CY),
 *   colors fading smoothly outward into the void.
 * - Filament wisps radiating from the core.
 * - Slow drifting outer haze blobs.
 * - `bloom` mode: same structure, scaled up to fill the whole surface
 *   (used as a fullscreen background during call/listening).
 */

function hexToRgb(hex: string): [number, number, number] {
  const h = (hex || "#ffffff").replace("#", "").trim();
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full || "ffffff", 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function Core({
  mode,
  bloom = false,
  fill = false,
}: {
  mode: CoreMode;
  bloom?: boolean;
  fill?: boolean;
}) {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const modeRef = useRef<CoreMode>(mode);
  const bloomRef = useRef<boolean>(bloom);
  modeRef.current = mode;
  bloomRef.current = bloom;

  const isDimmed = mode === "dimmed";
  const size = isDimmed ? 130 : 600;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, CX = 0, CY = 0, DPR = 1;

    const resize = () => {
      const rect = wrapper.getBoundingClientRect();
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = rect.width; H = rect.height;
      CX = W / 2; CY = H / 2;
      canvas.width = W * DPR; canvas.height = H * DPR;
      canvas.style.width = W + "px"; canvas.style.height = H + "px";
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrapper);

    const rand = (a: number, b: number) => a + Math.random() * (b - a);

    // Outer drifting haze — larger, slower, biased outward from center
    const hazeBlobs = Array.from({ length: 16 }).map(() => ({
      angle: Math.random() * Math.PI * 2,
      radius: rand(0.15, 0.5),
      size: rand(0.25, 0.55),
      drift: rand(0.04, 0.15),
      phase: Math.random() * Math.PI * 2,
      color: Math.floor(Math.random() * 3),
      alpha: rand(0.2, 0.55),
    }));

    // Filament wisps that radiate outward from a small inner ring
    const filaments = Array.from({ length: 30 }).map(() => ({
      baseAngle: Math.random() * Math.PI * 2,
      innerR: rand(0.015, 0.04),
      outerR: rand(0.09, 0.16),
      wobbleAmp: rand(0.4, 1.4),
      wobbleFreq: rand(0.6, 1.6),
      thickness: rand(0.6, 1.6),
      speed: rand(-0.5, 0.5),
      seed: Math.random() * 10,
      color: Math.floor(Math.random() * 4),
      alpha: rand(0.45, 0.9),
    }));

    // Colored swirling blobs INSIDE the core, orbiting close to center
    const coreBlobs = Array.from({ length: 9 }).map((_, i) => ({
      seed: i,
      speed: rand(0.25, 0.7) * (i % 2 ? -1 : 1),
      orbit: rand(0.05, 0.22),
      size: rand(0.14, 0.28),
      color: i % 4,
      phase: Math.random() * Math.PI * 2,
    }));

    const sparkles = Array.from({ length: 26 }).map(() => ({
      r: rand(0.3, 0.95),
      a: Math.random() * Math.PI * 2,
      speed: rand(-0.4, 0.4),
      size: rand(0.4, 1.2),
      twinkle: rand(1.5, 4),
      phase: Math.random() * Math.PI * 2,
    }));

    let raf = 0;
    let start = performance.now();
    let bloomT = bloomRef.current ? 1 : 0;
    let activeT = 0;
    // Brief rotation "kick" — pulses on activation change, decays in ~1s.
    let kick = 0;
    let prevActive = false;
    let prevBloom = bloomRef.current;

    const loop = (now: number) => {
      const t = (now - start) / 1000;
      const m = modeRef.current;
      const busy = m === "thinking" || m === "listening";
      const call = m === "call";
      const dimmed = m === "dimmed";
      const active = busy || call;

      // Ease bloom and active state. Smooth, cinematic ramp both ways —
      // gentle enough that the transition is unmistakable but never snaps.
      const target = bloomRef.current ? 1 : 0;
      const bloomEase = bloomRef.current ? 0.022 : 0.035;
      bloomT += (target - bloomT) * bloomEase;
      const aTarget = active ? 1 : 0;
      const aEase = active ? 0.022 : 0.032;
      activeT += (aTarget - activeT) * aEase;
      if (Math.abs(activeT - aTarget) < 0.0005) activeT = aTarget;


      // Rotation kick: fires once when active toggles either direction,
      // decays to 0 in ~1s so the nebula settles instead of spinning forever.
      if (active !== prevActive) kick = 1;
      if (bloomRef.current !== prevBloom) kick = Math.max(kick, 1);
      prevActive = active;
      prevBloom = bloomRef.current;
      kick *= 0.94; // ~60fps -> ~1s to fade

      const cs = getComputedStyle(canvas);
      const accent = cs.getPropertyValue("--jv-cyan").trim() || "#d15a8f";
      const accentAlt = cs.getPropertyValue("--jv-cyan-alt").trim() || "#4fb8d4";
      const accentDim = cs.getPropertyValue("--jv-cyan-dim").trim() || "#4a2a6e";
      const accent3 = cs.getPropertyValue("--jv-cyan-alt2").trim() || "#a8c94a";
      const hot = cs.getPropertyValue("--jv-hot").trim() || "#f7d0e0";
      const contrast = cs.getPropertyValue("--jv-green").trim() || "#4aa8ff";

      const palette = [accent, accentAlt, accent3, accentDim];
      const rgb = palette.map(hexToRgb);
      const hotRgb = hexToRgb(hot);
      const contrastRgb = hexToRgb(contrast);
      const dimRgb = hexToRgb(accentDim);

      const minHalf = Math.min(W, H) / 2;
      // Motion is nearly still. Kick adds only a very subtle nudge.
      const idleSpeed = 0.1;
      const kickBoost = 0.35;
      const speedMul = dimmed ? 0.08 : idleSpeed + kick * kickBoost;

      // Standby is small and tight; active expands with clear delta but
      // capped so the glow never bleeds into the surrounding frame.
      const standbyScale = 0.78;
      const peakScale = call ? 1.55 : 1.45;
      const coreScale = dimmed ? 0.55 : standbyScale + (peakScale - standbyScale) * activeT;

      // Active DIMS more so internal filaments are clearly visible
      // (holographic Cassiopeia look, not a soft Siri blob).
      const lit = dimmed ? 0.4 : 0.85 - 0.35 * activeT;

      // Richness ramps in with activeT — internal wisps fade in, not pop in.
      const richness = activeT;


      // Blend palette with contrast (blue) — eased so tint fades in.
      const tintMix = 0.22 * activeT;
      const tint = (c: [number, number, number]): [number, number, number] => [
        Math.round(c[0] * (1 - tintMix) + contrastRgb[0] * tintMix),
        Math.round(c[1] * (1 - tintMix) + contrastRgb[1] * tintMix),
        Math.round(c[2] * (1 - tintMix) + contrastRgb[2] * tintMix),
      ];



      // Bloom scales the whole nebula outward on activation — capped so
      // the glow stays well within the surrounding frame ring.
      const bloomScale = 0.7 + bloomT * 0.85;  // haze radii multiplier
      const bloomAlpha = 0.85 + bloomT * 0.75; // haze alpha multiplier
      const bloomBlob = 0.75 + bloomT * 0.95;  // haze blob size multiplier
      // Standby atmosphere is tight; it grows visibly with activeT.
      const atmoPush = 0.85 + 0.4 * activeT;   // haze radius push
      const standbyAtmoAlpha = 0.3;            // trimmed standby haze

      ctx.clearRect(0, 0, W, H);

      // ----- 1. Deep base wash — colored fog anchored at center, fades to void.
      {
        const baseR = minHalf * (0.38 + bloomT * 0.4);
        const grad = ctx.createRadialGradient(CX, CY, 0, CX, CY, baseR);
        const [r, g, b] = tint(hexToRgb(accent));
        const [r2, g2, b2] = tint(dimRgb);
        const centerA = (dimmed ? 0.04 : 0.05 + bloomT * 0.12) * lit;
        grad.addColorStop(0, `rgba(${r},${g},${b},${centerA})`);
        grad.addColorStop(0.35, `rgba(${r2},${g2},${b2},${centerA * 0.7})`);
        grad.addColorStop(1, `rgba(${r2},${g2},${b2},0)`);
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);
      }

      // ----- 1b. Outer atmosphere ring — tight halo that grows visibly
      // with activeT. Kept well inside the frame ring.
      {
        const coreR = minHalf * (dimmed ? 0.14 : 0.28) * (dimmed ? 0.55 : 0.82 + 0.55 * activeT);
        const atmoInner = coreR * (0.9 + 0.2 * activeT);
        const atmoOuter = coreR * (1.15 + 0.9 * activeT);


        const [ar, ag, ab] = tint(hexToRgb(accentAlt));
        const [br2, bg2, bb2] = tint(hexToRgb(accent));
        const atmoA = (dimmed ? 0.05 : 0.05 + 0.18 * activeT) * lit;
        const grad = ctx.createRadialGradient(CX, CY, atmoInner, CX, CY, atmoOuter);
        grad.addColorStop(0, `rgba(${br2},${bg2},${bb2},${atmoA})`);
        grad.addColorStop(0.55, `rgba(${ar},${ag},${ab},${atmoA * 0.6})`);
        grad.addColorStop(1, `rgba(${ar},${ag},${ab},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(CX, CY, atmoOuter, 0, Math.PI * 2);
        ctx.fill();
      }

      // ----- 2. Outer haze blobs (drift around, tint the nebula) -----
      ctx.globalCompositeOperation = "source-over";
      for (const b of hazeBlobs) {
        const drift = t * b.drift * speedMul * 0.35;
        const wob = Math.sin(t * 0.4 + b.phase) * 0.08;
        const ang = b.angle + drift * 0.25;
        const rr = (b.radius + wob) * minHalf * bloomScale * atmoPush;
        const cx = CX + Math.cos(ang) * rr;
        const cy = CY + Math.sin(ang) * rr;
        const blobR = b.size * minHalf * bloomBlob * (0.9 + Math.sin(t * 0.5 + b.phase) * 0.08) * (0.85 + 0.25 * activeT);
        const [r, g, bl] = tint(rgb[b.color === 3 ? 0 : b.color]);
        const alphaScale = (dimmed ? 0.3 : call ? 0.75 : busy ? 0.8 : standbyAtmoAlpha) * bloomAlpha;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, blobR);
        grad.addColorStop(0, `rgba(${r},${g},${bl},${b.alpha * 0.5 * alphaScale})`);
        grad.addColorStop(0.5, `rgba(${r},${g},${bl},${b.alpha * 0.18 * alphaScale})`);
        grad.addColorStop(1, `rgba(${r},${g},${bl},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, blobR, 0, Math.PI * 2);
        ctx.fill();
      }

      // Shadow pockets — deep violet uneven density
      for (let i = 0; i < 4; i++) {
        const ang = t * 0.08 * speedMul + (i * Math.PI) / 2;
        const rr = minHalf * (0.28 + 0.12 * Math.sin(t * 0.2 + i)) * bloomScale;
        const cx = CX + Math.cos(ang) * rr;
        const cy = CY + Math.sin(ang) * rr;
        const blobR = minHalf * 0.35 * bloomBlob;
        const [r, g, bl] = dimRgb;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, blobR);
        grad.addColorStop(0, `rgba(${r},${g},${bl},${dimmed ? 0.1 : 0.24})`);
        grad.addColorStop(1, `rgba(${r},${g},${bl},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, blobR, 0, Math.PI * 2);
        ctx.fill();
      }

      // ----- 3. THE CORE — dense concentrated nucleus at center -----
      const coreR = minHalf * (dimmed ? 0.14 : 0.34) * coreScale;

      ctx.globalCompositeOperation = "lighter";

      // 3a. Soft outer core aura
      {
        const auraR = coreR * 1.6;
        const grad = ctx.createRadialGradient(CX, CY, 0, CX, CY, auraR);
        const [r, g, b] = tint(hexToRgb(accent));
        grad.addColorStop(0, `rgba(${r},${g},${b},${(dimmed ? 0.2 : 0.4) * lit})`);
        grad.addColorStop(0.45, `rgba(${r},${g},${b},${(dimmed ? 0.08 : 0.18) * lit})`);
        grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(CX, CY, auraR, 0, Math.PI * 2);
        ctx.fill();
      }

      // 3b. Colored blobs orbiting inside the core — the "fire"
      for (const cb of coreBlobs) {
        const ang = t * cb.speed * speedMul + cb.phase;
        const rr = coreR * cb.orbit * (0.7 + 0.3 * Math.sin(t * 0.9 + cb.seed));
        const cx = CX + Math.cos(ang) * rr;
        const cy = CY + Math.sin(ang) * rr;
        const br = coreR * cb.size * (0.85 + 0.2 * Math.sin(t * 1.3 + cb.seed));
        const [r, g, bl] = tint(rgb[cb.color === 3 ? 1 : cb.color]);
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, br);
        grad.addColorStop(0, `rgba(${r},${g},${bl},${(dimmed ? 0.2 : 0.4) * lit})`);
        grad.addColorStop(0.55, `rgba(${r},${g},${bl},${(dimmed ? 0.08 : 0.18) * lit})`);
        grad.addColorStop(1, `rgba(${r},${g},${bl},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, br, 0, Math.PI * 2);
        ctx.fill();
      }

      // 3c. Filament wisps radiating from the nucleus
      for (const f of filaments) {
        const innerR = coreR * (0.35 + f.innerR * 3);
        const outerR = coreR * (1.05 + f.outerR * 4);
        const spin = t * f.speed * speedMul + f.seed;
        const a0 = f.baseAngle + spin;
        const wob = Math.sin(t * f.wobbleFreq * speedMul + f.seed) * f.wobbleAmp * 0.08;
        const a1 = a0 + wob;
        const x1 = CX + Math.cos(a0) * innerR;
        const y1 = CY + Math.sin(a0) * innerR;
        const x2 = CX + Math.cos(a1) * outerR;
        const y2 = CY + Math.sin(a1) * outerR;
        const [r, g, bl] = tint(rgb[f.color === 3 ? 1 : f.color]);
        const grad = ctx.createLinearGradient(x1, y1, x2, y2);
        const aFade = (0.55 + Math.sin(t * 1.2 + f.seed) * 0.45) * f.alpha * (dimmed ? 0.3 : 0.75) * lit;
        grad.addColorStop(0, `rgba(${r},${g},${bl},${aFade * 0.9})`);
        grad.addColorStop(1, `rgba(${r},${g},${bl},0)`);
        ctx.strokeStyle = grad;
        ctx.lineWidth = f.thickness;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        const mx = (x1 + x2) / 2 + Math.cos(a1 + Math.PI / 2) * 6 * Math.sin(t * 2 + f.seed);
        const my = (y1 + y2) / 2 + Math.sin(a1 + Math.PI / 2) * 6 * Math.sin(t * 2 + f.seed);
        ctx.quadraticCurveTo(mx, my, x2, y2);
        ctx.stroke();
      }

      // 3d. Extra holographic wisps — only when active. NO lines, NO dots.
      // Soft curved smears of color drifting inside the expanded core,
      // making the active nebula feel like a stretched, richer version
      // of the standby core (Cassiopeia-style filaments).
      if (richness > 0.01) {
        const wisps = 14;
        for (let i = 0; i < wisps; i++) {
          const a = (i / wisps) * Math.PI * 2 + t * (0.15 + (i % 3) * 0.05) * (i % 2 ? -1 : 1);
          const r0 = coreR * (0.15 + 0.15 * Math.sin(t * 0.7 + i));
          const r1 = coreR * (0.55 + 0.35 * Math.sin(t * 0.4 + i * 1.3));
          const x0 = CX + Math.cos(a) * r0;
          const y0 = CY + Math.sin(a) * r0;
          const x1 = CX + Math.cos(a + 0.9) * r1;
          const y1 = CY + Math.sin(a + 0.9) * r1;
          const midR = (r0 + r1) * 0.6;
          const midA = a + 0.4 + Math.sin(t + i) * 0.3;
          const mx = CX + Math.cos(midA) * midR;
          const my = CY + Math.sin(midA) * midR;
          // Draw a soft radial smear at the midpoint (no hard stroke)
          const blob = coreR * (0.14 + 0.06 * Math.sin(t * 1.1 + i));
          const [r, g, bl] = tint(rgb[i % 3]);
          const alpha = (0.18 + 0.22 * Math.abs(Math.sin(t * 0.9 + i))) * lit * richness;
          const grad = ctx.createRadialGradient(mx, my, 0, mx, my, blob);
          grad.addColorStop(0, `rgba(${r},${g},${bl},${alpha})`);
          grad.addColorStop(1, `rgba(${r},${g},${bl},0)`);
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(mx, my, blob, 0, Math.PI * 2);
          ctx.fill();
          // A second, smaller smear along the curve for streaky feel
          const bx = (x0 + mx) / 2;
          const by = (y0 + my) / 2;
          const blob2 = blob * 0.6;
          const grad2 = ctx.createRadialGradient(bx, by, 0, bx, by, blob2);
          grad2.addColorStop(0, `rgba(${r},${g},${bl},${alpha * 0.7})`);
          grad2.addColorStop(1, `rgba(${r},${g},${bl},0)`);
          ctx.fillStyle = grad2;
          ctx.beginPath();
          ctx.arc(bx, by, blob2, 0, Math.PI * 2);
          ctx.fill();
          // Suppress unused-var warnings for endpoint math (kept for shape math)
          void x1; void y1;
        }
      }


      // 3e. Restrained hot pinpoint at true center — soft in standby.
      {
        const pulse = 0.9 + Math.sin(t * (busy ? 3 : 1.4)) * 0.1;
        const hotR = coreR * 0.28 * pulse;
        const [hr, hg, hb] = active ? tint(hotRgb) : hotRgb;
        const grad = ctx.createRadialGradient(CX, CY, 0, CX, CY, hotR * 2.2);
        grad.addColorStop(0, `rgba(${hr},${hg},${hb},${(dimmed ? 0.12 : 0.22) * lit})`);
        grad.addColorStop(0.5, `rgba(${hr},${hg},${hb},${(dimmed ? 0.04 : 0.08) * lit})`);
        grad.addColorStop(1, `rgba(${hr},${hg},${hb},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(CX, CY, hotR * 2.2, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";

      // ----- 4. Sparkle stars scattered through the haze -----
      for (const s of sparkles) {
        const ang = s.a + t * s.speed * speedMul * 0.3;
        const rr = s.r * minHalf * bloomScale * (0.9 + 0.4 * Math.sin(t * 0.3 + s.phase));
        const x = CX + Math.cos(ang) * rr * (1 + Math.sin(t * 0.5 + s.phase) * 0.15);
        const y = CY + Math.sin(ang) * rr * (1 + Math.cos(t * 0.4 + s.phase) * 0.15);
        const twk = 0.5 + 0.5 * Math.sin(t * s.twinkle + s.phase);
        const [r, g, bl] = hotRgb;
        ctx.fillStyle = `rgba(${r},${g},${bl},${(dimmed ? 0.35 : 0.7) * twk})`;
        ctx.beginPath();
        ctx.arc(x, y, s.size, 0, Math.PI * 2);
        ctx.fill();
      }


      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  if (fill) {
    return (
      <div ref={wrapperRef} className="absolute inset-0 h-full w-full">
        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden />
      </div>
    );
  }

  return (
    <div
      ref={wrapperRef}
      className="relative select-none transition-all duration-500 ease-out"
      style={{ width: size, height: size }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden />
    </div>
  );
}
