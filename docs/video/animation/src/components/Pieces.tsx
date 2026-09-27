/** Shared animated pieces: the exchange, the bell, kinetic words, counters, labels, rays. */
import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** The bell; `ringAt` is the frame it is struck (it swings and settles). */
export const Bell: React.FC<{ size?: number; ringAt?: number; glow?: number }> = ({
  size = 120,
  ringAt = -999,
  glow = 1,
}) => {
  const f = useCurrentFrame();
  const t = f - ringAt;
  const swing = t >= 0 ? Math.sin(t / 3.2) * 24 * Math.exp(-t / 28) : 0;
  const halo = t >= 0 ? interpolate(t, [0, 6, 50], [0, 1, 0], clamp) : 0;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <div
        style={{
          position: "absolute",
          inset: -size * 0.6,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${C.brass}${Math.round(90 * halo * glow)
            .toString(16)
            .padStart(2, "0")} 0%, transparent 65%)`,
        }}
      />
      <svg
        viewBox="0 0 64 64"
        width={size}
        height={size}
        style={{ transform: `rotate(${swing}deg)`, transformOrigin: "50% 10%" }}
      >
        <rect x="30.5" y="3" width="3" height="9" fill={C.brass} />
        <path d="M32 11c-9 0-10.5 9-10.5 18.5L17 41h30l-4.5-11.5C42.5 20 41 11 32 11z" fill={C.brass} />
        <path d="M14 41h36v4H14z" fill={C.brassDeep} />
        <circle cx={32 + swing * 0.15} cy="49" r="4" fill={C.brass} />
      </svg>
    </div>
  );
};

/** An art deco exchange front with a bell tower, a clock and lit windows. */
export const Exchange: React.FC<{
  scale?: number;
  ringAt?: number;
  lights?: number;
  clockHour?: number;
}> = ({ scale = 1, ringAt, lights = 1, clockHour = 16 }) => {
  const f = useCurrentFrame();
  const W = 760;
  const angle = (clockHour % 12) * 30;
  return (
    <div style={{ width: W, height: 620, position: "relative", transform: `scale(${scale})` }}>
      {/* tower */}
      <div style={{ position: "absolute", left: W / 2 - 90, top: 0, width: 180, height: 170, background: "#1e2858", borderTop: `3px solid ${C.brass}` }}>
        <div style={{ position: "absolute", left: 30, top: 10 }}>
          <Bell size={120} ringAt={ringAt} />
        </div>
      </div>
      <div style={{ position: "absolute", left: W / 2 - 150, top: 170, width: 300, height: 90, background: "#212c60" }}>
        <div
          style={{
            position: "absolute",
            left: 115,
            top: 10,
            width: 70,
            height: 70,
            borderRadius: 70,
            border: `3px solid ${C.text}`,
            background: C.bg,
          }}
        >
          <div style={{ position: "absolute", left: 33, top: 12, width: 3, height: 24, background: C.text, transformOrigin: "50% 100%", transform: `rotate(${angle}deg)` }} />
          <div style={{ position: "absolute", left: 33, top: 6, width: 2, height: 30, background: C.brass, transformOrigin: "50% 100%", transform: `rotate(${(f * 6) % 360}deg)` }} />
        </div>
      </div>
      {/* body */}
      <div style={{ position: "absolute", left: 40, top: 260, width: W - 80, height: 360, background: "#1b2452", borderTop: `4px solid ${C.rule}` }}>
        {Array.from({ length: 2 }, (_, r) =>
          Array.from({ length: 10 }, (_, c) => (
            <div
              key={`${r}-${c}`}
              style={{
                position: "absolute",
                left: 40 + c * 62,
                top: 24 + r * 58,
                width: 34,
                height: 38,
                background: C.brass,
                opacity: ((r * 10 + c) % 7 === 3 ? 0.15 : 0.9) * lights,
              }}
            />
          )),
        )}
        {/* columns */}
        {[0, 1, 2, 5, 6, 7].map((c) => (
          <div key={c} style={{ position: "absolute", left: 60 + c * 80, top: 150, width: 26, height: 190, background: "#2a3670", borderLeft: `2px solid ${C.rule}` }} />
        ))}
        {/* door and fan */}
        <div style={{ position: "absolute", left: W / 2 - 40 - 80, top: 160, width: 160, height: 80, borderRadius: "160px 160px 0 0", background: `repeating-conic-gradient(from -90deg at 50% 100%, ${C.brass} 0deg 7deg, ${C.brassDeep} 7deg 12deg)`, opacity: lights }} />
        <div style={{ position: "absolute", left: W / 2 - 40 - 60, top: 240, width: 120, height: 120, background: C.brass, opacity: 0.9 * lights }} />
      </div>
    </div>
  );
};

/** Words that spring up one after another. */
export const Kinetic: React.FC<{
  text: string;
  at?: number;
  size?: number;
  color?: string;
  display?: boolean;
  stagger?: number;
  weight?: number;
  highlight?: string[];
}> = ({ text, at = 0, size = 96, color = C.text, display = true, stagger = 3, weight, highlight = [] }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div
      style={{
        fontFamily: display ? FONT.display : FONT.sans,
        fontSize: size,
        lineHeight: 1.05,
        color,
        fontWeight: weight ?? (display ? 400 : 800),
        display: "flex",
        flexWrap: "wrap",
        gap: `0 ${size * 0.26}px`,
      }}
    >
      {text.split(" ").map((w, i) => {
        const s = spring({ frame: f - at - i * stagger, fps, config: { damping: 14, mass: 0.6 } });
        const hot = highlight.includes(w.replace(/[.,:;]/g, ""));
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              transform: `translateY(${(1 - s) * size * 0.6}px) rotate(${(1 - s) * 6}deg)`,
              opacity: s,
              color: hot ? C.brass : undefined,
              textShadow: hot ? `0 0 ${size * 0.3}px ${C.brass}66` : undefined,
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};

/** Counts up to a generated number and shows it exactly as numbers.json writes it. */
export const Counter: React.FC<{
  text: string;
  at?: number;
  frames?: number;
  size?: number;
  color?: string;
  prefix?: string;
  suffix?: string;
}> = ({ text, at = 0, frames = 40, size = 140, color = C.brass, prefix = "", suffix = "" }) => {
  const f = useCurrentFrame();
  const target = parseFloat(text.replace(/,/g, "").replace("%", ""));
  const decimals = (text.split(".")[1] ?? "").replace("%", "").length;
  const p = interpolate(f, [at, at + frames], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const shown =
    p >= 1
      ? text
      : (target * p).toLocaleString("en-US", {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }) + (text.endsWith("%") ? "%" : "");
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: size,
        color,
        fontVariantNumeric: "tabular-nums",
        opacity: interpolate(f, [at - 5, at], [0, 1], clamp),
        textShadow: `0 0 ${size * 0.25}px ${color}55`,
      }}
    >
      {prefix}
      {shown}
      {suffix}
    </span>
  );
};

/** A small caps label, e.g. "Simulation" or "Historical stock prices, simulated vault". */
export const Chip: React.FC<{ children: React.ReactNode; color?: string; at?: number }> = ({
  children,
  color = C.brass,
  at = 0,
}) => {
  const f = useCurrentFrame();
  return (
    <span
      style={{
        fontFamily: FONT.sans,
        fontWeight: 600,
        fontSize: 26,
        letterSpacing: 2,
        textTransform: "uppercase",
        color,
        border: `2px solid ${color}`,
        borderRadius: 999,
        padding: "8px 22px",
        opacity: interpolate(f, [at, at + 10], [0, 1], clamp),
      }}
    >
      {children}
    </span>
  );
};

/** Rotating art deco rays behind a title. */
export const Sunburst: React.FC<{ opacity?: number; size?: number }> = ({ opacity = 0.35, size = 1800 }) => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        width: size,
        height: size,
        marginLeft: -size / 2,
        marginTop: -size / 2,
        borderRadius: "50%",
        background: `repeating-conic-gradient(from ${f * 0.15}deg, ${C.brass}33 0deg 4deg, transparent 4deg 12deg)`,
        maskImage: "radial-gradient(circle, black 10%, transparent 65%)",
        WebkitMaskImage: "radial-gradient(circle, black 10%, transparent 65%)",
        opacity,
      }}
    />
  );
};
