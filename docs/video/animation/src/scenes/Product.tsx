/** 0:20 to 0:50. The product: three tiers, a forecast before every close, a pullback, a reason onchain. */
import React from "react";
import { AbsoluteFill, Sequence, interpolate, random, spring, useCurrentFrame, useVideoConfig } from "remotion";

import { Sfx } from "../components/Sfx";
import { Grain, Sky, Stars, Vignette } from "../components/Atmosphere";
import { Bell, Chip, Kinetic } from "../components/Pieces";
import { n, TIERS, VAULT_STOCKS } from "../data";
import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Vault: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Sky glow={C.rule} />
      <Stars count={80} seed="v" />
      {Array.from({ length: 26 }, (_, i) => {
        const start = i * 4;
        const t = interpolate(f, [start, start + 40], [0, 1], clamp);
        const x = 300 + random(`cx${i}`) * 1320;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: interpolate(t, [0, 1], [x, 932]),
              top: interpolate(t, [0, 1], [-80, 690]),
              width: 56,
              height: 56,
              borderRadius: 56,
              background: C.brass,
              border: `4px solid ${C.brassDeep}`,
              opacity: t < 1 ? 1 : 0,
              fontFamily: FONT.sans,
              fontWeight: 800,
              fontSize: 18,
              color: C.bg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            USDG
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: 760,
          top: 600,
          width: 400,
          height: 360,
          borderRadius: 34,
          border: `6px solid ${C.brass}`,
          background: `linear-gradient(160deg, ${C.surface}, ${C.bg})`,
          boxShadow: `0 0 ${70 + Math.sin(f / 6) * 25}px ${C.brass}55`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 18,
        }}
      >
        <div
          style={{
            width: 150,
            height: 150,
            borderRadius: 150,
            border: `10px solid ${C.brass}`,
            background: `repeating-conic-gradient(from ${f * 3}deg, ${C.brass} 0deg 10deg, transparent 10deg 30deg)`,
          }}
        />
        <div style={{ fontFamily: FONT.display, fontSize: 52, color: C.text }}>The vault</div>
      </div>
      <AbsoluteFill style={{ padding: "90px 120px" }}>
        <Kinetic text="Afterhours: a Morpho vault for Stock Tokens." at={6} size={80} highlight={["Afterhours:"]} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Shelves: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: C.bgDeep, padding: "80px 120px" }}>
      <Kinetic text="Each stock lends in the riskiest market its own last year allows." at={0} size={62} highlight={["riskiest", "last", "year"]} />
      <div style={{ display: "flex", gap: 70, marginTop: 80, justifyContent: "center" }}>
        {TIERS.map((t, i) => {
          const s = spring({ frame: f - 20 - i * 10, fps, config: { damping: 12 } });
          const cushion = parseFloat(t.cushion);
          return (
            <div key={t.name} style={{ width: 440, transform: `translateY(${(1 - s) * 200}px)`, opacity: s }}>
              <div style={{ fontFamily: FONT.display, fontSize: 110, color: C.brass, textAlign: "center" }}>{t.lltv}</div>
              <div style={{ fontFamily: FONT.sans, fontWeight: 600, fontSize: 28, color: C.text, textAlign: "center", marginBottom: 20 }}>
                loan-to-value
              </div>
              <div style={{ height: 300, borderRadius: 22, border: `3px solid ${C.rule}`, position: "relative", overflow: "hidden", background: C.surface }}>
                <div
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: `${interpolate(f, [40 + i * 10, 80 + i * 10], [0, cushion * 5], clamp)}%`,
                    background: `linear-gradient(0deg, ${C.safe}, ${C.safe}66)`,
                  }}
                />
                <div style={{ position: "absolute", left: 24, top: 20, fontFamily: FONT.sans, fontWeight: 800, fontSize: 34, color: C.text }}>
                  cushion {t.cushion}
                </div>
              </div>
              <div style={{ fontFamily: FONT.sans, fontSize: 26, color: C.text, opacity: 0.8, textAlign: "center", marginTop: 14 }}>
                {i === 0 ? "earns most, least room" : i === 2 ? "earns least, most room" : "in between"}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Forecast: React.FC = () => {
  const f = useCurrentFrame();
  const limit = parseFloat(n("policy.pull_limit"));
  const lineY = 700 - limit * 22;
  // Illustrative bad cases: calm stocks well under the line; META (earnings night) far over it.
  const cases: Record<string, number> = { NVDA: 5.4, SPY: 2.6, META: 22, SGOV: 0.6, USO: 4.8 };
  const pulled = f > 150;
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <AbsoluteFill style={{ padding: "70px 120px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 30 }}>
          <Bell size={90} ringAt={4} />
          <Kinetic text="Before every close: tonight's bad case." at={0} size={70} highlight={["bad", "case."]} />
        </div>
      </AbsoluteFill>
      <svg width="1920" height="1080" style={{ position: "absolute" }}>
        <line x1="260" x2="1660" y1={lineY} y2={lineY} stroke={C.risk} strokeWidth="4" strokeDasharray="14 10" />
        <text x="1670" y={lineY + 12} fill={C.risk} fontFamily={FONT.sans} fontWeight="800" fontSize="34">{n("policy.pull_limit")}</text>
        <text x="1670" y={lineY + 52} fill={C.text} fontFamily={FONT.sans} fontSize="24">every market's limit</text>
        {VAULT_STOCKS.map((sym, i) => {
          const h = interpolate(f, [20 + i * 8, 90 + i * 8], [0, (cases[sym] ?? 3) * 22], clamp);
          const x = 330 + i * 270;
          const over = (cases[sym] ?? 0) > limit && h > limit * 22;
          return (
            <g key={sym}>
              <rect x={x} y={700 - h} width="150" height={h} rx="12" fill={over ? C.risk : C.brass} opacity={over && pulled ? 0.55 : 1} />
              <text x={x + 75} y="760" textAnchor="middle" fill={C.text} fontFamily={FONT.sans} fontWeight="800" fontSize="40">{sym}</text>
            </g>
          );
        })}
      </svg>
      {pulled &&
        Array.from({ length: 14 }, (_, i) => {
          const t = interpolate(f, [150 + i * 3, 190 + i * 3], [0, 1], clamp);
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: interpolate(t, [0, 1], [870 + (i % 3) * 30, 1560]),
                top: interpolate(t, [0, 0.5, 1], [420 + (i % 4) * 30, 250, 880]),
                width: 36,
                height: 36,
                borderRadius: 36,
                background: C.brass,
                opacity: t > 0 && t < 1 ? 1 : 0,
              }}
            />
          );
        })}
      <div style={{ position: "absolute", left: 1480, top: 840, width: 300, height: 120, borderRadius: 20, border: `3px dashed ${C.safe}`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT.sans, fontWeight: 800, fontSize: 34, color: C.safe, opacity: pulled ? 1 : 0.2 }}>
        idle, safe
      </div>
      <div style={{ position: "absolute", left: 120, bottom: 70 }}>
        <Kinetic text="Too risky for any market? Pull the money borrowers aren't using." at={160} size={52} display={false} weight={800} highlight={["Pull"]} />
      </div>
      <div style={{ position: "absolute", right: 60, top: 50 }}>
        <Chip>Illustration</Chip>
      </div>
    </AbsoluteFill>
  );
};

const Reason: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 13 } });
  const hex = Array.from({ length: 64 }, (_, i) => "0123456789abcdef"[Math.floor(random(`h${i}-${Math.min(f, 70) >> 1}`) * 16)]).join("");
  const stamp = 110;
  const landed = f > stamp;
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <div
        style={{
          position: "absolute",
          left: 160,
          top: 160,
          width: 760,
          padding: 44,
          borderRadius: 28,
          background: C.surface,
          border: `3px solid ${C.rule}`,
          transform: `translateX(${(1 - s) * -400}px) rotate(${(1 - s) * -8}deg)`,
          fontFamily: FONT.sans,
          color: C.text,
        }}
      >
        <div style={{ fontFamily: FONT.display, fontSize: 60 }}>Reason card</div>
        {["The stock's rating", "Tonight's forecast", "The rule that fired"].map((row, i) => (
          <div key={row} style={{ fontSize: 36, marginTop: 22, opacity: interpolate(f, [12 + i * 8, 20 + i * 8], [0, 1], clamp) }}>
            <span style={{ color: C.brass }}>●</span> {row}
          </div>
        ))}
        <div style={{ fontFamily: "monospace", fontSize: 22, marginTop: 36, color: C.brass, wordBreak: "break-all" }}>0x{hex}</div>
      </div>
      {/* the chain */}
      <div style={{ position: "absolute", left: 1040, top: 380, display: "flex", gap: 26, alignItems: "center" }}>
        {Array.from({ length: 5 }, (_, i) => {
          const me = i === 3;
          return (
            <div
              key={i}
              style={{
                width: 130,
                height: 130,
                borderRadius: 20,
                border: `4px solid ${me && landed ? C.brass : C.rule}`,
                background: me && landed ? `${C.brass}33` : C.surface,
                boxShadow: me && landed ? `0 0 60px ${C.brass}` : undefined,
                transform: me && landed ? `scale(${interpolate(f, [stamp, stamp + 8], [1.25, 1], clamp)})` : undefined,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: FONT.sans,
                fontWeight: 800,
                fontSize: 26,
                color: C.text,
              }}
            >
              {me && landed ? "✓ hash" : "block"}
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 160, bottom: 110 }}>
        <Kinetic text="Every move writes its reason onchain." at={stamp + 6} size={84} highlight={["reason", "onchain."]} />
      </div>
    </AbsoluteFill>
  );
};

export const Product: React.FC = () => (
  <AbsoluteFill style={{ background: C.bgDeep }}>
    <Sequence durationInFrames={150}>
      <Vault />
      <Sfx name="whoosh" volume={0.5} />
    </Sequence>
    <Sequence from={150} durationInFrames={270}>
      <Shelves />
      <Sfx name="whoosh" volume={0.4} />
    </Sequence>
    <Sequence from={420} durationInFrames={250}>
      <Forecast />
      <Sfx name="bell" volume={0.45} />
      <Sequence from={150}>
        <Sfx name="whoosh" volume={0.6} />
      </Sequence>
    </Sequence>
    <Sequence from={670} durationInFrames={230}>
      <Reason />
      <Sequence from={110}>
        <Sfx name="stamp" volume={0.9} />
      </Sequence>
    </Sequence>
    <Grain />
    <Vignette />
  </AbsoluteFill>
);
