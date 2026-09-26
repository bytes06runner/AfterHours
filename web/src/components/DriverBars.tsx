import { formatPct } from "@/lib/time";

const FEATURE: Record<string, string> = {
  stock_volatility: "Stock volatility",
  closed_hours: "Hours closed",
  segment_earnings: "Earnings night",
  segment_weekend: "Weekend",
  segment_holiday: "Holiday",
  segment_overnight: "Overnight",
};

/** Signed contribution bars: brass adds to the bad case, verdigris takes away. */
export function DriverBars({
  drivers,
}: {
  drivers: { feature: string; value: number; detail: string }[];
}) {
  const scale = Math.max(...drivers.map((d) => Math.abs(d.value)), 1e-9);
  return (
    <ul className="mt-2 flex flex-col gap-2">
      {drivers.map((d) => (
        <li
          key={d.feature}
          className="grid grid-cols-[9rem_1fr_4rem] items-center gap-3 text-[14px]"
          title={d.detail}
        >
          <span>{FEATURE[d.feature] ?? d.feature}</span>
          <span className="relative h-3 rounded-full bg-bg">
            <span
              className="absolute top-0 h-3 rounded-full"
              style={{
                left: d.value < 0 ? `${50 - (50 * Math.abs(d.value)) / scale}%` : "50%",
                width: `${(50 * Math.abs(d.value)) / scale}%`,
                background: d.value < 0 ? "var(--c-safe)" : "var(--c-brass)",
              }}
            />
            <span
              aria-hidden="true"
              className="absolute left-1/2 top-[-3px] h-[18px] border-l-[1.25px] border-ink"
            />
          </span>
          <span className="text-right font-semibold">
            {d.value >= 0 ? "+" : "−"}
            {formatPct(Math.abs(d.value))}
          </span>
        </li>
      ))}
    </ul>
  );
}
