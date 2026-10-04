/**
 * The product walkthrough: real screen recordings of the site (docs/video/screen-demo), framed
 * in a browser window with auto zoom, chapter cards and quiet sound effects. There is no
 * voiceover; it is cut to leave room for one.
 */
import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

import { Sky, Stars, Vignette } from "../components/Atmosphere";
import { C, FONT } from "../theme";
import { CARD, Chapter, INTRO, OUTRO, XFADE, timeline } from "./edit";
import { EnvChip, WIN, Window } from "./Window";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const LIVE_SITE = "after-hours-web-eta.vercel.app";
const REPO = "github.com/bytes06runner/AfterHours";

const Fade: React.FC<{ frames: number; children: React.ReactNode; inFrames?: number; outFrames?: number }> = ({ frames, children, inFrames = XFADE, outFrames = XFADE }) => {
  const f = useCurrentFrame();
  const o = Math.min(interpolate(f, [0, inFrames], [0, 1], clamp), interpolate(f, [frames - outFrames, frames], [1, 0], clamp));
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

const Rise: React.FC<{ at: number; children: React.ReactNode; y?: number }> = ({ at, children, y = 30 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - at, fps, config: { damping: 200 }, durationInFrames: 22 });
  return <div style={{ opacity: p, transform: `translateY(${(1 - p) * y}px)` }}>{children}</div>;
};

const Backdrop: React.FC = () => (
  <AbsoluteFill>
    <Sky />
    <Stars count={90} seed="demo" />
  </AbsoluteFill>
);

const Intro: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const mark = spring({ frame: f - 4, fps, config: { damping: 14, mass: 0.8 } });
  const rule = interpolate(f, [30, 60], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
      <Img src={staticFile("demo/mark.svg")} style={{ width: 200, height: 200, transform: `scale(${0.6 + 0.4 * mark})`, opacity: Math.min(1, mark * 1.4) }} />
      <Rise at={14}>
        <div style={{ fontFamily: FONT.display, fontSize: 150, color: C.text, letterSpacing: 2, marginTop: -6 }}>Afterhours</div>
      </Rise>
      <div style={{ width: 520 * rule, height: 2, background: C.brass, margin: "18px 0 26px" }} />
      <Rise at={36}>
        <div style={{ fontFamily: FONT.sans, fontWeight: 800, fontSize: 30, letterSpacing: 9, color: C.brass, textTransform: "uppercase" }}>Product walkthrough</div>
      </Rise>
      <Rise at={52}>
        <div style={{ fontFamily: FONT.sans, fontSize: 30, color: C.text, opacity: 0.75, marginTop: 26, textAlign: "center", lineHeight: 1.5 }}>
          Recorded on the real site. Every click is a real click.
        </div>
      </Rise>
    </AbsoluteFill>
  );
};

const Card: React.FC<{ ch: Chapter }> = ({ ch }) => {
  const f = useCurrentFrame();
  const rule = interpolate(f, [XFADE, XFADE + 26], [0, 1], clamp);
  const drift = interpolate(f, [0, CARD + 2 * XFADE], [0, -14]);
  return (
    <AbsoluteFill style={{ background: `${C.bgDeep}f2`, justifyContent: "center", paddingLeft: 220 }}>
      <div style={{ transform: `translateX(${drift}px)` }}>
        <Rise at={4}>
          <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
            <Img src={staticFile("demo/mark.svg")} style={{ width: 64, height: 64 }} />
            <div style={{ fontFamily: FONT.sans, fontWeight: 800, fontSize: 30, letterSpacing: 8, color: C.brass }}>CHAPTER {ch.n}</div>
          </div>
        </Rise>
        <Rise at={9}>
          <div style={{ fontFamily: FONT.display, fontSize: 112, color: C.text, marginTop: 22, lineHeight: 1.05 }}>{ch.title}</div>
        </Rise>
        <div style={{ width: 300 * rule, height: 2, background: C.brass, margin: "30px 0" }} />
        <Rise at={16}>
          <div style={{ fontFamily: FONT.sans, fontSize: 36, color: C.text, opacity: 0.78, maxWidth: 1300, lineHeight: 1.4 }}>{ch.line}</div>
        </Rise>
        <Rise at={22}>
          <div style={{ marginTop: 36 }}>
            <EnvChip env={ch.env} size={24} />
          </div>
        </Rise>
      </div>
    </AbsoluteFill>
  );
};

/** The chapter's name above the window while its shots play. */
const Heading: React.FC<{ ch: Chapter }> = ({ ch }) => (
  <div style={{ position: "absolute", left: WIN.x + 4, top: 22, display: "flex", alignItems: "center", gap: 14, fontFamily: FONT.sans, fontSize: 21, color: C.text }}>
    <Img src={staticFile("demo/mark.svg")} style={{ width: 28, height: 28 }} />
    <span style={{ color: C.brass, fontWeight: 800, letterSpacing: 3 }}>{ch.n}</span>
    <span style={{ opacity: 0.8, fontWeight: 600 }}>{ch.title}</span>
  </div>
);

const Outro: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
    <Rise at={6}>
      <Img src={staticFile("demo/mark.svg")} style={{ width: 150, height: 150 }} />
    </Rise>
    <Rise at={12}>
      <div style={{ fontFamily: FONT.display, fontSize: 120, color: C.text }}>Afterhours</div>
    </Rise>
    <Rise at={20}>
      <div style={{ fontFamily: FONT.sans, fontSize: 32, color: C.text, opacity: 0.78, marginTop: 10 }}>A risk-curated lending vault for Robinhood Stock Tokens on Morpho.</div>
    </Rise>
    <Rise at={34}>
      <div style={{ display: "flex", gap: 30, marginTop: 56, fontFamily: FONT.sans, fontSize: 30, fontWeight: 600 }}>
        <div style={{ padding: "14px 28px", borderRadius: 999, background: `${C.brass}22`, border: `1px solid ${C.brass}`, color: C.text }}>{LIVE_SITE}</div>
        <div style={{ padding: "14px 28px", borderRadius: 999, background: `${C.frost}18`, border: `1px solid ${C.frost}99`, color: C.text }}>{REPO}</div>
      </div>
    </Rise>
  </AbsoluteFill>
);

export const Demo: React.FC<{ sfx: boolean }> = ({ sfx }) => {
  const { chapters, outro, total } = timeline();
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <Backdrop />
      <Sequence durationInFrames={INTRO}>
        <Fade frames={INTRO} inFrames={1}>
          <Intro />
        </Fade>
        {sfx && <Audio src={staticFile("bell.wav")} volume={0.35} />}
      </Sequence>
      {chapters.map(({ ch, card, shots }) => {
        const end = shots[shots.length - 1].start + shots[shots.length - 1].frames;
        return (
          <React.Fragment key={ch.n}>
            <Sequence from={shots[0].start} durationInFrames={end - shots[0].start}>
              <Fade frames={end - shots[0].start} inFrames={XFADE} outFrames={1}>
                <Heading ch={ch} />
              </Fade>
            </Sequence>
            {shots.map(({ shot, start, frames }, i) => (
              <Sequence key={shot.rec} from={start} durationInFrames={frames}>
                <Window shot={shot} frames={frames} enter={i === 0 ? "rise" : "fade"} clicks={sfx} />
              </Sequence>
            ))}
            <Sequence from={card - XFADE} durationInFrames={CARD + 2 * XFADE}>
              <Fade frames={CARD + 2 * XFADE}>
                <Card ch={ch} />
              </Fade>
              {sfx && <Audio src={staticFile("whoosh.wav")} volume={0.22} />}
            </Sequence>
          </React.Fragment>
        );
      })}
      <Sequence from={outro - XFADE} durationInFrames={total - outro + XFADE}>
        <Fade frames={total - outro + XFADE} outFrames={20}>
          <Outro />
        </Fade>
        {sfx && <Audio src={staticFile("bell.wav")} volume={0.25} />}
      </Sequence>
      <Vignette />
    </AbsoluteFill>
  );
};
