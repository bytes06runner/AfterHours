"use client";

/** TickerRibbon: the brass band across the facade with live Stock Token prices. */
import { usePrices } from "@/lib/queries";
import { formatUsd } from "@/lib/time";

export function TickerRibbon({ className = "flex" }: { className?: string }) {
  const { data } = usePrices();
  const items = data?.prices ?? [];
  const label = data?.source === "simulated" ? "Simulated prices" : "Chainlink prices";
  return (
    <div
      className={`ticker ${className}`}
      role="marquee"
      aria-label={label}
      style={{ fontSize: "19px" }}
    >
      <div className="ticker-track">
        {items.length === 0 ? (
          <span>Waiting for prices from the API</span>
        ) : (
          // Two copies scroll by half their width, so the band is always full and loops seamlessly.
          [0, 1].map((copy) => (
            <span key={copy} className="flex gap-[2.5em] pr-[2.5em]" aria-hidden={copy === 1}>
              {[...items, ...items].map((p, i) => (
                <span key={`${p.symbol}-${i}`}>
                  {p.symbol} {formatUsd(p.price_usdg, 2)}
                </span>
              ))}
            </span>
          ))
        )}
      </div>
    </div>
  );
}
