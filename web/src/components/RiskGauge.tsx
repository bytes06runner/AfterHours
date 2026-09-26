"use client";

/**
 * RiskGauge (docs/DESIGN.md section 6): a semicircle from 0 to a full-scale drop. The zone up to
 * option B's pullback limit is verdigris; the needle is the bad-case drop. From /v1/risk.
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
  pullLimit,
  pulled,
}: {
  drop: number;
  pullLimit: number;
  pulled: boolean;
}) {
  const full = Math.max(0.25, Math.ceil((Math.max(drop, pullLimit) * 1.25) / 0.05) * 0.05);
  const [nx, ny] = point(drop, full, R - 14);
  return (
    <figure className="w-full max-w-[300px]">
      <svg
        viewBox="0 0 240 136"
        className="w-full"
        role="img"
        aria-label={`Bad-case drop ${formatPct(drop)} against a pullback limit of ${formatPct(pullLimit)}: ${pulled ? "pulled back" : "lending"}.`}
      >
        <path d={arc(0, full, full)} stroke="var(--c-rule)" strokeWidth={16} fill="none" />
        <path d={arc(0, pullLimit, full)} stroke="var(--c-safe)" strokeWidth={16} fill="none" />
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
        Green: lends in its mapped tier (up to {formatPct(pullLimit)}). Above it, money not lent out
        goes idle.
      </figcaption>
    </figure>
  );
}
