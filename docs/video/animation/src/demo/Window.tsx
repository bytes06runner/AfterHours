/** A recorded shot inside a browser window: toolbar with the real URL and an honest label, auto zoom. */
import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

import { C, FONT } from "../theme";
import { camera, urlAt, VIEW } from "./camera";
import { clipTime, ENV, outFrame, pieces, REC, Shot, XFADE } from "./edit";

export const WIN = { x: 160, y: 72, w: 1600, bar: 52 };
const CONTENT_H = (WIN.w * VIEW.h) / VIEW.w; // 900
const K = WIN.w / VIEW.w; // CSS pixels to screen pixels
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Lights: React.FC = () => (
  <div style={{ display: "flex", gap: 9 }}>
    {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
      <div key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c, opacity: 0.9 }} />
    ))}
  </div>
);

const Lock: React.FC = () => (
  <svg width="13" height="15" viewBox="0 0 13 15" style={{ marginRight: 9, flex: "none" }}>
    <rect x="1" y="6.5" width="11" height="8" rx="2" fill={C.text} opacity="0.55" />
    <path d="M3.5 6.5V4.5a3 3 0 0 1 6 0v2" stroke={C.text} strokeOpacity="0.55" strokeWidth="1.6" fill="none" />
  </svg>
);

const Url: React.FC<{ url: string }> = ({ url }) => {
  let host = url;
  let rest = "";
  try {
    const u = new URL(url);
    host = u.host;
    rest = u.pathname === "/" ? "" : u.pathname;
  } catch {
    // not a URL; show it as is
  }
  const secure = url.startsWith("https://");
  return (
    <div style={{ display: "flex", alignItems: "center", height: 34, padding: "0 18px", borderRadius: 17, background: "#0a0f26", border: `1px solid ${C.rule}`, width: 720, fontFamily: FONT.sans, fontSize: 17, whiteSpace: "nowrap", overflow: "hidden" }}>
      {secure && <Lock />}
      <span style={{ color: C.text, fontWeight: 600 }}>{host}</span>
      <span style={{ color: C.text, opacity: 0.5, overflow: "hidden", textOverflow: "ellipsis" }}>{rest}</span>
    </div>
  );
};

export const EnvChip: React.FC<{ env: keyof typeof ENV; size?: number }> = ({ env, size = 16 }) => {
  const e = ENV[env];
  const color = C[e.tone];
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: size * 0.55, padding: `${size * 0.4}px ${size * 0.9}px`, borderRadius: 999, background: `${color}1f`, border: `1px solid ${color}88`, color: C.text, fontFamily: FONT.sans, fontWeight: 600, fontSize: size, whiteSpace: "nowrap" }}>
      <div style={{ width: size * 0.55, height: size * 0.55, borderRadius: size, background: color, boxShadow: `0 0 ${size * 0.6}px ${color}` }} />
      {e.label}
    </div>
  );
};

export const Window: React.FC<{ shot: Shot; frames: number; enter: "rise" | "fade"; clicks: boolean }> = ({ shot, frames, enter, clicks }) => {
  const f = useCurrentFrame();
  const { t, piece } = clipTime(shot, f);
  const cam = camera(shot.rec, t);
  const inP = interpolate(f, [0, enter === "rise" ? XFADE + 8 : XFADE], [0, 1], clamp);
  const ease = 1 - Math.pow(1 - inP, 3);
  const rise = enter === "rise" ? (1 - ease) * 40 : 0;
  const grow = enter === "rise" ? 0.965 + 0.035 * ease : 1;
  // The window leans in a touch while the camera is zoomed, for depth.
  const lean = 1 + (cam.s - 1) * 0.012;
  const fastO = piece.speed > 1 ? interpolate(f, [piece.start, piece.start + 8, piece.start + piece.frames - 8, piece.start + piece.frames], [0, 1, 1, 0], clamp) : 0;
  const clickFrames = REC[shot.rec].events
    .filter((e) => e.type === "click")
    .map((e) => outFrame(shot, e.t))
    .filter((x): x is number => x !== null && x < frames);
  return (
    <AbsoluteFill style={{ opacity: ease }}>
      <div
        style={{
          position: "absolute",
          left: WIN.x,
          top: WIN.y,
          width: WIN.w,
          height: WIN.bar + CONTENT_H,
          borderRadius: 18,
          overflow: "hidden",
          background: "#0a0f26",
          border: `1px solid ${C.rule}`,
          boxShadow: "0 40px 120px rgba(0,0,0,0.6), 0 12px 30px rgba(0,0,0,0.4)",
          transform: `translateY(${rise}px) scale(${grow * lean})`,
          transformOrigin: "50% 50%",
        }}
      >
        <div style={{ height: WIN.bar, display: "flex", alignItems: "center", padding: "0 20px", gap: 22, background: "#141a3c", borderBottom: `1px solid ${C.rule}` }}>
          <Lights />
          <div style={{ display: "flex", gap: 14, color: C.text, opacity: 0.4, fontFamily: FONT.sans, fontSize: 20 }}>
            <span>‹</span>
            <span>›</span>
          </div>
          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <Url url={urlAt(shot.rec, t)} />
          </div>
          <EnvChip env={shot.env} />
        </div>
        <div style={{ position: "relative", width: WIN.w, height: CONTENT_H, overflow: "hidden" }}>
          <div style={{ width: VIEW.w, height: VIEW.h, transform: `scale(${K})`, transformOrigin: "0 0" }}>
            <div
              style={{
                width: VIEW.w,
                height: VIEW.h,
                transformOrigin: "0 0",
                transform: `translate(${VIEW.w / 2 - cam.x * cam.s}px, ${VIEW.h / 2 - cam.y * cam.s}px) scale(${cam.s})`,
              }}
            >
              {pieces(shot).map((p) => (
                <Sequence key={p.start} from={p.start} durationInFrames={p.frames} layout="none">
                  <OffthreadVideo src={staticFile(REC[shot.rec].clip)} trimBefore={Math.round(p.from * 30)} playbackRate={p.speed} muted style={{ width: VIEW.w, height: VIEW.h, display: "block" }} />
                </Sequence>
              ))}
            </div>
          </div>
          {piece.speed > 1 && (
            <div style={{ position: "absolute", left: 0, right: 0, bottom: 34, display: "flex", justifyContent: "center", opacity: fastO }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 22px", borderRadius: 999, background: "rgba(7,10,28,0.88)", border: `1px solid ${C.rule}`, color: C.text, fontFamily: FONT.sans, fontSize: 21, fontWeight: 600, boxShadow: "0 10px 30px rgba(0,0,0,0.4)" }}>
                <span style={{ color: C.brass, fontWeight: 800 }}>{piece.speed}× speed</span>
                <span style={{ opacity: 0.8 }}>{piece.note}</span>
              </div>
            </div>
          )}
        </div>
      </div>
      {clicks &&
        clickFrames.map((cf) => (
          <Sequence key={cf} from={Math.max(0, cf - 1)} durationInFrames={10} layout="none">
            <Audio src={staticFile("click.wav")} volume={0.55} />
          </Sequence>
        ))}
    </AbsoluteFill>
  );
};
