/**
 * A Stock Token's price regime and price quality score (docs/REGIME.md), as a small badge.
 * Regular trades on the exchange's own session (verdigris); extended hours still post prices
 * (brass); a weekend price comes from a thin source and a frozen one is not moving (signal,
 * outlined for the weekend price so the two read apart without colour).
 */
import type { LiveRegimeT } from "@/lib/api";

const COLOR: Record<LiveRegimeT["regime"], string> = {
  regular: "var(--c-safe)",
  extended: "var(--c-brass)",
  weekend_venue: "var(--c-risk)",
  frozen: "var(--c-risk)",
};

export function RegimeDot({ regime }: { regime: LiveRegimeT["regime"] }) {
  const c = COLOR[regime];
  const outlined = regime === "weekend_venue";
  return (
    <span
      aria-hidden="true"
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
      style={outlined ? { border: `2px solid ${c}` } : { background: c }}
    />
  );
}

export function RegimeBadge({ r, size = "md" }: { r: LiveRegimeT; size?: "sm" | "md" }) {
  const q = r.quality;
  return (
    <span
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 ${size === "sm" ? "text-[14px]" : ""}`}
    >
      <span className="flex items-center gap-2 font-semibold">
        <RegimeDot regime={r.regime} />
        {r.label}
      </span>
      {q.score !== null && (
        <span
          className="rounded-full border-[1.25px] border-rule px-2 text-[14px] tabular-nums"
          title={`Price quality: staleness, DEX divergence and depth (${q.used.join(", ")})`}
        >
          Price quality {q.score}, {q.grade}
        </span>
      )}
    </span>
  );
}
