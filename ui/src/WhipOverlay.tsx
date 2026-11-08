import { useEffect, useRef } from "react";
import { playOpenWhipCrack } from "./whipAssets";

const P = {
  // Rope structure (exact OpenWhip overlay.html settings)
  segments: 28,
  segmentLength: 25,
  taper: 0.6,

  // Physics
  gravity: 1.2,
  dropGravity: 0.95,
  damping: 0.96,
  constraintIters: 20,
  maxStretchRatio: 1.2,

  // Dynamic handle aim (target angle + restoring spring)
  baseTargetAngle: -1.12,
  handleAimByMouseX: 0.4,
  handleAimByMouseY: 0.2,
  handleAimClamp: 2.0,
  handleSpring: 0.7,
  handleAngularDamping: 0.078,
  basePoseSegments: 2,
  basePoseStiffStart: 0.9,
  basePoseStiffEnd: 0.8,

  // Elastic bend limits by chain position (handle stiff, tip floppy)
  handleMaxBendDeg: 16,
  tipMaxBendDeg: 130,
  bendRigidityStart: 0.8,
  bendRigidityEnd: 0.12,

  // Screen-edge slap
  wallBounce: 0.42,
  wallFriction: 0.86,

  // Crack detection
  crackSpeed: 340,
  crackCooldownMs: 200,
  firstCrackGraceMs: 350,

  // Visuals
  lineWidthHandle: 7,
  lineWidthTip: 5,
  outlineWidth: 3,
  handleExtraWidth: 5,
  handleThickSegments: 2,

  // Initial arc shape
  arcWidth: 260,
  arcHeight: 185,
};

type Pt = { x: number; y: number; px: number; py: number };

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const wrapPi = (a: number) => {
  let r = a;
  while (r > Math.PI) r -= Math.PI * 2;
  while (r < -Math.PI) r += Math.PI * 2;
  return r;
};

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

function catmullPoint(pts: Pt[], i: number): { x: number; y: number } {
  const n = pts.length;
  if (n === 0) return { x: 0, y: 0 };
  if (i < 0) {
    if (n >= 2) {
      return { x: 2 * pts[0].x - pts[1].x, y: 2 * pts[0].y - pts[1].y };
    }
    return { x: pts[0].x, y: pts[0].y };
  }
  if (i >= n) {
    if (n >= 2) {
      const a = pts[n - 2];
      const b = pts[n - 1];
      return { x: 2 * b.x - a.x, y: 2 * b.y - a.y };
    }
    return { x: pts[n - 1].x, y: pts[n - 1].y };
  }
  return pts[i];
}

function whipSegmentBezier(pts: Pt[], i: number) {
  const p0 = catmullPoint(pts, i - 1);
  const p1 = pts[i];
  const p2 = pts[i + 1];
  const p3 = catmullPoint(pts, i + 2);
  return {
    cp1x: p1.x + (p2.x - p0.x) / 6,
    cp1y: p1.y + (p2.y - p0.y) / 6,
    cp2x: p2.x - (p3.x - p1.x) / 6,
    cp2y: p2.y - (p3.y - p1.y) / 6,
    x2: p2.x,
    y2: p2.y,
  };
}

type Props = {
  armed: boolean;
  onCrack?: () => void;
};

export default function WhipOverlay({ armed, onCrack }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const whipRef = useRef<Pt[] | null>(null);
  const droppingRef = useRef(false);
  const mouseRef = useRef({ x: 0, y: 0, px: 0, py: 0 });
  const handleAngleRef = useRef(P.baseTargetAngle);
  const handleAngVelRef = useRef(0);
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
      mouseRef.current.px = mx;
      mouseRef.current.py = my;
      whipRef.current = spawnWhip(mx, my);
      droppingRef.current = false;
      handleAngleRef.current = P.baseTargetAngle;
      handleAngVelRef.current = 0;
      lastCrackRef.current = 0;
      spawnAtRef.current = Date.now();
    } else {
      root.classList.remove("whip-cursor-active");
      if (whipRef.current) {
        droppingRef.current = true;
      }
    }
    return () => {
      root.classList.remove("whip-cursor-active");
    };
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
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const applyBasePose = (whip: Pt[]) => {
      if (droppingRef.current) return;
      const dx = Math.cos(handleAngleRef.current);
      const dy = Math.sin(handleAngleRef.current);
      const guided = Math.min(P.basePoseSegments, whip.length - 1);
      for (let i = 1; i <= guided; i++) {
        const t = (i - 1) / Math.max(guided - 1, 1);
        const stiff = lerp(P.basePoseStiffStart, P.basePoseStiffEnd, t);
        const prev = whip[i - 1];
        const p = whip[i];
        const targetLen = segLen(i - 1);
        const tx = prev.x + dx * targetLen;
        const ty = prev.y + dy * targetLen;
        p.x = lerp(p.x, tx, stiff);
        p.y = lerp(p.y, ty, stiff);
      }
    };

    const applyBendLimits = (whip: Pt[]) => {
      if (whip.length < 3) return;
      for (let i = 1; i < whip.length - 1; i++) {
        const a = whip[i - 1];
        const b = whip[i];
        const c = whip[i + 1];
        const v1x = a.x - b.x;
        const v1y = a.y - b.y;
        const v2x = c.x - b.x;
        const v2y = c.y - b.y;
        const l1 = Math.hypot(v1x, v1y) || 0.0001;
        const l2 = Math.hypot(v2x, v2y) || 0.0001;
        const n1x = v1x / l1;
        const n1y = v1y / l1;
        const n2x = v2x / l2;
        const n2y = v2y / l2;
        const dot = clamp(n1x * n2x + n1y * n2y, -1, 1);
        const angle = Math.acos(dot);
        const t = i / (whip.length - 2);
        const maxBend = (lerp(P.handleMaxBendDeg, P.tipMaxBendDeg, t) * Math.PI) / 180;
        const bend = Math.PI - angle;
        if (bend <= maxBend) continue;
        const cross = n1x * n2y - n1y * n2x;
        const sign = cross >= 0 ? 1 : -1;
        const targetAngle = Math.PI - maxBend;
        const targetA = Math.atan2(n1y, n1x) + sign * targetAngle;
        const tx = b.x + Math.cos(targetA) * l2;
        const ty = b.y + Math.sin(targetA) * l2;
        const rigidity = lerp(P.bendRigidityStart, P.bendRigidityEnd, t);
        c.x = lerp(c.x, tx, rigidity);
        c.y = lerp(c.y, ty, rigidity);
      }
    };

    const capSegmentStretch = (whip: Pt[]) => {
      if (whip.length < 2) return;
      for (let i = 0; i < whip.length - 1; i++) {
        const a = whip[i];
        const b = whip[i + 1];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.0001;
        const maxLen = segLen(i) * P.maxStretchRatio;
        if (dist <= maxLen) continue;
        const k = maxLen / dist;
        b.x = a.x + dx * k;
        b.y = a.y + dy * k;
      }
    };

    const applyWallCollisions = (whip: Pt[], W: number, H: number) => {
      if (droppingRef.current) return;
      for (let i = 1; i < whip.length; i++) {
        const p = whip[i];
        let vx = p.x - p.px;
        let vy = p.y - p.py;
        let hit = false;
        if (p.x < 0) {
          p.x = 0;
          if (vx < 0) vx = -vx * P.wallBounce;
          vy *= P.wallFriction;
          hit = true;
        } else if (p.x > W) {
          p.x = W;
          if (vx > 0) vx = -vx * P.wallBounce;
          vy *= P.wallFriction;
          hit = true;
        }
        if (p.y < 0) {
          p.y = 0;
          if (vy < 0) vy = -vy * P.wallBounce;
          vx *= P.wallFriction;
          hit = true;
        } else if (p.y > H) {
          p.y = H;
          if (vy > 0) vy = -vy * P.wallBounce;
          vx *= P.wallFriction;
          hit = true;
        }
        if (hit) {
          p.px = p.x - vx;
          p.py = p.y - vy;
        }
      }
    };

    const step = () => {
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      const whip = whipRef.current;
      if (!whip) {
        raf = requestAnimationFrame(step);
        return;
      }

      const dropping = droppingRef.current;
      const g = dropping ? P.dropGravity : P.gravity;
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      if (!dropping) {
        const mvx = mx - mouseRef.current.px;
        const mvy = my - mouseRef.current.py;
        const delta = clamp(
          mvx * P.handleAimByMouseX + mvy * P.handleAimByMouseY,
          -P.handleAimClamp,
          P.handleAimClamp
        );
        const target = P.baseTargetAngle + delta;
        const err = wrapPi(target - handleAngleRef.current);
        handleAngVelRef.current += err * P.handleSpring;
        handleAngVelRef.current *= P.handleAngularDamping;
        handleAngleRef.current = wrapPi(handleAngleRef.current + handleAngVelRef.current);
      }

      const startIdx = dropping ? 0 : 1;
      for (let i = startIdx; i < whip.length; i++) {
        const p = whip[i];
        const vx = (p.x - p.px) * P.damping;
        const vy = (p.y - p.py) * P.damping;
        p.px = p.x;
        p.py = p.y;
        p.x += vx;
        p.y += vy + g;
      }

      if (!dropping) {
        whip[0].x = mx;
        whip[0].y = my;
        whip[0].px = mx;
        whip[0].py = my;
      }

      capSegmentStretch(whip);
      applyWallCollisions(whip, W, H);
      applyBasePose(whip);

      for (let iter = 0; iter < P.constraintIters; iter++) {
        for (let i = 0; i < whip.length - 1; i++) {
          const a = whip[i];
          const b = whip[i + 1];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 0.0001;
          const target = segLen(i);
          const diff = ((dist - target) / dist) * 0.5;
          const ox = dx * diff;
          const oy = dy * diff;
          if (i === 0 && !dropping) {
            b.x -= ox * 2;
            b.y -= oy * 2;
          } else {
            a.x += ox;
            a.y += oy;
            b.x -= ox;
            b.y -= oy;
          }
        }
        applyBendLimits(whip);
        if (!dropping) applyBasePose(whip);
        capSegmentStretch(whip);
        applyWallCollisions(whip, W, H);
      }

      const tip = whip[whip.length - 1];
      const tipVel = Math.hypot(tip.x - tip.px, tip.y - tip.py) * 8.5;
      const now = Date.now();
      if (
        !dropping &&
        tipVel > P.crackSpeed &&
        now - spawnAtRef.current >= P.firstCrackGraceMs &&
        now - lastCrackRef.current > P.crackCooldownMs
      ) {
        lastCrackRef.current = now;
        playOpenWhipCrack();
        onCrackRef.current?.();
      }

      if (dropping && whip.every((p) => p.y > H + 60)) {
        whipRef.current = null;
        droppingRef.current = false;
        raf = requestAnimationFrame(step);
        return;
      }

      mouseRef.current.px = mx;
      mouseRef.current.py = my;

      // Render OpenWhip Catmull-Rom cubic Bezier rope with white halo & black core
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#fff";
      if (whip.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(whip[0].x, whip[0].y);
        for (let i = 0; i < whip.length - 1; i++) {
          const { cp1x, cp1y, cp2x, cp2y, x2, y2 } = whipSegmentBezier(whip, i);
          ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
        }
        ctx.lineWidth = P.lineWidthTip + P.outlineWidth * 2;
        ctx.stroke();

        const thickLinks = Math.min(P.handleThickSegments, whip.length - 1);
        if (thickLinks > 0 && P.handleExtraWidth > 0) {
          ctx.beginPath();
          ctx.moveTo(whip[0].x, whip[0].y);
          for (let i = 0; i < thickLinks; i++) {
            const { cp1x, cp1y, cp2x, cp2y, x2, y2 } = whipSegmentBezier(whip, i);
            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
          }
          ctx.lineWidth = P.lineWidthHandle + P.handleExtraWidth + P.outlineWidth * 2;
          ctx.stroke();
        }
      }

      ctx.strokeStyle = "#111";
      for (let i = 0; i < whip.length - 1; i++) {
        const t = i / Math.max(1, whip.length - 2);
        const extra = i < P.handleThickSegments ? P.handleExtraWidth : 0;
        ctx.lineWidth = lerp(P.lineWidthHandle, P.lineWidthTip, t) + extra;
        const { cp1x, cp1y, cp2x, cp2y, x2, y2 } = whipSegmentBezier(whip, i);
        ctx.beginPath();
        ctx.moveTo(whip[i].x, whip[i].y);
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
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
