/** 0:50 to 1:20. The claim: above the line of fixed mixes, tested the honest way. */
import React from "react";
import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

import { Sfx } from "../components/Sfx";
import { Grain, Vignette } from "../components/Atmosphere";
import { Chip, Counter, Kinetic } from "../components/Pieces";
import { FRONTIER, n } from "../data";
import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Chart frame: bad debt (USDG) across, lender yield (%) up. Ranges from the data itself.
const X0 = 260, X1 = 1060, Y0 = 860, Y1 = 300;
const maxDebt = Math.max(...FRONTIER.map((p) => p.badDebt)) * 1.08;
const minY = Math.min(...FRONTIER.map((p) => p.yield)) - 0.4;
const maxY = Math.max(...FRONTIER.map((p) => p.yield)) + 0.3;
/** Where each point's label goes, so the three close together at the top do not collide. */
const LABEL: Record<string, { dx: number; dy: number; anchor: "start" | "middle" | "end" }> = {
  always_weekday: { dx: 20, dy: 8, anchor: "start" },
  blend: { dx: 22, dy: 44, anchor: "start" },
  fixed_map: { dx: 0, dy: -34, anchor: "middle" },
  always_weekend: { dx: 24, dy: 8, anchor: "start" },
};
const px = (d: number) => X0 + (d / maxDebt) * (X1 - X0);
const py = (y: number) => Y0 - ((y - minY) / (maxY - minY)) * (Y0 - Y1);

const Frontier: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lo = FRONTIER.find((p) => p.key === "always_weekend")!;
  const hi = FRONTIER.find((p) => p.key === "always_weekday")!;
  const lineP = interpolate(f, [20, 60], [0, 1], clamp);
  const bAt = 90;
  const bPop = spring({ frame: f - bAt, fps, config: { damping: 9 } });
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <svg width="1920" height="1080" style={{ position: "absolute" }}>
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} stroke={C.rule} strokeWidth="3" />
        <line x1={X0} y1={Y0} x2={X0} y2={Y1 - 30} stroke={C.rule} strokeWidth="3" />
        <text x={X1} y={Y0 + 56} textAnchor="end" fill={C.text} fontFamily={FONT.sans} fontSize="28">bad debt (USDG) →</text>
        <text x={X0 - 20} y={Y1 - 50} fill={C.text} fontFamily={FONT.sans} fontSize="28">lender yield ↑</text>
        <line
          x1={px(lo.badDebt)}
          y1={py(lo.yield)}
          x2={px(lo.badDebt) + (px(hi.badDebt) - px(lo.badDebt)) * lineP}
          y2={py(lo.yield) + (py(hi.yield) - py(lo.yield)) * lineP}
          stroke={C.text}
          strokeWidth="4"
          strokeDasharray="12 10"
          opacity="0.7"
        />
        <text
          x={px(lo.badDebt) + (px(hi.badDebt) - px(lo.badDebt)) * 0.16 + 26}
          y={py(lo.yield) + (py(hi.yield) - py(lo.yield)) * 0.16 + 44}
          fill={C.text}
          fontFamily={FONT.sans}
          fontSize="28"
          opacity={lineP * 0.9}
          transform={`rotate(${(Math.atan2(py(hi.yield) - py(lo.yield), px(hi.badDebt) - px(lo.badDebt)) * 180) / Math.PI} ${px(lo.badDebt) + (px(hi.badDebt) - px(lo.badDebt)) * 0.16 + 26} ${py(lo.yield) + (py(hi.yield) - py(lo.yield)) * 0.16 + 44})`}
        >
          every fixed mix of markets sits on this line
        </text>
        {FRONTIER.filter((p) => p.key !== "b").map((p, i) => {
          const o = interpolate(f, [10 + i * 12, 20 + i * 12], [0, 1], clamp);
          return (
            <g key={p.key} opacity={o}>
              <circle cx={px(p.badDebt)} cy={py(p.yield)} r="13" fill={p.fixedMix ? C.text : C.frost} />
              <text
                x={px(p.badDebt) + (LABEL[p.key]?.dx ?? 22)}
                y={py(p.yield) + (LABEL[p.key]?.dy ?? -18)}
                textAnchor={LABEL[p.key]?.anchor ?? "start"}
                fill={C.text}
                fontFamily={FONT.sans}
                fontSize="24"
              >
                {p.label} · {p.yieldText}
              </text>
            </g>
          );
        })}
        {(() => {
          const b = FRONTIER.find((p) => p.key === "b")!;
          return (
            <g opacity={bPop} transform={`translate(${px(b.badDebt)} ${py(b.yield)}) scale(${bPop})`}>
              <circle r="46" fill={`${C.brass}33`} />
              <circle r="20" fill={C.brass} />
              <text x="-30" y="-44" textAnchor="end" fill={C.brass} fontFamily={FONT.display} fontSize="46">Afterhours · {b.yieldText}</text>
            </g>
          );
        })()}
      </svg>
      <div style={{ position: "absolute", left: 1320, top: 200, display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ fontFamily: FONT.sans, fontWeight: 600, fontSize: 30, color: C.text, opacity: interpolate(f, [120, 130], [0, 1], clamp) }}>
          vs the fixed mix that earns the same
        </div>
        <div><Counter text={n("rel.b_vs_blend.bad_debt_less")} at={130} size={120} /> <span style={{ fontFamily: FONT.sans, fontSize: 34, color: C.text }}>less bad debt</span></div>
        <div><Counter text={n("rel.b_vs_blend.worst_less")} at={150} size={120} /> <span style={{ fontFamily: FONT.sans, fontSize: 34, color: C.text }}>smaller worst night</span></div>
        <div style={{ fontFamily: FONT.sans, fontWeight: 600, fontSize: 30, color: C.text, marginTop: 30, opacity: interpolate(f, [210, 220], [0, 1], clamp) }}>
          vs a plan re-rated once a year
        </div>
        <div><Counter text={n("rel.b_vs_fixed_map.bad_debt_less")} at={220} size={96} color={C.frost} /> <span style={{ fontFamily: FONT.sans, fontSize: 30, color: C.text }}>less bad debt</span></div>
        <div><Counter text={n("rel.b_vs_fixed_map.worst_less")} at={240} size={96} color={C.frost} /> <span style={{ fontFamily: FONT.sans, fontSize: 30, color: C.text }}>smaller worst night</span></div>
      </div>
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <Kinetic text="Same yield. About half the loss." at={96} size={76} highlight={["half"]} />
      </div>
      <div style={{ position: "absolute", left: 120, bottom: 60, display: "flex", gap: 20 }}>
        <Chip at={40}>Historical stock prices, simulated vault</Chip>
        <Chip at={50} color={C.text}>Held out: {n("b5.eval_first").slice(0, 4)} to {n("b5.eval_last").slice(0, 4)}</Chip>
      </div>
    </AbsoluteFill>
  );
};

const TestFirst: React.FC = () => {
  const f = useCurrentFrame();
  const rule = n("verdict.rule");
  const typed = rule.slice(0, Math.floor(interpolate(f, [20, 130], [0, rule.length], clamp)));
  const stampAt = 160;
  return (
    <AbsoluteFill style={{ background: C.bgDeep, padding: "100px 140px" }}>
      <Kinetic text="We wrote the test down before running it." at={0} size={72} />
      <div style={{ marginTop: 50, padding: "40px 50px", borderLeft: `8px solid ${C.brass}`, background: C.surface, borderRadius: 16, fontFamily: FONT.sans, fontSize: 44, color: C.text, lineHeight: 1.35, minHeight: 200 }}>
        “{typed}
        <span style={{ opacity: f % 20 < 10 ? 1 : 0 }}>▍</span>”
      </div>
      <div style={{ marginTop: 60, display: "flex", alignItems: "center", gap: 50 }}>
        <div style={{ fontFamily: FONT.display, fontSize: 64, color: C.text }}>Our first design</div>
        <div
          style={{
            fontFamily: FONT.sans,
            fontWeight: 800,
            fontSize: 72,
            color: C.risk,
            border: `8px solid ${C.risk}`,
            padding: "6px 30px",
            borderRadius: 14,
            transform: `rotate(-8deg) scale(${interpolate(f, [stampAt, stampAt + 6], [2.2, 1], clamp)})`,
            opacity: f >= stampAt ? 1 : 0,
          }}
        >
          DID NOT PASS
        </div>
      </div>
      <div style={{ marginTop: 50 }}>
        <Kinetic text="So the simpler design ships." at={stampAt + 30} size={72} highlight={["simpler"]} />
      </div>
    </AbsoluteFill>
  );
};

const Honest: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.bgDeep, justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <Kinetic text="The backtest uses modelled rates." at={0} size={72} />
      <div style={{ height: 50 }} />
      <div style={{ fontFamily: FONT.sans, fontSize: 40, color: C.text, opacity: interpolate(f, [30, 45], [0, 1], clamp) }}>
        Real Stock Token markets pay lenders
      </div>
      <Counter text={n("market.supply_apy")} at={50} size={170} color={C.frost} />
      <div style={{ fontFamily: FONT.sans, fontSize: 34, color: C.text, opacity: interpolate(f, [70, 85], [0, 0.8], clamp) }}>
        today (Robinhood Chain block {n("market.block")}). The market is early.
      </div>
    </AbsoluteFill>
  );
};

export const Claim: React.FC = () => (
  <AbsoluteFill style={{ background: C.bgDeep }}>
    <Sequence durationInFrames={420}>
      <Frontier />
      <Sfx name="whoosh" volume={0.5} />
      <Sequence from={90}>
        <Sfx name="stamp" volume={0.6} />
      </Sequence>
    </Sequence>
    <Sequence from={420} durationInFrames={300}>
      <TestFirst />
      <Sequence from={160}>
        <Sfx name="stamp" volume={1} />
      </Sequence>
    </Sequence>
    <Sequence from={720} durationInFrames={180}>
      <Honest />
    </Sequence>
    <Grain />
    <Vignette />
  </AbsoluteFill>
);
