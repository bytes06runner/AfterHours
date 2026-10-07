"use client";

/**
 * A full-width brass band of measured facts, scrolling like the exchange ticker (pauses on
 * hover, static with reduced motion). Every figure comes from /v1/report-card.
 */
import { useReportCard } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

export function FactsBand() {
  const { data } = useReportCard();
  if (!data) return <div className="facts-band" aria-hidden="true" />;
  const d = data.decision;
  const u = d.universes.vault;
  const oracle = data.oracle;
  const less = (a: number, b: number) => formatPct(1 - a / b, 0);
  const facts = [
    `${less(u.b.bad_debt, u.nearest_blend.bad_debt)} less bad debt than the fixed mix with the same yield`,
    `${less(u.b.worst, u.nearest_blend.worst)} smaller worst night`,
    `${u.pulls.total.nights} nights pulled back, ${d.evaluation_years}`,
    `${oracle.feeds_without_update} of ${oracle.feeds} feeds silent across ${oracle.weekends} weekends`,
    `${formatUsd(d.market_now.usdg_borrowed)} of ${formatUsd(d.market_now.usdg_supplied)} USDG lent against Stock Tokens on ${d.market_now.block_time.slice(0, 10)}`,
    `${formatPct(d.market_now.utilization, 1)} utilization`,
    `${formatPct(d.market_now.supply_apy, 1)} supply APY`,
  ];
  const row = (copy: number) => (
    <span className="flex shrink-0 gap-[3em] pr-[3em]" aria-hidden={copy === 1}>
      {facts.map((f) => (
        <span key={f} className="flex items-center gap-[3em]">
          <span>{f}</span>
          <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" aria-hidden="true">
            <path d="M5 0 L10 5 L5 10 L0 5 Z" fill="currentColor" />
          </svg>
        </span>
      ))}
    </span>
  );
  return (
    <section aria-label="Measured facts" className="facts-band">
      <div className="facts-track">
        {row(0)}
        {row(1)}
      </div>
      <p className="sr-only">
        Historical stock prices, simulated vault, for the backtest figures; market figures read
        onchain at block {d.market_now.block}.
      </p>
    </section>
  );
}
