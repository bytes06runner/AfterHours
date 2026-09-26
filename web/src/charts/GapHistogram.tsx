"use client";

/**
 * Gap histogram (docs/DESIGN.md ChartKit): share of closed periods per gap bin for one segment,
 * with the drops beyond a tier's cushion shaded in the risk colour. Data from the M2 gap study.
 */
import { AxisBottom } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear } from "@visx/scale";

import { formatPct } from "@/lib/time";

import { useWidth } from "./useWidth";

export function GapHistogram({
  edges,
  share,
  cushion,
  label,
  height = 220,
}: {
  edges: number[];
  share: number[];
  cushion: number | null;
  label: string;
  height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const m = { top: 8, right: 8, bottom: 32, left: 8 };
  const w = Math.max(200, width) - m.left - m.right;
  const h = height - m.top - m.bottom;
  const x = scaleLinear({ domain: [edges[0], edges[edges.length - 1]], range: [0, w] });
  // Square-root scale so the thin tails stay visible next to the tall centre.
  const top = Math.sqrt(Math.max(...share, 1e-9));
  const y = (v: number) => (Math.sqrt(v) / top) * h;
  const beyond =
    cushion === null ? 0 : share.reduce((a, s, i) => a + (edges[i + 1] <= -cushion ? s : 0), 0);
  return (
    <div ref={ref}>
      <svg
        width={w + m.left + m.right}
        height={height}
        role="img"
        aria-label={`${label}. ${cushion === null ? "" : `${formatPct(beyond, 2)} of closed periods fell by more than the ${formatPct(cushion)} cushion.`}`}
      >
        <Group left={m.left} top={m.top}>
          {share.map((s, i) => {
            const x0 = x(edges[i]);
            const x1 = x(edges[i + 1]);
            const tail = cushion !== null && edges[i + 1] <= -cushion;
            return (
              <rect
                key={edges[i]}
                x={x0 + 0.5}
                width={Math.max(0.5, x1 - x0 - 1)}
                y={h - y(s)}
                height={y(s)}
                fill={tail ? "var(--c-risk)" : "var(--c-brass)"}
                opacity={tail ? 1 : 0.85}
              />
            );
          })}
          {cushion !== null && (
            <g>
              <line
                x1={x(-cushion)}
                x2={x(-cushion)}
                y1={0}
                y2={h}
                stroke="var(--c-text)"
                strokeWidth={1.25}
                strokeDasharray="4 4"
              />
              <text x={x(-cushion) + 6} y={12} fill="var(--c-text)" fontSize={12} fontWeight={600}>
                cushion {formatPct(cushion)}
              </text>
            </g>
          )}
          <AxisBottom
            top={h}
            scale={x}
            numTicks={width < 500 ? 5 : 9}
            tickFormat={(v) => `${(Number(v) * 100).toFixed(0)}%`}
            stroke="var(--c-rule)"
            tickStroke="var(--c-rule)"
            tickLabelProps={{ fill: "var(--c-text)", fontSize: 12, textAnchor: "middle" }}
          />
        </Group>
      </svg>
    </div>
  );
}
