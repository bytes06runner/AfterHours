/** 1:20 to 1:40. One night: META's October 2022 earnings gap, replayed. */
import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, random, staticFile, useCurrentFrame } from "remotion";

import { Grain, Moon, Sky, Stars, Vignette } from "../components/Atmosphere";
import { Bell, Chip, Counter, Kinetic } from "../components/Pieces";
import { n } from "../data";
import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Calendar: React.FC = () => {
  const f = useCurrentFrame();
  const date = new Date(`${n("replay.date")}T00:00:00Z`);
  const month = date.toLocaleString("en-US", { month: "short", timeZone: "UTC" }).toUpperCase();
  const flip = interpolate(f, [0, 20], [90, 0], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Sky />
      <Stars />
      <Moon x={70} y={10} />
      <div style={{ display: "flex", alignItems: "center", gap: 80 }}>
        <div style={{ width: 360, borderRadius: 30, overflow: "hidden", background: C.text, transform: `perspective(800px) rotateX(${flip}deg)`, boxShadow: `0 30px 80px #000a` }}>
          <div style={{ background: C.risk, color: C.text, fontFamily: FONT.sans, fontWeight: 800, fontSize: 56, textAlign: "center", padding: 16 }}>{month}</div>
          <div style={{ color: C.bg, fontFamily: FONT.display, fontSize: 210, textAlign: "center", lineHeight: 1.1 }}>{date.getUTCDate()}</div>
          <div style={{ color: C.bg, fontFamily: FONT.sans, fontWeight: 800, fontSize: 44, textAlign: "center", paddingBottom: 20 }}>{date.getUTCFullYear()}</div>
        </div>
        <div>
          <Kinetic text={`${n("replay.ticker")} reports earnings.`} at={18} size={96} highlight={[n("replay.ticker")]} />
          <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 30 }}>
            <Bell size={90} ringAt={50} />
            <Kinetic text="The bell rings. Feeds freeze." at={52} size={60} display={false} color={C.frost} />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Drop: React.FC = () => {
  const f = useCurrentFrame();
  const hit = 50;
  const gap = parseFloat(n("replay.gap"));
  const shake = f > hit && f < hit + 20 ? (random(`d${f}`) - 0.5) * 40 * (1 - (f - hit) / 20) : 0;
  const candles = Array.from({ length: 12 }, (_, i) => {
    const mid = 430 + Math.sin(i * 1.3) * 30;
    return { x: 200 + i * 80, open: mid + 20, close: mid - 20 + (i % 3) * 14 };
  });
  const lastClose = candles[candles.length - 1].close;
  const fall = gap * 16;
  return (
    <AbsoluteFill style={{ background: C.bgDeep, transform: `translate(${shake}px, ${shake / 2}px)` }}>
      <AbsoluteFill style={{ background: C.risk, opacity: interpolate(f, [hit, hit + 3, hit + 25], [0, 0.4, 0], clamp) }} />
      <svg width="1920" height="1080" style={{ position: "absolute" }}>
        {candles.map((c, i) => (
          <g key={i} opacity={interpolate(f, [i * 3, i * 3 + 6], [0, 1], clamp)}>
            <line x1={c.x + 20} x2={c.x + 20} y1={Math.min(c.open, c.close) - 26} y2={Math.max(c.open, c.close) + 26} stroke={C.text} strokeWidth="3" />
            <rect x={c.x} y={Math.min(c.open, c.close)} width="40" height={Math.abs(c.open - c.close) + 6} fill={c.close < c.open ? C.safe : C.risk} />
          </g>
        ))}
        <line x1="1180" x2="1320" y1={lastClose} y2={lastClose} stroke={C.frost} strokeWidth="5" strokeDasharray="12 10" opacity={f > 36 ? 1 : 0} />
        {f > hit && (
          <g>
            <rect x="1340" y={lastClose + interpolate(f, [hit, hit + 10], [0, fall], clamp) - 20} width="40" height="60" fill={C.risk} />
            <line x1="1300" x2="1360" y1={lastClose} y2={lastClose + interpolate(f, [hit, hit + 10], [0, fall], clamp)} stroke={C.risk} strokeWidth="6" strokeDasharray="6 6" />
          </g>
        )}
      </svg>
      <div style={{ position: "absolute", left: 1420, top: 520 }}>
        <Counter text={n("replay.gap")} at={hit} frames={14} size={140} color={C.risk} prefix="−" />
        <div style={{ fontFamily: FONT.sans, fontWeight: 800, fontSize: 40, color: C.text, opacity: f > hit + 10 ? 1 : 0 }}>at the next open</div>
      </div>
      <div style={{ position: "absolute", right: 60, top: 50 }}>
        <Chip>Candles illustrative · gap from history</Chip>
      </div>
    </AbsoluteFill>
  );
};

const Losses: React.FC = () => {
  const f = useCurrentFrame();
  const top = parseFloat(n("replay.always_weekday.bad_debt").replace(/,/g, ""));
  const us = parseFloat(n("replay.afterhours.bad_debt").replace(/,/g, ""));
  const rows = [
    { label: `Lending at ${n("tiers.weekday.lltv_short")}`, text: n("replay.always_weekday.bad_debt"), v: top, color: C.risk, at: 10 },
    { label: "Afterhours", text: n("replay.afterhours.bad_debt"), v: us, color: C.brass, at: 30 },
  ];
  return (
    <AbsoluteFill style={{ background: C.bgDeep, padding: "110px 140px" }}>
      <Kinetic text="Afterhours had already pulled the money borrowers weren't using." at={0} size={60} highlight={["already"]} />
      <div style={{ marginTop: 70, display: "flex", flexDirection: "column", gap: 50 }}>
        {rows.map((r) => (
          <div key={r.label}>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: FONT.sans, fontWeight: 800, fontSize: 40, color: C.text }}>
              <span>{r.label}</span>
              <span>
                <Counter text={r.text} at={r.at} frames={45} size={60} color={r.color} /> <span style={{ fontSize: 30 }}>USDG lost</span>
              </span>
            </div>
            <div style={{ height: 40, borderRadius: 20, background: C.surface, marginTop: 14, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${interpolate(f, [r.at, r.at + 45], [0, (r.v / top) * 100], clamp)}%`, background: r.color, borderRadius: 20 }} />
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 60, display: "flex", alignItems: "baseline", gap: 30 }}>
        <Counter text={n("rel.replay.b_less")} at={90} size={180} />
        <span style={{ fontFamily: FONT.display, fontSize: 72, color: C.text, opacity: f > 95 ? 1 : 0 }}>less lost</span>
      </div>
      <div style={{ position: "absolute", right: 60, top: 50 }}>
        <Chip>Replay: historical stock prices, simulated vault</Chip>
      </div>
    </AbsoluteFill>
  );
};

export const Night: React.FC = () => (
  <AbsoluteFill style={{ background: C.bgDeep }}>
    <Sequence durationInFrames={130}>
      <Calendar />
      <Audio src={staticFile("whoosh.wav")} volume={0.5} />
      <Sequence from={50}>
        <Audio src={staticFile("bell.wav")} volume={0.6} />
      </Sequence>
    </Sequence>
    <Sequence from={130} durationInFrames={150}>
      <Drop />
      <Sequence from={50}>
        <Audio src={staticFile("boom.wav")} volume={1} />
      </Sequence>
    </Sequence>
    <Sequence from={280} durationInFrames={320}>
      <Losses />
    </Sequence>
    <Grain />
    <Vignette />
  </AbsoluteFill>
);
