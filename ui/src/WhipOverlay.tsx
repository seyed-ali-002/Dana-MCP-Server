import { useEffect, useRef } from "react";

const WHIP_CDN = "https://raw.githubusercontent.com/GitFrog1111/OpenWhip/main";
const WHIP_SOUNDS = ["A.mp3", "B.mp3", "C.mp3", "D.mp3", "E.mp3"] as const;

const P = {
  segments: 28,
  segmentLength: 22,
  taper: 0.55,
  gravity: 1.15,
  damping: 0.96,
  constraintIters: 16,
  crackSpeed: 320,
  crackCooldownMs: 200,
  firstCrackGraceMs: 280,
  lineWidthHandle: 5.2,
  lineWidthTip: 1.4,
  outlineWidth: 1.6,
  arcWidth: 240,
  arcHeight: 170,
};

type Pt = { x: number; y: number; px: number; py: number };

function playOpenWhipCrack() {
  const name = WHIP_SOUNDS[Math.floor(Math.random() * WHIP_SOUNDS.length)];
  const remote = `${WHIP_CDN}/sounds/${name}`;
  const local = `/whip/sounds/${name}`;
  const tryPlay = (src: string, onFail?: () => void) => {
    const a = new Audio(src);
    a.volume = 0.95;
    a.play().catch(() => onFail?.());
  };
  tryPlay(local, () => tryPlay(remote));
}

function spawnWhip(mx: number, my: number): Pt[] {
  const pts: Pt[] = [];
  for (let i = 0; i < P.segments; i++) {
    const t = i / (P.segments - 1);
    const x = mx + t * P.arcWidth;
    const y = my - Math.sin(t * Math.PI * 0.75) * P.arcHeight;
    pts.push({ x, y, px: x, py: y });
  }
  return pts;
}

function segLen(i: number) {
  const t = i / (P.segments - 1);
  return P.segmentLength * (1 - t * (1 - P.taper));
}

type Props = {
  armed: boolean;
  onCrack?: () => void;
};

export default function WhipOverlay({ armed, onCrack }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const whipRef = useRef<Pt[] | null>(null);
  const mouseRef = useRef({ x: 0, y: 0, px: 0, py: 0 });
  const lastCrackRef = useRef(0);
  const spawnAtRef = useRef(0);
  const onCrackRef = useRef(onCrack);
  onCrackRef.current = onCrack;

  useEffect(() => {
    const root = document.documentElement;
    if (armed) {
      root.classList.add("whip-cursor-active");
      const mx = mouseRef.current.x || window.innerWidth * 0.55;
      const my = mouseRef.current.y || window.innerHeight * 0.45;
      whipRef.current = spawnWhip(mx, my);
      spawnAtRef.current = Date.now();
    } else {
      root.classList.remove("whip-cursor-active");
      whipRef.current = null;
    }
    return () => root.classList.remove("whip-cursor-active");
  }, [armed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const onMove = (e: PointerEvent) => {
      mouseRef.current.px = mouseRef.current.x;
      mouseRef.current.py = mouseRef.current.y;
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;
    };
    window.addEventListener("pointermove", onMove);

    const step = () => {
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      const whip = whipRef.current;
      if (!whip || !armed) {
        raf = requestAnimationFrame(step);
        return;
      }

      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;
      for (let i = 0; i < whip.length; i++) {
        const p = whip[i];
        if (i === 0) {
          p.px = p.x;
          p.py = p.y;
          p.x = mx;
          p.y = my;
          continue;
        }
        const vx = (p.x - p.px) * P.damping;
        const vy = (p.y - p.py) * P.damping + P.gravity;
        p.px = p.x;
        p.py = p.y;
        p.x += vx;
        p.y += vy;
      }
      for (let iter = 0; iter < P.constraintIters; iter++) {
        for (let i = 0; i < whip.length - 1; i++) {
          const a = whip[i];
          const b = whip[i + 1];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.hypot(dx, dy) || 0.0001;
          const target = segLen(i);
          const diff = (dist - target) / dist;
          const ox = dx * 0.5 * diff;
          const oy = dy * 0.5 * diff;
          if (i === 0) {
            b.x -= ox * 2;
            b.y -= oy * 2;
          } else {
            a.x += ox;
            a.y += oy;
            b.x -= ox;
            b.y -= oy;
          }
        }
      }

      const tip = whip[whip.length - 1];
      const tipSpeed = Math.hypot(tip.x - tip.px, tip.y - tip.py) * 60;
      const now = Date.now();
      if (
        tipSpeed > P.crackSpeed &&
        now - lastCrackRef.current > P.crackCooldownMs &&
        now - spawnAtRef.current > P.firstCrackGraceMs
      ) {
        lastCrackRef.current = now;
        playOpenWhipCrack();
        onCrackRef.current?.();
      }

      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#fff";
      ctx.beginPath();
      ctx.moveTo(whip[0].x, whip[0].y);
      for (let i = 1; i < whip.length; i++) ctx.lineTo(whip[i].x, whip[i].y);
      ctx.lineWidth = P.lineWidthTip + P.outlineWidth * 2;
      ctx.stroke();
      for (let i = 0; i < whip.length - 1; i++) {
        const t = i / Math.max(1, whip.length - 2);
        ctx.strokeStyle = "#111";
        ctx.lineWidth = P.lineWidthHandle * (1 - t) + P.lineWidthTip * t;
        ctx.beginPath();
        ctx.moveTo(whip[i].x, whip[i].y);
        ctx.lineTo(whip[i + 1].x, whip[i + 1].y);
        ctx.stroke();
      }

      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
    };
  }, [armed]);

  return (
    <canvas
      ref={canvasRef}
      className={"whip-canvas" + (armed ? " active" : "")}
      aria-hidden={!armed}
    />
  );
}
