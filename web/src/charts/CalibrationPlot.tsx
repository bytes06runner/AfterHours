"use client";

/** Nominal vs observed miss rate with the perfect-calibration diagonal (visx, token colours). */
import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";

import { useWidth } from "./useWidth";

export interface CalPoint {
  nominal: number;
  observed: number;
  n: number;
}

export function CalibrationPlot({
  points,
  title,
  max = 260,
}: {
  points: CalPoint[];
  title: string;
  max?: number;
}) {
  const [ref, width] = useWidth<HTMLElement>(max);
  const size = Math.max(160, Math.min(max, width));
  const m = { top: 12, right: 12, bottom: 36, left: 44 };
  const w = size - m.left - m.right;
  const h = size - m.top - m.bottom;
  const top = Math.max(0.06, ...points.map((p) => Math.max(p.nominal, p.observed))) * 1.15;
  const x = scaleLinear({ domain: [0, top], range: [0, w] });
  const y = scaleLinear({ domain: [0, top], range: [h, 0] });
  const pct = (v: { valueOf(): number }) => `${(Number(v) * 100).toFixed(0)}%`;
  return (
    <figure ref={ref}>
      <svg
        width={size}
        height={size}
        role="img"
        aria-label={`${title}: ${points.map((p) => `target ${pct(p.nominal)}, observed ${(p.observed * 100).toFixed(2)}%`).join("; ")}`}
      >
        <Group left={m.left} top={m.top}>
          <line
            x1={x(0)}
            y1={y(0)}
            x2={x(top)}
            y2={y(top)}
            stroke="var(--c-rule)"
            strokeWidth={1.25}
          />
          <LinePath
            data={points}
            x={(p) => x(p.nominal)}
            y={(p) => y(p.observed)}
            stroke="var(--c-safe)"
            strokeWidth={2}
          />
          {points.map((p) => (
            <circle
              key={p.nominal}
              cx={x(p.nominal)}
              cy={y(p.observed)}
              r={4}
              fill="var(--c-safe)"
            />
          ))}
          <AxisBottom
            top={h}
            scale={x}
            numTicks={3}
            tickFormat={pct}
            stroke="var(--c-rule)"
            tickStroke="var(--c-rule)"
            tickLabelProps={{ fill: "var(--c-text)", fontSize: 12, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={y}
            numTicks={3}
            tickFormat={pct}
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
      <figcaption className="text-[14px] font-semibold">{title}</figcaption>
    </figure>
  );
}
