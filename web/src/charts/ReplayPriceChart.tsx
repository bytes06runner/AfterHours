"use client";

/**
 * Replay price path (docs/DESIGN.md ChartKit, "replay dual timeline"): each session drawn from
 * open to close, each closed period as a night band with a dashed jump from close to next open.
 * The selected closed period is highlighted; clicking a band selects it.
 */
import { AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear } from "@visx/scale";

import type { Replay } from "@/lib/api";
import { formatPct } from "@/lib/time";

import { useWidth } from "./useWidth";

export function ReplayPriceChart({
  replay,
  index,
  onSelect,
  height = 240,
}: {
  replay: Replay;
  index: number;
  onSelect: (i: number) => void;
  height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const m = { top: 22, right: 12, bottom: 28, left: 52 };
  const w = Math.max(240, width) - m.left - m.right;
  const h = height - m.top - m.bottom;
  const days = replay.price_path;
  const slot = w / days.length;
  const day = 0.45 * slot; // session width; the rest of the slot is the closed period
  const lo = Math.min(...days.map((d) => Math.min(d.open, d.close)));
  const hi = Math.max(...days.map((d) => Math.max(d.open, d.close)));
  const y = scaleLinear({ domain: [lo * 0.97, hi * 1.03], range: [h, 0] });
  const x0 = (i: number) => i * slot;
  const x1 = (i: number) => i * slot + day;
  const short = (iso: string) =>
    new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
  return (
    <div ref={ref}>
      <svg
        width={w + m.left + m.right}
        height={height}
        role="img"
        aria-label={`${replay.ticker} price from ${days[0].date} to ${days[days.length - 1].date}; it opened ${formatPct(replay.g)} from the close on ${replay.session_prev}.`}
      >
        <Group left={m.left} top={m.top}>
          {replay.periods.map((p, i) => {
            const selected = i === index;
            return (
              <rect
                key={p.session_prev}
                x={x1(i)}
                y={0}
                width={slot - day}
                height={h}
                fill={selected ? "var(--c-brass)" : "var(--c-surface)"}
                opacity={selected ? 0.28 : 0.6}
                onClick={() => onSelect(i)}
                style={{ cursor: "pointer" }}
              />
            );
          })}
          {replay.periods.map((p, i) =>
            p.session_prev === replay.session_prev ? (
              <text
                key="event"
                x={x1(i) + (slot - day) / 2}
                y={-4}
                textAnchor="middle"
                fill={p.g < 0 ? "var(--c-risk)" : "var(--c-text)"}
                fontSize={12}
                fontWeight={700}
              >
                {formatPct(p.g)}
              </text>
            ) : null,
          )}
          {days.map((d, i) => (
            <g key={d.date}>
              <line
                x1={x0(i)}
                x2={x1(i)}
                y1={y(d.open)}
                y2={y(d.close)}
                stroke="var(--c-text)"
                strokeWidth={2}
              />
              {i + 1 < days.length && (
                <line
                  x1={x1(i)}
                  x2={x0(i + 1)}
                  y1={y(d.close)}
                  y2={y(days[i + 1].open)}
                  stroke={replay.periods[i]?.g < -0.05 ? "var(--c-risk)" : "var(--c-text)"}
                  strokeWidth={replay.periods[i]?.g < -0.05 ? 2 : 1.25}
                  strokeDasharray="3 3"
                />
              )}
              {(i % Math.ceil(days.length / Math.max(2, Math.floor(w / 72))) === 0 ||
                i === days.length - 1) && (
                <text x={x0(i)} y={h + 18} fill="var(--c-text)" fontSize={12}>
                  {short(d.date)}
                </text>
              )}
            </g>
          ))}
          <AxisLeft
            scale={y}
            numTicks={4}
            tickFormat={(v) => `$${Number(v).toFixed(0)}`}
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
    </div>
  );
}
