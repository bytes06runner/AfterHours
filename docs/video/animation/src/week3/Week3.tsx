/**
 * Week 3 update for Colosseum: a silent cut under 60 seconds of real recordings of the live site,
 * with zooms on the important detail, short crossfades and one caption per shot. No audio track;
 * the voiceover script is docs/video/week3-voiceover.md.
 */
import React from "react";
import { AbsoluteFill, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

import { Sky, Stars, Vignette } from "../components/Atmosphere";
import { Shot, XFADE, shotFrames } from "../demo/edit";
import { Window } from "../demo/Window";
import { C, FONT } from "../theme";

type Cut = { shot: Shot; caption: string };

export const CUTS: Cut[] = [
  { caption: "Afterhours, week 3", shot: { rec: "w3-01-landing", env: "site", from: 8.0, to: 15.2 } },
  { caption: "Frozen today, thin tomorrow", shot: { rec: "10-regimes", env: "live", from: 39.0, to: 49.0 } },
  {
    caption: "Is your loan safe tonight?",
    shot: {
      rec: "w3-03-checker",
      env: "live",
      from: 0.4,
      to: 18.3,
      fast: [{ from: 3.7, to: 11.9, speed: 20, note: "", quiet: true }],
    },
  },
  { caption: "Weekend risk for AI agents", shot: { rec: "11-agents", env: "agents", from: 9.0, to: 19.5 } },
  { caption: "Every move, verified onchain", shot: { rec: "w3-07-testnet", env: "testnet", from: 0.0, to: 7.5 } },
  {
    caption: "We publish what failed",
    shot: {
      rec: "09-report",
      env: "history",
      from: 1.6,
      to: 8.4,
      // Slower while the rule written before running and the recorded result are on screen.
      fast: [{ from: 2.8, to: 6.8, speed: 0.6, note: "", quiet: true }],
    },
  },
];

export const CLOSE = 150; // the closing frame, frames

export function week3Timeline() {
  let at = 0;
  const cuts = CUTS.map((c, i) => {
    const start = i === 0 ? 0 : at - XFADE;
    const frames = shotFrames(c.shot);
    at = start + frames;
    return { ...c, start, frames };
  });
  return { cuts, close: at - XFADE, total: at - XFADE + CLOSE };
}

const Caption: React.FC<{ text: string; frames: number }> = ({ text, frames }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - 8, fps, config: { damping: 200 }, durationInFrames: 18 });
  const out = interpolate(f, [frames - XFADE, frames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 26, display: "flex", justifyContent: "center", opacity: p * out }}>
      <div
        style={{
          transform: `translateY(${(1 - p) * 16}px)`,
          padding: "10px 36px 14px",
          borderRadius: 999,
          background: "rgba(7,10,28,0.9)",
          border: `1.5px solid ${C.brass}`,
          color: C.text,
          fontFamily: FONT.display,
          fontSize: 50,
          lineHeight: 1.1,
        }}
      >
        {text}
      </div>
    </div>
  );
};

const Close: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - XFADE, fps, config: { damping: 200 }, durationInFrames: 24 });
  const line = spring({ frame: f - XFADE - 18, fps, config: { damping: 200 }, durationInFrames: 24 });
  const o = interpolate(f, [0, XFADE], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <Sky />
      <Stars count={120} seed="close" />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
        <Img src={staticFile("demo/mark.svg")} style={{ width: 170, height: 170, opacity: p, transform: `scale(${0.85 + 0.15 * p})` }} />
        <div style={{ fontFamily: FONT.display, fontSize: 150, color: C.text, opacity: p, marginTop: -4 }}>Afterhours</div>
        <div style={{ width: 460 * line, height: 2, background: C.brass, margin: "16px 0 28px" }} />
        <div style={{ fontFamily: FONT.sans, fontWeight: 600, fontSize: 40, color: C.brass, opacity: line, transform: `translateY(${(1 - line) * 14}px)` }}>
          Next: real lenders, final submission
        </div>
      </AbsoluteFill>
      <Vignette />
    </AbsoluteFill>
  );
};

export const Week3: React.FC = () => {
  const { cuts, close, total } = week3Timeline();
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <Sky />
      <Stars count={90} seed="w3" />
      {cuts.map((c, i) => (
        <Sequence key={c.shot.rec} from={c.start} durationInFrames={c.frames}>
          <AbsoluteFill style={{ transform: "translateY(-34px) scale(0.89)", transformOrigin: "50% 0%" }}>
            <Window shot={c.shot} frames={c.frames} enter={i === 0 ? "rise" : "fade"} clicks={false} />
          </AbsoluteFill>
          <Caption text={c.caption} frames={c.frames} />
        </Sequence>
      ))}
      <Sequence from={close} durationInFrames={total - close}>
        <Close />
      </Sequence>
      <Vignette />
    </AbsoluteFill>
  );
};
