/** 0:00 to 0:20. The hook: Stock Tokens trade all weekend; their feeds freeze; lenders take the gap. */
import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, random, staticFile, useCurrentFrame } from "remotion";

import { Grain, Moon, Skyline, Sky, Stars, Vignette } from "../components/Atmosphere";
import { Bell, Chip, Counter, Exchange, Kinetic, Sunburst } from "../components/Pieces";
import { n, STOCK_TOKENS, UPDATED_FEEDS } from "../data";
import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const ColdOpen: React.FC = () => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, 62, 75], [0, 1, 1, 0], clamp);
  const s = interpolate(f, [0, 75], [0.92, 1.05]);
  return (
    <AbsoluteFill style={{ background: C.bgDeep, justifyContent: "center", alignItems: "center", opacity: o }}>
      <Sunburst opacity={interpolate(f, [8, 30], [0, 0.5], clamp)} />
      <div style={{ transform: `scale(${s})`, display: "flex", flexDirection: "column", alignItems: "center", gap: 30 }}>
        <Bell size={170} ringAt={8} />
        <div style={{ fontFamily: FONT.display, fontSize: 150, color: C.text, letterSpacing: 4 }}>Afterhours</div>
      </div>
    </AbsoluteFill>
  );
};

const City: React.FC = () => {
  const f = useCurrentFrame();
  const zoom = interpolate(f, [0, 165], [1, 1.12]);
  return (
    <AbsoluteFill>
      <Sky />
      <Stars />
      <Moon x={86} y={30} size={120} />
      <AbsoluteFill style={{ transform: `scale(${zoom})`, transformOrigin: "50% 90%" }}>
        <Skyline />
        <div style={{ position: "absolute", left: 580, bottom: 0 }}>
          <Exchange scale={1} lights={interpolate(f, [60, 100], [1, 0.35], clamp)} />
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ padding: "110px 120px" }}>
        <Kinetic text="Stock Tokens trade all weekend." at={12} size={104} highlight={["weekend"]} />
        <div style={{ height: 24 }} />
        <Kinetic text="Their price feeds don't." at={70} size={104} color={C.frost} highlight={[]} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** The 35 real Stock Token feeds; all but three freeze for the weekend. */
const Feeds: React.FC = () => {
  const f = useCurrentFrame();
  const clockP = interpolate(f, [10, 150], [0, 1], clamp);
  const hours = Math.round(clockP * 48);
  const day = hours < 4 ? "FRI" : hours < 28 ? "SAT" : "SUN";
  const hh = (20 + hours) % 24;
  return (
    <AbsoluteFill style={{ background: C.bgDeep, padding: "80px 110px" }}>
      <Stars count={60} seed="f" />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={{ fontFamily: FONT.display, fontSize: 64, color: C.text }}>Every Stock Token price feed</div>
        <div style={{ fontFamily: FONT.sans, fontWeight: 800, fontSize: 60, color: C.frost, fontVariantNumeric: "tabular-nums" }}>
          {day} {String(hh).padStart(2, "0")}:00 <span style={{ fontSize: 30, fontWeight: 600 }}>New York</span>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 18, marginTop: 44 }}>
        {STOCK_TOKENS.map((sym, i) => {
          const updates = UPDATED_FEEDS.includes(sym);
          const freezeAt = 20 + random(`fz${i}`) * 90;
          const frozen = !updates && f > freezeAt;
          const ping = updates && f > 18 && f < 34;
          return (
            <div
              key={sym}
              style={{
                height: 92,
                borderRadius: 16,
                border: `2px solid ${frozen ? C.frost : updates ? C.brass : C.safe}`,
                background: frozen ? `${C.frost}22` : ping ? `${C.brass}55` : `${C.safe}18`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0 20px",
                fontFamily: FONT.sans,
                fontWeight: 800,
                fontSize: 32,
                color: frozen ? C.frost : C.text,
                transform: frozen ? `scale(${interpolate(f, [freezeAt, freezeAt + 6], [1.08, 1], clamp)})` : undefined,
                boxShadow: ping ? `0 0 30px ${C.brass}` : undefined,
              }}
            >
              {sym}
              <span style={{ fontSize: 26 }}>{frozen ? "❄" : updates ? "•" : "~"}</span>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 110, bottom: 70, display: "flex", alignItems: "baseline", gap: 26 }}>
        <Counter text={n("oracle.feeds_without_update")} at={120} size={150} color={C.frost} />
        <span style={{ fontFamily: FONT.display, fontSize: 64, color: C.text, opacity: interpolate(f, [125, 140], [0, 1], clamp) }}>
          of {n("oracle.feeds")} feeds posted nothing, Friday night to Sunday night, over {n("oracle.weekends")} weekends.
        </span>
      </div>
    </AbsoluteFill>
  );
};

/** A price that flat-lines for the weekend, then gaps down on Monday. */
const Gap: React.FC = () => {
  const f = useCurrentFrame();
  const draw = interpolate(f, [0, 70], [0, 1], clamp);
  const hit = 70;
  const shake = f > hit && f < hit + 18 ? (random(`sh${f}`) - 0.5) * 30 * (1 - (f - hit) / 18) : 0;
  const pts: [number, number][] = [];
  for (let i = 0; i <= 60; i++) {
    const x = 120 + i * 14;
    pts.push([x, 520 + Math.sin(i * 0.7) * 18 + Math.sin(i * 1.9) * 9]);
  }
  const weekday = pts.map(([x, y]) => `${x},${y}`).join(" ");
  const last = pts[pts.length - 1];
  const flatEnd = last[0] + 620;
  return (
    <AbsoluteFill style={{ background: C.bgDeep, transform: `translate(${shake}px, ${shake * 0.6}px)` }}>
      <AbsoluteFill style={{ background: C.risk, opacity: interpolate(f, [hit, hit + 3, hit + 20], [0, 0.35, 0], clamp) }} />
      <svg width="1920" height="1080">
        <defs>
          <clipPath id="draw">
            <rect x="0" y="0" width={120 + draw * 1500} height="1080" />
          </clipPath>
        </defs>
        <g clipPath="url(#draw)">
          <polyline points={weekday} fill="none" stroke={C.safe} strokeWidth="7" />
          <line x1={last[0]} y1={last[1]} x2={flatEnd} y2={last[1]} stroke={C.frost} strokeWidth="7" strokeDasharray="18 14" />
        </g>
        {f > hit && (
          <line
            x1={flatEnd}
            y1={last[1]}
            x2={flatEnd}
            y2={last[1] + interpolate(f, [hit, hit + 8], [0, 300], clamp)}
            stroke={C.risk}
            strokeWidth="9"
          />
        )}
        <text x={last[0] + 60} y={last[1] - 40} fill={C.frost} fontFamily={FONT.sans} fontSize="40" fontWeight="800" opacity={draw > 0.6 ? 1 : 0}>
          WEEKEND: FEED FROZEN
        </text>
        <text x={flatEnd + 30} y={last[1] + 280} fill={C.risk} fontFamily={FONT.sans} fontSize="44" fontWeight="800" opacity={f > hit + 6 ? 1 : 0}>
          MONDAY OPEN
        </text>
      </svg>
      <AbsoluteFill style={{ padding: "90px 120px" }}>
        <Kinetic text="No prices, no liquidations." at={4} size={84} />
        <div style={{ height: 16 }} />
        <Kinetic text="When trading resumes, lenders take the gap." at={hit + 10} size={84} color={C.risk} highlight={["gap."]} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const Hook: React.FC = () => (
  <AbsoluteFill style={{ background: C.bgDeep }}>
    <Sequence durationInFrames={75}>
      <ColdOpen />
      <Audio src={staticFile("bell.wav")} startFrom={0} volume={0.9} />
    </Sequence>
    <Sequence from={75} durationInFrames={165}>
      <City />
    </Sequence>
    <Sequence from={240} durationInFrames={180}>
      <Feeds />
      <Audio src={staticFile("whoosh.wav")} volume={0.5} />
    </Sequence>
    <Sequence from={420} durationInFrames={180}>
      <Gap />
      <Sequence from={70}>
        <Audio src={staticFile("boom.wav")} volume={0.9} />
      </Sequence>
    </Sequence>
    <Grain />
    <Vignette />
    <div style={{ position: "absolute", right: 60, top: 50 }}>
      <Sequence from={240} durationInFrames={180} layout="none">
        <Chip color={C.frost}>Real data: Robinhood Chain mainnet</Chip>
      </Sequence>
    </div>
  </AbsoluteFill>
);
