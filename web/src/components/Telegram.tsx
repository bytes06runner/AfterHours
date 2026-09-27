"use client";

import type { Card } from "@/lib/api";
import { formatPct, formatUsd } from "@/lib/time";

import { TornEdge } from "@/art/TornEdge";

import { DriverBars } from "./DriverBars";
import { VerifyBadge } from "./VerifyBadge";
import { ZonedTime } from "./ZonedTime";

const TIER = {
  weekday: "weekday tier",
  middle: "middle tier",
  weekend: "weekend tier",
  idle: "idle",
} as Record<string, string>;

/** A reason card printed as a telegram slip. */
export function Telegram({ card, compact = false }: { card: Card; compact?: boolean }) {
  const drop = Number(card.prediction.bad_case_drop);
  const drivers = card.top_drivers.map((d) => ({ ...d, value: Number(d.contribution) }));
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
          <p className="text-[14px]">
            <ZonedTime iso={card.created_at} />
          </p>
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
              <DriverBars drivers={drivers} />
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
