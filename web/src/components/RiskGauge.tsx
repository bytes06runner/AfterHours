"use client";

/**
 * RiskGauge (docs/DESIGN.md section 6): a semicircle from 0 to a full-scale drop. The allowed
 * zone for each tier (cushion minus the safety margin) is drawn in verdigris, the weekday zone
 * darker; the needle is the bad-case drop. Numbers come from /v1/risk and /v1/vault.
 */
import { formatPct } from "@/lib/time";

const R = 96;
const CX = 120;
const CY = 112;

function point(v: number, full: number, r = R): [number, number] {
  const a = Math.PI * (1 - Math.min(1, Math.max(0, v / full)));
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
}

function arc(from: number, to: number, full: number): string {
  const [x0, y0] = point(from, full);
  const [x1, y1] = point(to, full);
  return `M${x0} ${y0} A${R} ${R} 0 0 1 ${x1} ${y1}`;
}

export function RiskGauge({
  drop,
  margin,
  cushions,
}: {
  drop: number;
  margin: number;
  cushions: { weekday: number; weekend: number };
}) {
  const full = Math.max(0.25, Math.ceil((Math.max(drop, cushions.weekend) * 1.25) / 0.05) * 0.05);
  const wd = Math.max(0, cushions.weekday - margin);
  const we = Math.max(0, cushions.weekend - margin);
  const [nx, ny] = point(drop, full, R - 14);
  const tier =
    drop <= wd ? "weekday and weekend tiers" : drop <= we ? "weekend tier only" : "neither tier";
  return (
    <figure className="w-full max-w-[300px]">
      <svg
        viewBox="0 0 240 136"
        className="w-full"
        role="img"
        aria-label={`Bad-case drop ${formatPct(drop)}. Allowed in the weekday tier up to ${formatPct(wd)}, in the weekend tier up to ${formatPct(we)}. Open: ${tier}.`}
      >
        <path d={arc(0, full, full)} stroke="var(--c-rule)" strokeWidth={16} fill="none" />
        {we > 0 && (
          <path
            d={arc(0, we, full)}
            stroke="var(--c-safe)"
            strokeOpacity={0.45}
            strokeWidth={16}
            fill="none"
          />
        )}
        {wd > 0 && (
          <path d={arc(0, wd, full)} stroke="var(--c-safe)" strokeWidth={16} fill="none" />
        )}
        <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="var(--c-text)" strokeWidth={2} />
        <circle cx={CX} cy={CY} r={5} fill="var(--c-text)" />
        <text x={CX - R} y={CY + 18} fontSize={12} textAnchor="middle" fill="var(--c-text)">
          0%
        </text>
        <text x={CX + R} y={CY + 18} fontSize={12} textAnchor="middle" fill="var(--c-text)">
          {formatPct(full, 0)}
        </text>
      </svg>
      <figcaption className="text-[14px]">
        <span className="block text-[21px] font-bold">{formatPct(drop)} bad case</span>
        Dark green: weekday tier allowed (up to {formatPct(wd)}). Light green: weekend tier only (up
        to {formatPct(we)}).
      </figcaption>
    </figure>
  );
}
