/** Night sky, skyline, grain and vignette: the backdrop every scene sits on. */
import React from "react";
import { AbsoluteFill, interpolate, random, useCurrentFrame } from "remotion";

import { C } from "../theme";

export const Sky: React.FC<{ glow?: string }> = ({ glow = C.surface }) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(ellipse 120% 80% at 50% 110%, ${glow} 0%, ${C.bg} 45%, ${C.bgDeep} 100%)`,
    }}
  />
);

export const Stars: React.FC<{ count?: number; seed?: string }> = ({ count = 140, seed = "s" }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      {Array.from({ length: count }, (_, i) => {
        const x = random(`${seed}x${i}`) * 100;
        const y = random(`${seed}y${i}`) * 62;
        const r = 1 + random(`${seed}r${i}`) * 2.2;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(f / (18 + (i % 23)) + i));
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: r,
              height: r,
              borderRadius: r,
              background: C.text,
              opacity: tw * 0.85,
              boxShadow: r > 2.6 ? `0 0 ${r * 3}px ${C.text}` : undefined,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export const Moon: React.FC<{ x?: number; y?: number; size?: number }> = ({
  x = 78,
  y = 16,
  size = 150,
}) => {
  const f = useCurrentFrame();
  const drift = Math.sin(f / 90) * 6;
  return (
    <div
      style={{
        position: "absolute",
        left: `${x}%`,
        top: `calc(${y}% + ${drift}px)`,
        width: size,
        height: size,
        borderRadius: size,
        boxShadow: `${size * 0.22}px ${-size * 0.08}px 0 0 ${C.text}`,
        filter: `drop-shadow(0 0 40px ${C.text}55)`,
        transform: "rotate(-20deg)",
      }}
    />
  );
};

/** Lit windows flicker slowly; `lights` from 0 to 1 dims the whole city. */
export const Skyline: React.FC<{ lights?: number; seed?: string }> = ({ lights = 1, seed = "k" }) => {
  const f = useCurrentFrame();
  const buildings = Array.from({ length: 26 }, (_, i) => {
    const w = 60 + random(`${seed}w${i}`) * 90;
    const h = 160 + random(`${seed}h${i}`) * 330;
    return { w, h };
  });
  let x = -40;
  return (
    <AbsoluteFill style={{ top: "auto", height: 560 }}>
      {buildings.map((b, i) => {
        const left = x;
        x += b.w + 6;
        const cols = Math.max(2, Math.floor(b.w / 22));
        const rows = Math.floor(b.h / 34);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left,
              bottom: 0,
              width: b.w,
              height: b.h,
              background: i % 3 ? "#1a2350" : "#141c44",
              borderTop: `2px solid ${C.rule}`,
            }}
          >
            {Array.from({ length: rows * cols }, (_, k) => {
              const on = random(`${seed}${i}-${k}`) > 0.45;
              const flick = random(`${seed}${i}-${k}-f`) > 0.93 ? Math.sin(f / 7 + k) > 0 : true;
              return (
                <div
                  key={k}
                  style={{
                    position: "absolute",
                    left: 8 + (k % cols) * ((b.w - 16) / cols),
                    top: 14 + Math.floor(k / cols) * 34,
                    width: 9,
                    height: 13,
                    background: C.brass,
                    opacity: on && flick ? 0.85 * lights : 0.06,
                  }}
                />
              );
            })}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const Grain: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay", opacity: 0.16 }}>
      <svg width="100%" height="100%">
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={f % 12} />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)",
    }}
  />
);

/** Fade a scene in and out at its edges. */
export const SceneFade: React.FC<{ frames: number; children: React.ReactNode; edge?: number }> = ({
  frames,
  children,
  edge = 14,
}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, edge, frames - edge, frames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};
