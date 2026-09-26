"use client";

import type { Card } from "@/lib/api";
import { formatPct, formatUsd } from "@/lib/time";

import { VerifyBadge } from "./VerifyBadge";

const TIER = { weekday: "weekday tier", weekend: "weekend tier", idle: "idle" } as Record<
  string,
  string
>;
const FEATURE: Record<string, string> = {
  stock_volatility: "Stock volatility",
  closed_hours: "Hours closed",
  segment_earnings: "Earnings night",
  segment_weekend: "Weekend",
  segment_holiday: "Holiday",
  segment_overnight: "Overnight",
};

function when(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

/** Torn bottom edge, drawn once and stretched. */
function TornEdge() {
  const teeth = Array.from(
    { length: 40 },
    (_, i) => `L${i * 10 + 5} ${i % 2 ? 2 : 8} L${(i + 1) * 10} ${i % 3 ? 4 : 1}`,
  ).join(" ");
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 400 10"
      preserveAspectRatio="none"
      className="block h-[10px] w-full"
    >
      <path d={`M0 0 ${teeth} L400 0 Z`} fill="var(--c-surface)" />
    </svg>
  );
}

/** A reason card printed as a telegram slip. */
export function Telegram({ card, compact = false }: { card: Card; compact?: boolean }) {
  const drop = Number(card.prediction.bad_case_drop);
  const drivers = card.top_drivers.map((d) => ({ ...d, value: Number(d.contribution) }));
  const scale = Math.max(...drivers.map((d) => Math.abs(d.value)), 1e-9);
  const from = TIER[card.from_tier ?? ""] ?? card.from_tier;
  const to = TIER[card.to_tier ?? ""] ?? card.to_tier;
  return (
    <article aria-label={`Reason for ${card.stock}`} className="max-w-[640px]">
      <div className="rounded-t-[12px] border-x-[1.25px] border-t-[1.25px] border-rule bg-surface px-5 pb-4 pt-5">
        <header className="flex flex-wrap items-baseline justify-between gap-2 border-b-[1.25px] border-dashed border-rule pb-3">
          <h3 className="font-display text-[24px]">
            {card.action === "queue_reorder"
              ? `Deposits now route to ${card.stock}'s ${(card.to_tier ?? "").split(":")[1] ?? ""} tier`
              : `${card.stock}: ${formatUsd(Number(card.amount_usdg))} USDG from ${from} to ${to}`}
          </h3>
          <p className="text-[14px]">{when(card.created_at)} New York</p>
        </header>
        <p className="mt-4 text-[18px] leading-[1.5]">{card.rule_fired}</p>
        {!compact && (
          <>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-[14px] sm:grid-cols-3">
              <div>
                <dt className="font-semibold">
                  Bad case (1 in {Math.round(1 / Number(card.prediction.alpha))})
                </dt>
                <dd className="text-[21px] font-bold">{formatPct(drop)}</dd>
              </div>
              <div>
                <dt className="font-semibold">Closed period</dt>
                <dd className="text-[16px]">
                  {card.closed_period.segment}, {Number(card.closed_period.hours).toFixed(1)} h
                </dd>
              </div>
              <div>
                <dt className="font-semibold">Model</dt>
                <dd className="text-[16px]">
                  {card.prediction.method} {card.prediction.model_version.slice(0, 8)}
                </dd>
              </div>
            </dl>
            <figure className="mt-4">
              <figcaption className="text-[14px] font-semibold">
                What made up the bad case
              </figcaption>
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
              <p className="mt-2 text-[12px]">
                {card.drivers_method.charAt(0).toUpperCase() + card.drivers_method.slice(1)}.
              </p>
            </figure>
          </>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <VerifyBadge card={card} />
        </div>
      </div>
      <TornEdge />
    </article>
  );
}
