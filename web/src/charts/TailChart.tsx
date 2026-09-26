"use client";

/** Tail curve: share of closed periods with a drop at least x, one line per segment (log scale). */
import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear, scaleLog } from "@visx/scale";
import { LinePath } from "@visx/shape";

import { useWidth } from "./useWidth";

const STYLE: Record<string, { stroke: string; dash?: string; label: string }> = {
  earnings: { stroke: "var(--c-risk)", label: "Earnings nights" },
  weekend: { stroke: "var(--c-brass)", label: "Weekends" },
  holiday: { stroke: "var(--c-safe)", dash: "6 4", label: "Holidays" },
  overnight: { stroke: "var(--c-text)", dash: "2 4", label: "Ordinary nights" },
};

export function TailChart({
  drops,
  series,
  height = 260,
}: {
  drops: number[];
  series: Record<string, number[]>;
  height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const m = { top: 8, right: 12, bottom: 36, left: 52 };
  const w = Math.max(220, width) - m.left - m.right;
  const h = height - m.top - m.bottom;
  const floor = 1e-4;
  const x = scaleLinear({ domain: [drops[0], drops[drops.length - 1]], range: [0, w] });
  const y = scaleLog({ domain: [floor, 1], range: [h, 0], clamp: true });
  const keys = Object.keys(STYLE).filter((k) => series[k]);
  return (
    <div ref={ref}>
      <svg
        width={w + m.left + m.right}
        height={height}
        role="img"
        aria-label="Share of closed periods with a drop at least this large, by kind of closed period"
      >
        <Group left={m.left} top={m.top}>
          {keys.map((k) => (
            <LinePath
              key={k}
              data={series[k].map((v, i) => [drops[i], Math.max(v, floor)] as const)}
              x={(d) => x(d[0])}
              y={(d) => y(d[1])}
              stroke={STYLE[k].stroke}
              strokeDasharray={STYLE[k].dash}
              strokeWidth={2}
            />
          ))}
          <AxisBottom
            top={h}
            scale={x}
            numTicks={6}
            tickFormat={(v) => `${(Number(v) * 100).toFixed(0)}%`}
            stroke="var(--c-rule)"
            tickStroke="var(--c-rule)"
            tickLabelProps={{ fill: "var(--c-text)", fontSize: 12, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={y}
            tickValues={[1, 0.1, 0.01, 0.001, 0.0001]}
            tickFormat={(v) => `${+(Number(v) * 100).toPrecision(1)}%`}
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
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[14px]">
        {keys.map((k) => (
          <li key={k} className="flex items-center gap-2">
            <svg width="24" height="8" aria-hidden="true">
              <line
                x1="0"
                x2="24"
                y1="4"
                y2="4"
                stroke={STYLE[k].stroke}
                strokeDasharray={STYLE[k].dash}
                strokeWidth={2}
              />
            </svg>
            {STYLE[k].label}
          </li>
        ))}
      </ul>
    </div>
  );
}
