/** 1:40 to 2:05. The market today: early, and growing. */
import React from "react";
import { AbsoluteFill, Sequence, interpolate, random, useCurrentFrame } from "remotion";

import { Sfx } from "../components/Sfx";
import { Grain, Skyline, Sky, Stars, Vignette } from "../components/Atmosphere";
import { Chip, Counter, Kinetic } from "../components/Pieces";
import { n, v } from "../data";
import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** One dot per Morpho market that takes a Stock Token as collateral. */
const Markets: React.FC = () => {
  const f = useCurrentFrame();
  const count = v("market.stock_token_markets");
  // Exactly market.markets_with_borrowing dots glow (which ones is decoration).
  const order = Array.from({ length: count }, (_, i) => i).sort((a, b) => random(`o${a}`) - random(`o${b}`));
  const withBorrowing = new Set(order.slice(0, v("market.markets_with_borrowing")));
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <Stars count={50} seed="m" />
      {Array.from({ length: count }, (_, i) => {
        const x = 1400 + Math.cos(i * 2.399) * Math.sqrt(i) * 34;
        const y = 600 + Math.sin(i * 2.399) * Math.sqrt(i) * 34;
        const on = interpolate(f, [10 + i * 0.8, 16 + i * 0.8], [0, 1], clamp);
        const borrowed = withBorrowing.has(i);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: 16,
              height: 16,
              borderRadius: 16,
              background: borrowed ? C.brass : C.safe,
              opacity: on,
              transform: `scale(${on})`,
              boxShadow: borrowed ? `0 0 14px ${C.brass}` : undefined,
            }}
          />
        );
      })}
      <div style={{ position: "absolute", left: 120, top: 120 }}>
        <Kinetic text="The market is early." at={0} size={96} highlight={["early."]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 330, display: "flex", flexDirection: "column", gap: 34 }}>
        <div>
          <Counter text={n("market.stock_token_markets")} at={30} size={130} />
          <div style={{ fontFamily: FONT.sans, fontSize: 34, color: C.text }}>Morpho markets take a Stock Token</div>
        </div>
        <div>
          <Counter text={n("market.usdg_supplied")} at={70} size={110} color={C.safe} />
          <div style={{ fontFamily: FONT.sans, fontSize: 34, color: C.text }}>USDG supplied</div>
        </div>
        <div>
          <Counter text={n("market.usdg_borrowed")} at={110} size={110} color={C.brass} />
          <div style={{ fontFamily: FONT.sans, fontSize: 34, color: C.text }}>USDG borrowed</div>
        </div>
      </div>
      <div style={{ position: "absolute", right: 60, bottom: 50 }}>
        <Chip color={C.text} at={40}>
          Robinhood Chain block {n("market.block")} · {n("market.date")}
        </Chip>
      </div>
    </AbsoluteFill>
  );
};

const Grow: React.FC = () => {
  const f = useCurrentFrame();
  const rise = interpolate(f, [0, 200], [300, 0], clamp);
  return (
    <AbsoluteFill>
      <Sky glow={C.brassDeep} />
      <Stars />
      <AbsoluteFill style={{ transform: `translateY(${rise}px)` }}>
        <Skyline lights={interpolate(f, [0, 200], [0.2, 1], clamp)} seed="g" />
      </AbsoluteFill>
      <AbsoluteFill style={{ padding: "140px 140px", alignItems: "center", textAlign: "center" }}>
        <Kinetic text="We're building the vault lenders can trust with it, as it grows." at={10} size={84} highlight={["trust"]} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const Market: React.FC = () => (
  <AbsoluteFill style={{ background: C.bgDeep }}>
    <Sequence durationInFrames={420}>
      <Markets />
      <Sfx name="whoosh" volume={0.5} />
    </Sequence>
    <Sequence from={420} durationInFrames={330}>
      <Grow />
      <Sfx name="whoosh" volume={0.4} />
    </Sequence>
    <Grain />
    <Vignette />
  </AbsoluteFill>
);
