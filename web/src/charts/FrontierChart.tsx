"use client";

/**
 * Yield against the worst single night (share of the vault lost in one closed period), for every
 * static weekday/weekend blend (a line of dots), the two pure tiers, the no-hindsight fixed map,
 * the dynamic strategy and option B. The dashed line is the 0.10% worst-night cap. Data:
 * /v1/report-card `decision` (artifacts/backtest/option_a.json and option_b.json).
 */
import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";

import type { DecisionUniverse, FrontierPoint } from "@/lib/api";
import { formatPct } from "@/lib/time";

import { useInView } from "./useInView";
import { useWidth } from "./useWidth";

type Labelled = FrontierPoint & { label: string; color: string; big?: boolean };

export function FrontierChart({
  u,
  cap,
  height = 320,
}: {
  u: DecisionUniverse;
  cap: number;
  height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [seen, shown] = useInView<SVGSVGElement>();
  const m = { top: 16, right: 24, bottom: 44, left: 56 };
  const w = Math.max(260, width) - m.left - m.right;
  const h = height - m.top - m.bottom;
  const blends = [...u.blends].sort((a, b) => a.w - b.w);
  const named: Labelled[] = [
    { ...blends[0], label: "Always weekend", color: "var(--c-text)" },
    { ...blends[blends.length - 1], label: "Always weekday", color: "var(--c-text)" },
    { ...u.fixed_map, label: "Fixed map", color: "var(--c-text)" },
    { ...u.dynamic, label: "Dynamic", color: "var(--c-safe)" },
    { ...u.b, label: "Afterhours (B)", color: "var(--c-brass)", big: true },
  ];
  const all = [...blends, ...named];
  const x = scaleLinear({
    domain: [0, Math.max(cap, ...all.map((p) => p.worst)) * 1.12],
    range: [0, w],
  });
  const ys = all.map((p) => p.yield);
  const y = scaleLinear({
    domain: [Math.min(...ys) * 0.97, Math.max(...ys) * 1.01],
    range: [h, 0],
  });
  const pct2 = (v: { valueOf(): number }) => `${(Number(v) * 100).toFixed(2)}%`;
  const narrow = width < 560;
  return (
    <div ref={ref}>
      <svg
        ref={seen}
        className={shown ? "frontier shown" : "frontier"}
        width={w + m.left + m.right}
        height={height}
        role="img"
        aria-label={named
          .map(
            (p) =>
              `${p.label}: yield ${formatPct(p.yield, 2)}, worst night ${formatPct(p.worst, 3)} of the vault`,
          )
          .join("; ")}
      >
        <Group left={m.left} top={m.top}>
          <line
            x1={x(cap)}
            x2={x(cap)}
            y1={0}
            y2={h}
            stroke="var(--c-risk)"
            strokeWidth={1.25}
            strokeDasharray="4 4"
          />
          <text x={x(cap) + 6} y={h - 8} fontSize={12} fill="var(--c-text)">
            {formatPct(cap, 2)} cap
          </text>
          <LinePath
            data={blends}
            x={(p) => x(p.worst)}
            y={(p) => y(p.yield)}
            stroke="var(--c-rule)"
            strokeWidth={2}
            className="draw-line"
            pathLength={1}
          />
          {blends.map((p, i) => (
            <circle
              key={p.w}
              cx={x(p.worst)}
              cy={y(p.yield)}
              r={3}
              fill="var(--c-rule)"
              className="pop"
              style={{ transitionDelay: `${200 + i * 40}ms` }}
            />
          ))}
          {named.map((p, i) => (
            <g key={p.label} className="pop" style={{ transitionDelay: `${1000 + i * 180}ms` }}>
              {p.big && <circle cx={x(p.worst)} cy={y(p.yield)} r={7} className="pulse-ring" />}
              {/* On narrow screens only B is labelled on the chart; the list below names all. */}
              <circle
                cx={x(p.worst)}
                cy={y(p.yield)}
                r={p.big ? 7 : 5}
                fill={p.color}
                stroke="var(--c-bg)"
                strokeWidth={1.25}
              />
              <text
                display={narrow && !p.big ? "none" : undefined}
                x={x(p.worst) + (p.big ? 10 : 8)}
                y={y(p.yield) + 4}
                fontSize={12}
                fontWeight={p.big ? 700 : 500}
                fill="var(--c-text)"
              >
                {p.label}
              </text>
            </g>
          ))}
          <AxisBottom
            top={h}
            scale={x}
            numTicks={5}
            tickFormat={pct2}
            stroke="var(--c-rule)"
            tickStroke="var(--c-rule)"
            tickLabelProps={{ fill: "var(--c-text)", fontSize: 12, textAnchor: "middle" }}
            label="Worst single night (share of the vault)"
            labelProps={{ fill: "var(--c-text)", fontSize: 12, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={y}
            numTicks={5}
            tickFormat={pct2}
            stroke="var(--c-rule)"
            tickStroke="var(--c-rule)"
            tickLabelProps={{
              fill: "var(--c-text)",
              fontSize: 12,
              textAnchor: "end",
              dx: -4,
              dy: 3,
            }}
          />
        </Group>
      </svg>
      {narrow && (
        <ul className="mt-2 flex flex-col gap-1 text-[14px]">
          {named.map((p) => (
            <li key={p.label}>
              <span
                aria-hidden="true"
                className="mr-2 inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: p.color }}
              />
              {p.label}: {formatPct(p.yield, 2)} yield, worst night {formatPct(p.worst, 3)}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[14px]">
        Grey line: static blends from 0% to 100% weekday in 5% steps. Up is more yield; left is a
        smaller worst night. Historical stock prices, simulated vault.
      </p>
    </div>
  );
}
